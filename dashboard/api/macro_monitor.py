"""Bubble-monitor orchestration for the dashboard API.

Wraps ``src.data_sources.liquidity_monitor.LiquidityMonitor`` with:
  * SQLite persistence of each metric's series + full daily snapshots
  * a stale-value fallback (so an unavailable source — e.g. rate-limited
    yfinance options skew — reuses the last stored value instead of blanking)
  * alert diffing vs the previous snapshot, so email fires only on *new* trips
  * human-readable display formatting

Public API (imported by server.py):
    refresh_and_store(send_email=True) -> dict   # scheduler + manual endpoint
    get_latest() -> dict                          # /api/macro/monitor
    get_series(metric) -> dict                    # /api/macro/series/{metric}
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("macro_monitor")

DB_PATH = Path(__file__).parent / "macro_monitor.db"

# Optional GCS persistence so snapshot history / trip-detection state survives
# across stateless Cloud Run Job runs. No-op locally (bucket env unset).
_GCS_BUCKET = os.environ.get("GCS_MACRO_DB_BUCKET", "")
_GCS_BLOB = os.environ.get("GCS_MACRO_DB_BLOB", "macro_monitor.db")


def restore_from_gcs() -> bool:
    """Download macro_monitor.db from GCS before a run. Returns True if restored."""
    if not _GCS_BUCKET:
        return False
    try:
        from google.cloud import storage

        blob = storage.Client().bucket(_GCS_BUCKET).blob(_GCS_BLOB)
        if blob.exists():
            blob.download_to_filename(str(DB_PATH))
            logger.info("Restored macro_monitor.db from gs://%s/%s", _GCS_BUCKET, _GCS_BLOB)
            return True
    except Exception as e:  # noqa: BLE001
        logger.warning("macro DB restore failed: %s", e)
    return False


def backup_to_gcs() -> bool:
    """Upload macro_monitor.db to GCS after a run. Returns True on success."""
    if not _GCS_BUCKET or not DB_PATH.exists():
        return False
    try:
        from google.cloud import storage

        storage.Client().bucket(_GCS_BUCKET).blob(_GCS_BLOB).upload_from_filename(str(DB_PATH))
        logger.info("Backed up macro_monitor.db to gs://%s/%s", _GCS_BUCKET, _GCS_BLOB)
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("macro DB backup failed: %s", e)
    return False

# Ordered severity so we can compare statuses.
_SEV = {"unavailable": -1, "normal": 0, "yellow": 1, "red": 2}


# --------------------------------------------------------------------------- db
def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS macro_series (
               metric TEXT, date TEXT, value REAL, extra TEXT,
               PRIMARY KEY (metric, date))"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS macro_snapshots (
               ts TEXT PRIMARY KEY, overall TEXT, payload TEXT)"""
    )
    return conn


def _store_series(conn: sqlite3.Connection, metric: str, series: list[dict]) -> None:
    for p in series:
        extra = {k: v for k, v in p.items() if k not in ("date", "value")}
        conn.execute(
            "INSERT OR REPLACE INTO macro_series (metric, date, value, extra) "
            "VALUES (?, ?, ?, ?)",
            (metric, p["date"], p["value"], json.dumps(extra) if extra else None),
        )


def _load_series(conn: sqlite3.Connection, metric: str) -> list[dict]:
    rows = conn.execute(
        "SELECT date, value, extra FROM macro_series WHERE metric=? ORDER BY date",
        (metric,),
    ).fetchall()
    out = []
    for d, v, extra in rows:
        pt = {"date": d, "value": v}
        if extra:
            pt.update(json.loads(extra))
        out.append(pt)
    return out


def _load_prev_snapshot(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        "SELECT payload FROM macro_snapshots ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    return json.loads(row[0]) if row else None


# ---------------------------------------------------------------- formatting
def _display_value(metric: dict) -> str:
    """Human-readable current value string for UI + email."""
    v = metric.get("current")
    if v is None:
        return "—"
    unit = metric.get("unit")
    if unit == "usd_millions":
        return f"${v / 1e6:.2f}T" if abs(v) >= 1e6 else f"${v / 1e3:.0f}B"
    if unit == "usd_billions":
        return f"${v:.1f}B"
    if unit == "usd_thousands":
        return f"${v / 1e6:.2f}B" if abs(v) >= 1e6 else f"${v / 1e3:.1f}M"
    if unit == "basis_points":
        return f"{v:+.1f} bp"
    if unit == "percent":
        return f"{v:+.1f}%"
    if unit == "index":
        return f"{v:.1f}"
    return f"{v:g}"


# --------------------------------------------------------------------- core
def refresh_and_store(send_email: bool = True, digest: bool = False) -> dict:
    """Fetch a fresh snapshot, persist it, backfill stale metrics, alert on trips.

    ``digest=True`` sends the full-snapshot email unconditionally (used by the
    daily job so a complete snapshot lands in the inbox every day). Otherwise an
    email is sent only when a metric newly trips. Either way the email body is a
    complete snapshot of all indicators.
    """
    from src.data_sources.liquidity_monitor import LiquidityMonitor

    lm = LiquidityMonitor()
    snap = lm.snapshot()
    conn = _conn()
    try:
        prev = _load_prev_snapshot(conn)

        # 1) Persist every fetched series; backfill unavailable metrics from store.
        for key, m in snap["metrics"].items():
            if m["series"]:
                _store_series(conn, key, m["series"])
            elif m["status"] == "unavailable":
                stored = _load_series(conn, key)
                if stored:
                    cfg_m = lm.cfg["metrics"][key]
                    reeval = lm._evaluate(key, cfg_m, stored)
                    reeval["stale"] = True
                    snap["metrics"][key] = reeval
                    logger.info("Backfilled %s from stored series (stale)", key)

        # 2) Recompute the per-card aggregate after backfill (excluding context-only).
        #    overall_status stays as the confluence-based headline from snapshot() —
        #    backfill only touches options_skew, which is not a confluence input.
        statuses = [v["status"] for v in snap["metrics"].values() if not v.get("context_only")]
        snap["card_alert_status"] = (
            "red" if "red" in statuses
            else "yellow" if "yellow" in statuses
            else "unavailable" if statuses and all(s == "unavailable" for s in statuses)
            else "normal"
        )

        # 3) Add display strings.
        for m in snap["metrics"].values():
            m["display_value"] = _display_value(m)

        # 3b) AI daily commentary (DeepSeek) — best-effort, stored + emailed.
        try:
            import ai_commentary
            snap["ai_commentary"] = ai_commentary.generate_commentary(snap)
        except Exception as e:  # noqa: BLE001
            logger.warning("AI commentary failed: %s", e)
            snap["ai_commentary"] = None

        # 3c) Unit-economics (from quarterly 10-Q financials). Generates + stores a
        #     DeepSeek report when a NEW quarter is filed; else reuses the stored one.
        unit_econ_new = False
        try:
            import unit_economics
            ue = unit_economics.refresh(generate=True)
            snap["unit_economics"] = {"data": ue.get("data"), "report": ue.get("report")}
            unit_econ_new = bool(ue.get("is_new_quarter"))
        except Exception as e:  # noqa: BLE001
            logger.warning("Unit-economics refresh failed: %s", e)
            snap["unit_economics"] = None
        snap["unit_economics_new"] = unit_econ_new

        # 4) Detect newly-tripped metrics (severity increased vs previous snapshot).
        triggered = _detect_trips(prev, snap)

        # 5) Persist snapshot.
        conn.execute(
            "INSERT OR REPLACE INTO macro_snapshots (ts, overall, payload) VALUES (?,?,?)",
            (snap["generated_at"], snap["overall_status"], json.dumps(snap)),
        )
        conn.commit()

        # 6) Detect a fresh quarterly capex report (new quarter vs last snapshot).
        prev_q = (prev or {}).get("metrics", {}).get("cloud_capex_accel", {}).get("as_of_quarter")
        new_q = snap["metrics"].get("cloud_capex_accel", {}).get("as_of_quarter")
        capex_updated = bool(prev_q) and bool(new_q) and new_q != prev_q
        snap["capex_updated"] = capex_updated
        if capex_updated:
            logger.info("New cloud-capex quarter detected: %s → %s", prev_q, new_q)

        # 7) Alert — email on trips, digest, a NEW sell-now state, a fresh capex
        #    quarter, or a fresh unit-economics report (the "separate push").
        sell_transition = snap.get("sell_now") and not (prev or {}).get("sell_now", False)
        if send_email and (triggered or digest or sell_transition or capex_updated or unit_econ_new):
            import email_alerts

            email_alerts.send_snapshot(snap, triggered, digest=digest)
        snap["triggered"] = triggered
        return snap
    finally:
        conn.close()


_CONF_LEVEL = {"normal": 0, "yellow": 1, "red": 2, "top": 3}


def _detect_trips(prev: dict | None, snap: dict) -> list[dict]:
    """Alert ONLY when the creator's actual framework escalates.

    The video's alerts are CONFLUENCE combos (SOFR+reserves+TGA yellow; the red
    combo; the resonance top), plus standalone sells (handled separately via
    sell_now). Individual card status changes (e.g. SRF ticking to yellow on a
    routine repo op, TGA at $0.9T, reserves at $2.9T, low options-skew) are NOT
    thesis alerts — firing on them produced false alarms. So we escalate the email
    only on a confluence-LEVEL increase; sell triggers are caught by sell_now.
    """
    now_conf = snap.get("confluence", {}) or {}
    now_level = now_conf.get("level", "normal")
    prev_level = ((prev or {}).get("confluence", {}) or {}).get("level", "normal")
    if _CONF_LEVEL.get(now_level, 0) <= _CONF_LEVEL.get(prev_level, 0):
        return []  # no escalation

    met = [c["label"] for grp in ("yellow", "red", "top")
           for c in now_conf.get(grp, []) if c.get("met")]
    return [{
        "key": "confluence",
        "label": f"Confluence combo → {now_level.upper()}",
        "status": "red" if now_level in ("red", "top") else "yellow",
        "current": None,
        "display_value": ", ".join(met) if met else now_level.upper(),
        "percentile": None,
        "transition": f"{prev_level} → {now_level}",
    }]


def get_latest() -> dict:
    """Return the most recent stored snapshot, or refresh if none exists."""
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT payload FROM macro_snapshots ORDER BY ts DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if row:
        return json.loads(row[0])
    return refresh_and_store(send_email=False)


def get_series(metric: str) -> dict:
    """Return the full stored time series for one metric (for charting)."""
    conn = _conn()
    try:
        series = _load_series(conn, metric)
    finally:
        conn.close()
    return {"metric": metric, "series": series, "points": len(series)}

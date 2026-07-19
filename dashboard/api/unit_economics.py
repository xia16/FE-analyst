"""Unit-economics / capital-structure signals — the AI-bubble "layered collapse"
thesis (companion video). Computed from quarterly SEC 10-Q financials.

Automatable pieces only:
  - DSO (days-sales-outstanding) per hyperscaler + aggregate, with YoY trend — the
    creator's "lazy man's" systemic-deleveraging tell (cloud providers extending
    credit to customers who can't pay = vendor-financed demand).
  - Capex carrying-cost threshold — the ~$Xxx B/yr of external gross profit the
    current capex must earn back just to break even, vs. the real AI top line.

Survey-based indicators from the video (NRR, pilot-conversion, down-rounds,
secondary discounts) have no free feed and are deliberately omitted.

A DeepSeek "quarterly unit-economics report" is generated whenever a NEW quarter
is filed (detected by SEC filing date), then surfaced as its own section in the
daily email + a push, and stored in macro_monitor.db.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import urllib.request
from datetime import date, datetime
from pathlib import Path

logger = logging.getLogger("unit_economics")

DB_PATH = Path(__file__).parent / "macro_monitor.db"

_SYS_PROMPT = (
    "You are writing the quarterly 'unit-economics' note for an AI-bubble monitor "
    "built on a specific thesis (from a market-analysis video): the AI build-out is "
    "long-lived assets (GPUs, data centres) funded by short-duration private capital "
    "and demand that can vanish — so it 'collapses in layers' (分层塌方), and the "
    "FINANCING STRUCTURE breaks before the technology. Key tells: (1) capital "
    "coverage — the hyperscalers' capex is enormous vs the real external AI revenue "
    "that must cover its ~25%/yr carrying cost; (2) rising DSO (days-sales-"
    "outstanding) = cloud providers extending credit to customers who can't pay, i.e. "
    "vendor-financed demand; watch the aggregate + trend.\n\n"
    "Given the freshly-filed quarter's figures below, write a tight report (4-6 "
    "sentences, no bullet points, no headings, no preamble). Lead with the capex-vs-"
    "revenue coverage gap in concrete numbers, then the DSO picture (level + YoY "
    "change, flag any company or the aggregate whose DSO is lengthening materially), "
    "then what it implies for the layered-collapse thesis this quarter, and end with "
    "the single number to watch next quarter. Be specific and quantitative, neutral "
    "and analytical. No buy/sell advice, no disclaimers."
)


# --------------------------------------------------------------------------- db
def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA busy_timeout=8000")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS unit_economics_reports (
               quarter TEXT PRIMARY KEY, filed TEXT, generated_at TEXT,
               data TEXT, report TEXT)"""
    )
    return conn


def _http_json(url: str, ua: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


class UnitEconomics:
    def __init__(self, config: dict | None = None):
        from src.data_sources.liquidity_monitor import LiquidityMonitor, _load_config, SEC_UA

        self._LM = LiquidityMonitor
        self.lm = LiquidityMonitor(config)
        self.cfg = (config or _load_config()).get("unit_economics", {})
        self.ua = SEC_UA

    # ---------------------------------------------------------- SEC helpers
    def _usd_units(self, cik: str, concepts: list[str], pick_freshest: bool = True) -> list[dict]:
        """Return the USD facts for the first (or freshest) concept that has data."""
        best, best_latest = [], ""
        for concept in concepts:
            url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json"
            try:
                units = _http_json(url, self.ua).get("units", {}).get("USD", [])
            except Exception:  # noqa: BLE001
                continue
            if not units:
                continue
            if not pick_freshest:
                return units
            latest = max(u["end"] for u in units)
            if latest > best_latest:
                best_latest, best = latest, units
        return best

    @staticmethod
    def _ar_by_quarter(units: list[dict]) -> dict[str, float]:
        """Accounts receivable is a point-in-time balance — value at each period end."""
        out: dict[str, tuple[float, str]] = {}
        for u in units:
            if u.get("form") not in ("10-Q", "10-K"):
                continue
            prev = out.get(u["end"])
            if prev is None or u.get("filed", "") > prev[1]:
                out[u["end"]] = (float(u["val"]), u.get("filed", ""))
        return {k: v[0] for k, v in out.items()}

    # ------------------------------------------------------------- compute
    def compute(self) -> dict:
        days = int(self.cfg.get("days_in_quarter", 91))
        companies = self.cfg.get("companies", {})
        ar_concepts = self.cfg.get("ar_concepts", ["AccountsReceivableNetCurrent"])
        rev_concepts = self.cfg.get("revenue_concepts", ["Revenues"])

        per_co, latest_filed, latest_quarter = [], "", ""
        for name, meta in companies.items():
            cik = meta["cik"]
            ar_q = self._ar_by_quarter(self._usd_units(cik, ar_concepts))
            rev_units = self._usd_units(cik, rev_concepts)
            rev_q, rev_filed = self._LM._derive_quarters(rev_units)
            common = sorted(set(ar_q) & set(rev_q))
            if not common:
                logger.warning("Unit-economics: no aligned AR/rev for %s", name)
                continue
            end = common[-1]
            dso = round(ar_q[end] / rev_q[end] * days, 1) if rev_q[end] else None
            # YoY: same quarter ~4 prints back
            dso_yoy = None
            if len(common) >= 5:
                p = common[-5]
                if rev_q.get(p):
                    dso_yoy = round(ar_q[p] / rev_q[p] * days, 1)
            filed = rev_filed.get(end, "")
            latest_filed = max(latest_filed, filed)
            latest_quarter = max(latest_quarter, end)
            per_co.append({
                "company": name, "quarter": end,
                "ar_usd": round(ar_q[end], 0), "rev_usd": round(rev_q[end], 0),
                "dso": dso, "dso_yoy": dso_yoy,
                "dso_change": round(dso - dso_yoy, 1) if (dso and dso_yoy) else None,
                "filed": filed,
            })

        # Aggregate DSO = total AR / total quarterly revenue (latest common quarter)
        agg_ar = sum(c["ar_usd"] for c in per_co if c["quarter"] == latest_quarter)
        agg_rev = sum(c["rev_usd"] for c in per_co if c["quarter"] == latest_quarter)
        agg_dso = round(agg_ar / agg_rev * days, 1) if agg_rev else None

        # Capex carrying-cost threshold from the existing aggregate capex series.
        capex_series = self.lm._fetch_sec_capex(self.lm.cfg["metrics"]["cloud_capex_accel"])
        ttm_capex = sum(p.get("capex_usd", 0) for p in capex_series[-4:]) if capex_series else 0
        carrying_rate = float(self.cfg.get("carrying_rate", 0.25))
        gross_margin = float(self.cfg.get("gross_margin", 0.65))
        carrying_cost = ttm_capex * carrying_rate
        revenue_needed = carrying_cost / gross_margin if gross_margin else None

        return {
            "quarter": latest_quarter,
            "filed": latest_filed,
            "companies": per_co,
            "aggregate_dso": agg_dso,
            "ttm_capex_usd": round(ttm_capex, 0),
            "carrying_rate": carrying_rate,
            "gross_margin": gross_margin,
            "annual_carrying_cost_usd": round(carrying_cost, 0),
            "external_revenue_needed_usd": round(revenue_needed, 0) if revenue_needed else None,
            "dso_alert_yoy_days": float(self.cfg.get("dso_alert_yoy_days", 5)),
        }

    # -------------------------------------------------------------- report
    @staticmethod
    def _summarize(data: dict) -> str:
        b = 1e9
        lines = [f"Freshly filed quarter: {data['quarter']} (filed {data['filed']})", ""]
        lines.append(
            f"Hyperscaler TTM capex ≈ ${data['ttm_capex_usd']/b:.0f}B → annual carrying cost "
            f"(~{data['carrying_rate']*100:.0f}%) ≈ ${data['annual_carrying_cost_usd']/b:.0f}B, "
            f"needing ≈ ${(data['external_revenue_needed_usd'] or 0)/b:.0f}B/yr of external AI "
            f"gross profit (at {data['gross_margin']*100:.0f}% margin) just to break even."
        )
        lines.append(f"Aggregate DSO: {data['aggregate_dso']} days.")
        lines.append("Per company (DSO days, YoY change):")
        for c in data["companies"]:
            chg = f"{c['dso_change']:+.1f}" if c["dso_change"] is not None else "n/a"
            lines.append(f"  {c['company']}: {c['dso']}d (YoY {chg}), AR ${c['ar_usd']/b:.1f}B, "
                         f"rev ${c['rev_usd']/b:.1f}B")
        return "\n".join(lines)

    def generate_report(self, data: dict) -> str | None:
        import ai_commentary
        return ai_commentary.call_deepseek(_SYS_PROMPT, self._summarize(data), max_tokens=400)


# ------------------------------------------------------------------- public
def refresh(generate: bool = True) -> dict:
    """Compute unit-economics; generate + store a report if a NEW quarter was filed.

    Returns {data, report, is_new_quarter}. `report` is the latest stored report
    (regenerated only when the filed date advances) so the daily email always has one.
    """
    ue = UnitEconomics()
    try:
        data = ue.compute()
    except Exception as e:  # noqa: BLE001
        logger.error("Unit-economics compute failed: %s", e)
        return {"data": None, "report": _load_latest_report(), "is_new_quarter": False}

    conn = _conn()
    try:
        row = conn.execute(
            "SELECT quarter, filed, report FROM unit_economics_reports ORDER BY quarter DESC LIMIT 1"
        ).fetchone()
        prev_filed = row[1] if row else None
        is_new = bool(data.get("filed")) and data["filed"] != prev_filed
        report = row[2] if row else None
        if is_new and generate:
            new_report = ue.generate_report(data)
            if new_report:
                report = new_report
                conn.execute(
                    "INSERT OR REPLACE INTO unit_economics_reports "
                    "(quarter, filed, generated_at, data, report) VALUES (?,?,?,?,?)",
                    (data["quarter"], data["filed"], datetime.utcnow().isoformat() + "Z",
                     json.dumps(data), report),
                )
                conn.commit()
                logger.info("Unit-economics report generated for %s (filed %s)",
                            data["quarter"], data["filed"])
        return {"data": data, "report": report, "is_new_quarter": is_new}
    finally:
        conn.close()


def _load_latest_report() -> str | None:
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT report FROM unit_economics_reports ORDER BY quarter DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_latest() -> dict:
    """Latest stored report + its data (for the API / email), without regenerating."""
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT quarter, filed, generated_at, data, report FROM unit_economics_reports "
            "ORDER BY quarter DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return {"quarter": None, "report": None, "data": None}
    return {"quarter": row[0], "filed": row[1], "generated_at": row[2],
            "data": json.loads(row[3]) if row[3] else None, "report": row[4]}


if __name__ == "__main__":  # smoke test
    r = refresh(generate=True)
    d = r["data"]
    if d:
        print(f"quarter={d['quarter']} filed={d['filed']} agg_DSO={d['aggregate_dso']} "
              f"carrying=${d['annual_carrying_cost_usd']/1e9:.0f}B new={r['is_new_quarter']}")
        print("\nREPORT:\n", r["report"])

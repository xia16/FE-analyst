"""Email alerts for the bubble monitor — Gmail SMTP via app password.

Every email is a COMPLETE, self-contained snapshot of all indicators so the
recipient never has to open the live dashboard. Rendered in email-safe HTML:
table-based layout, inline styles, and HTML bar sparklines only — no external
CSS, no <style> reliance, no SVG, no data-URI images (Gmail strips all three).

Configuration (all from environment / .env):
    SMTP_USER        Gmail address to send from (e.g. adamxyz96@gmail.com)
    SMTP_PASS        Gmail App Password (https://myaccount.google.com/apppasswords)
    SMTP_HOST        default smtp.gmail.com
    SMTP_PORT        default 587
    ALERT_RECIPIENT  where to send (default = SMTP_USER)

If SMTP_USER / SMTP_PASS are unset, send_snapshot() logs and no-ops so the daily
job never crashes on a missing credential.
"""

from __future__ import annotations

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger("email_alerts")

_FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

# Status → (text/accent color, chip background). Tuned for readability on the
# dark card background AND when a client forces a light background.
_STATUS = {
    "red":         ("#ef4444", "#3a1417"),
    "yellow":      ("#f59e0b", "#3a2c10"),
    "normal":      ("#22c55e", "#0f2a18"),
    "unavailable": ("#9ca3af", "#23262f"),
}

# Display order (mirrors the dashboard).
_ORDER = [
    "reserves", "sofr_iorb_spread", "tga", "on_rrp",
    "srf_usage", "cloud_capex_accel", "options_skew",
]


def _cfg() -> dict:
    user = os.getenv("SMTP_USER", "")
    return {
        "user": user,
        "password": os.getenv("SMTP_PASS", ""),
        "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "recipient": os.getenv("ALERT_RECIPIENT", user),
    }


def is_configured() -> bool:
    c = _cfg()
    return bool(c["user"] and c["password"])


def _fmt_ts(iso: str) -> str:
    """'2026-07-07T07:08:53.4Z' -> '07 Jul 2026, 07:08 UTC' (best-effort)."""
    from datetime import datetime

    try:
        s = iso.replace("Z", "").split(".")[0]
        return datetime.fromisoformat(s).strftime("%d %b %Y, %H:%M UTC")
    except (ValueError, TypeError):
        return iso


# --------------------------------------------------------------- HTML pieces
def _sparkline(series: list[dict], color: str, n: int = 44, height: int = 34) -> str:
    """A pure-HTML bar sparkline (email-safe: table cells with bgcolor + height)."""
    pts = [p["value"] for p in (series or []) if p.get("value") is not None]
    if len(pts) < 3:
        return ""
    if len(pts) > n:  # evenly downsample
        step = len(pts) / n
        pts = [pts[min(len(pts) - 1, int(i * step))] for i in range(n)]
    lo, hi = min(pts), max(pts)
    rng = (hi - lo) or 1.0
    cells = []
    for v in pts:
        h = 2 + int((v - lo) / rng * (height - 2))
        cells.append(
            f'<td valign="bottom" style="padding:0 1px;font-size:0;line-height:0">'
            f'<div style="width:4px;height:{h}px;background:{color};opacity:.8;'
            f'font-size:0;line-height:0">&nbsp;</div></td>'
        )
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" '
        f'style="height:{height}px;margin-top:10px;border-collapse:collapse">'
        f"<tr>{''.join(cells)}</tr></table>"
    )


def _pct_bar(pct: float | None, color: str) -> str:
    """Trailing-percentile bar built from two coloured table cells."""
    w = 0 if pct is None else max(1, min(100, int(round(pct))))
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="margin-top:8px;border-collapse:collapse"><tr>'
        f'<td width="{w}%" bgcolor="{color}" '
        'style="height:6px;font-size:0;line-height:0;border-radius:3px">&nbsp;</td>'
        f'<td width="{100 - w}%" bgcolor="#2a2d3e" '
        'style="height:6px;font-size:0;line-height:0">&nbsp;</td>'
        "</tr></table>"
    )


def _card(m: dict, triggered_keys: set) -> str:
    color, chip_bg = _STATUS.get(m.get("status", "unavailable"), _STATUS["unavailable"])
    ctx = m.get("context_only")
    info = m.get("informational")
    chip_label = "CONTEXT" if ctx else "TIMING" if info else m.get("status", "").upper()
    if ctx:  # context-only cards are muted — not alert-colored
        color, chip_bg = _STATUS["unavailable"]
    elif info:  # informational/timing signal — neutral indigo, not an alert colour
        color, chip_bg = "#a5b4fc", "#1e2140"
    is_trig = (m.get("key") in triggered_keys) and not ctx
    border = color if is_trig else "#2a2d3e"
    pct = m.get("percentile")
    pct_txt = f"{int(round(pct))}th pctile" if pct is not None else "no percentile"
    stale = (
        ' <span style="font-size:10px;color:#f59e0b;font-weight:400">· stale</span>'
        if m.get("stale") else ""
    )
    trig_line = (
        f'<div style="margin-top:8px;font:600 11px {_FONT};color:{color}">'
        f'▲ newly {m.get("status","").upper()}</div>'
        if is_trig else ""
    )
    sell = m.get("sell_signal")
    sell_line = ""
    if sell:
        active = m.get("sell_active")
        high = sell.get("priority") == "high"
        if active:
            sc, sbg, stext = "#ffffff", "#dc2626", "⚑ SELL NOW"
        elif high:
            sc, sbg, stext = "#f87171", "#3a1417", "⚑ SELL-NOW TRIGGER"
        else:
            sc, sbg, stext = "#fbbf24", "#3a2c10", "SELL-CONFIRM"
        sell_line = (
            f'<div style="margin-top:8px"><span style="font:700 9px {_FONT};color:{sc};'
            f'background:{sbg};padding:3px 7px;border-radius:5px">{stext}</span></div>'
        )
    asof_line = ""
    if m.get("as_of_quarter"):
        parts = [f"latest {m['as_of_quarter']}"]
        if m.get("as_of_filed"):
            parts.append(f"filed {m['as_of_filed']}")
        if m.get("next_expected"):
            parts.append(f"next ~{m['next_expected']}")
        asof_line = (
            f'<div style="margin-top:8px;font:400 10px {_FONT};color:#6b7280">'
            f'{" · ".join(parts)}</div>'
        )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:#151827;border:1px solid {border};border-radius:12px;'
        'border-collapse:separate"><tr><td style="padding:14px 16px">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="font:600 12px {_FONT};color:#a0a2ab;line-height:1.3">{m.get("label","")}</td>'
        f'<td align="right" valign="top"><span style="font:700 10px {_FONT};color:{color};'
        f'background:{chip_bg};padding:3px 8px;border-radius:6px;white-space:nowrap">'
        f'{chip_label}</span></td></tr></table>'
        f'<div style="font:700 26px {_FONT};color:{color};padding:10px 0 2px">'
        f'{m.get("display_value","—")}{stale}</div>'
        f'<div style="font:400 10px {_FONT};color:#8b8d97;text-transform:uppercase;'
        f'letter-spacing:.4px">trailing · {pct_txt}</div>'
        f'{_pct_bar(pct, color)}{_sparkline(m.get("series"), color)}{trig_line}{sell_line}{asof_line}'
        "</td></tr></table>"
    )


def _ai_commentary_html(snap: dict) -> str:
    txt = snap.get("ai_commentary")
    if not txt:
        return ""
    return (
        f'<div style="background:#141a2e;border:1px solid #2a3352;border-left:3px solid #6366f1;'
        f'border-radius:10px;padding:14px 16px;margin:0 6px 12px">'
        f'<div style="font:700 11px {_FONT};color:#a5b4fc;text-transform:uppercase;'
        f'letter-spacing:.5px;margin-bottom:6px">🤖 AI daily note</div>'
        f'<div style="font:400 13px {_FONT};color:#d1d5db;line-height:1.6">{txt}</div></div>'
    )


def _sellnow_html(snap: dict) -> str:
    if not snap.get("sell_now"):
        return ""
    reasons = snap.get("sell_reasons") or []
    items = "".join(
        f'<li style="margin:2px 0"><b style="color:#f87171">{r.get("label")}</b> — {r.get("action")}</li>'
        for r in reasons
    ) or '<li style="margin:2px 0">Confluence reached a structural-top (red) state — clear positions.</li>'
    return (
        f'<div style="background:rgba(220,38,38,0.10);border:2px solid #dc2626;border-radius:12px;'
        f'padding:14px 16px;margin:0 6px 12px">'
        f'<div style="font:700 14px {_FONT};color:#f87171;text-transform:uppercase;'
        f'letter-spacing:.5px;margin-bottom:6px">⚑ Sell-now signal active</div>'
        f'<ul style="margin:0;padding-left:18px;font:400 13px {_FONT};color:#e5e7eb">{items}</ul></div>'
    )


def _confluence_html(conf: dict) -> str:
    if not conf:
        return ""
    color, bg = _STATUS.get(conf.get("level", "normal"), _STATUS["normal"])
    rows = ""
    for grp, title in (("yellow", "Yellow combo"), ("red", "Red combo"), ("top", "Top resonance")):
        for cnd in conf.get(grp, []):
            mark = "✓" if cnd["met"] else "○"
            mcol = color if cnd["met"] else "#6b7280"
            rows += (
                f'<tr><td style="padding:3px 10px;font:700 12px {_FONT};color:{mcol};width:16px">{mark}</td>'
                f'<td style="padding:3px 6px;font:400 12px {_FONT};color:#d1d5db">{cnd["label"]}</td>'
                f'<td style="padding:3px 10px;font:400 11px {_FONT};color:#8b8d97" align="right">{cnd["detail"]}</td></tr>'
            )
    return (
        f'<div style="background:#151827;border:1px solid {color};border-radius:12px;'
        f'padding:14px 16px;margin:0 6px 12px">'
        f'<div style="font:700 13px {_FONT};color:{color};text-transform:uppercase;'
        f'letter-spacing:.5px;margin-bottom:2px">Confluence · {conf.get("level","").upper()}</div>'
        f'<div style="font:400 12px {_FONT};color:#a0a2ab;margin-bottom:8px">{conf.get("headline","")}</div>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table>'
        "</div>"
    )


def _topmodel_html(snap: dict) -> str:
    tm = snap.get("top_model") or []
    if not tm:
        return ""
    n, tot = snap.get("top_model_triggered", 0), snap.get("top_model_total", len(tm))
    rows = ""
    for t in tm:
        trig = t.get("triggered")
        dot_c = _STATUS["red"][0] if trig else _STATUS["normal"][0]
        tag = "live" if t.get("live") else "manual"
        val = t.get("value")
        unit = t.get("unit", "")
        vtxt = "—" if val is None else (
            f"{val:.1f}%" if unit in ("percent", "percent_ratio") else f"{val:g}"
        )
        asof = f"as-of {t['as_of']}" if t.get("as_of") else "live"
        rows += (
            f'<tr><td style="padding:4px 10px;font:700 13px {_FONT};color:{dot_c};width:16px">●</td>'
            f'<td style="padding:4px 6px;font:400 12px {_FONT};color:#d1d5db">{t["label"]}'
            f' <span style="color:#6b7280;font-size:10px">({asof})</span></td>'
            f'<td style="padding:4px 10px;font:600 12px {_FONT};color:#fff" align="right">{vtxt}</td></tr>'
        )
    return (
        f'<div style="background:#151827;border:1px solid #2a2d3e;border-radius:12px;'
        f'padding:14px 16px;margin:12px 6px 0">'
        f'<div style="font:700 13px {_FONT};color:#e5e7eb;margin-bottom:8px">'
        f'Secondary top-model &nbsp;<span style="color:#8b8d97;font-weight:400">'
        f'{n}/{tot} triggered</span></div>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table>'
        f'<div style="font:400 10px {_FONT};color:#6b7280;margin-top:8px">'
        'Fully automated (FRED + State Street SPY holdings) — each with its own as-of date.</div>'
        "</div>"
    )


def _liquidity_calendar_html(snap: dict) -> str:
    lc = snap.get("liquidity_calendar")
    if not lc:
        return ""
    tag = (f"ACTIVE · peak ~{lc.get('peak')} ({lc.get('days_to_peak')}d)"
           if lc.get("phase") == "active" else f"UPCOMING in {lc.get('days_to_start')}d")
    return (
        f'<div style="background:#1a1710;border:1px solid #3a3320;border-left:3px solid #d97706;'
        f'border-radius:10px;padding:12px 16px;margin:0 6px 12px">'
        f'<div style="font:700 11px {_FONT};color:#fbbf24;text-transform:uppercase;'
        f'letter-spacing:.5px">📅 Liquidity calendar · {tag}</div>'
        f'<div style="font:700 13px {_FONT};color:#e5e7eb;margin-top:4px">{lc.get("label")}</div>'
        f'<div style="font:400 12px {_FONT};color:#a0a2ab;margin-top:3px;line-height:1.5">'
        f'{lc.get("detail")}</div></div>'
    )


def _capex_update_html(snap: dict) -> str:
    if not snap.get("capex_updated"):
        return ""
    cap = snap.get("metrics", {}).get("cloud_capex_accel", {})
    return (
        f'<div style="background:#10233a;border:1px solid #3b82f6;border-radius:12px;'
        f'padding:12px 16px;margin:0 6px 12px">'
        f'<div style="font:700 12px {_FONT};color:#60a5fa;text-transform:uppercase;'
        f'letter-spacing:.5px">📄 New cloud-capex quarter filed</div>'
        f'<div style="font:400 12px {_FONT};color:#d1d5db;margin-top:4px">'
        f'Latest {cap.get("as_of_quarter","")} · filed {cap.get("as_of_filed","")} · '
        f'QoQ {cap.get("display_value","")}. The sell-trigger has been re-evaluated.</div></div>'
    )


def _render_html(snap: dict, triggered: list[dict]) -> str:
    overall = snap.get("overall_status", "normal")
    o_color, o_bg = _STATUS.get(overall, _STATUS["unavailable"])
    metrics = snap.get("metrics", {})
    triggered_keys = {t.get("key") for t in triggered}
    generated = _fmt_ts(snap.get("generated_at", ""))

    keys = [k for k in _ORDER if k in metrics] + [k for k in metrics if k not in _ORDER]
    # Two-column grid of cards.
    rows = ""
    for i in range(0, len(keys), 2):
        left = _card(metrics[keys[i]], triggered_keys)
        right = (
            _card(metrics[keys[i + 1]], triggered_keys)
            if i + 1 < len(keys) else "&nbsp;"
        )
        rows += (
            '<tr>'
            f'<td width="50%" valign="top" style="padding:6px">{left}</td>'
            f'<td width="50%" valign="top" style="padding:6px">{right}</td>'
            "</tr>"
        )

    trip_banner = ""
    if triggered:
        items = "".join(
            f'<li style="margin:2px 0">{t.get("label")}: '
            f'<b>{t.get("display_value", t.get("current"))}</b> '
            f'<span style="color:#8b8d97">({t.get("transition","")})</span></li>'
            for t in triggered
        )
        trip_banner = (
            f'<div style="background:{o_bg};border:1px solid {o_color};border-radius:10px;'
            f'padding:12px 16px;margin:0 6px 10px"><div style="font:700 12px {_FONT};'
            f'color:{o_color};text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">'
            f'{len(triggered)} indicator(s) newly tripped</div>'
            f'<ul style="margin:0;padding-left:18px;font:400 13px {_FONT};color:#d1d5db">'
            f'{items}</ul></div>'
        )

    return (
        f'<div style="background:#0f1117;padding:20px 12px;font-family:{_FONT}">'
        '<div style="max-width:720px;margin:0 auto">'
        f'<div style="font:700 20px {_FONT};color:#ffffff;margin-bottom:2px">'
        f'AI Bubble Monitor &nbsp;'
        f'<span style="font-size:13px;color:{o_color};background:{o_bg};padding:3px 9px;'
        f'border-radius:6px;vertical-align:middle">{overall.upper()}</span></div>'
        f'<div style="font:400 12px {_FONT};color:#8b8d97;margin-bottom:14px">'
        f'Liquidity &amp; momentum indicators · percentile-scored · {generated}</div>'
        f'{_ai_commentary_html(snap)}'
        f'{_sellnow_html(snap)}'
        f'{_capex_update_html(snap)}'
        f'{_liquidity_calendar_html(snap)}'
        f'{trip_banner}'
        f'{_confluence_html(snap.get("confluence"))}'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse">{rows}</table>'
        f'{_topmodel_html(snap)}'
        f'<div style="font:400 11px {_FONT};color:#6b7280;margin:14px 6px 0;line-height:1.5">'
        'Bars = trailing-window percentile · sparklines = ~2yr trend. Percentiles auto-'
        'recalibrate; the thesis reference thresholds appear on the dashboard as static '
        'lines. Monitoring only — not financial advice.</div>'
        "</div></div>"
    )


def _render_plain(snap: dict, triggered: list[dict]) -> str:
    lines = [f"AI Bubble Monitor — {snap.get('overall_status','').upper()}",
             _fmt_ts(snap.get("generated_at", "")), ""]
    if snap.get("ai_commentary"):
        lines += ["AI DAILY NOTE:", snap["ai_commentary"], ""]
    if snap.get("sell_now"):
        lines.append("*** SELL-NOW SIGNAL ACTIVE ***")
        for r in snap.get("sell_reasons", []):
            lines.append(f"  ⚑ {r.get('label')} — {r.get('action')}")
        lines.append("")
    if triggered:
        lines.append("NEWLY TRIPPED:")
        for t in triggered:
            lines.append(f"  [{t.get('status','').upper()}] {t.get('label')}: "
                         f"{t.get('display_value', t.get('current'))} ({t.get('transition','')})")
        lines.append("")
    lines.append("ALL INDICATORS:")
    metrics = snap.get("metrics", {})
    order = [k for k in _ORDER if k in metrics] + [k for k in metrics if k not in _ORDER]
    for k in order:
        m = metrics[k]
        pct = m.get("percentile")
        pct_txt = f"{int(round(pct))}th pctile" if pct is not None else "n/a"
        stale = " (stale)" if m.get("stale") else ""
        ctx = " [context]" if m.get("context_only") else ""
        lines.append(f"  [{m.get('status','').upper():11s}] {m.get('label')}: "
                     f"{m.get('display_value','—')}{stale}{ctx} · {pct_txt}")
    conf = snap.get("confluence")
    if conf:
        lines += ["", f"CONFLUENCE: {conf.get('level','').upper()} — {conf.get('headline','')}"]
        for grp in ("yellow", "red", "top"):
            for c in conf.get(grp, []):
                lines.append(f"  [{grp:6s}] {'MET' if c['met'] else '  -'} {c['label']} ({c['detail']})")
    lc = snap.get("liquidity_calendar")
    if lc:
        when = (f"active, peak ~{lc.get('peak')}" if lc.get("phase") == "active"
                else f"upcoming in {lc.get('days_to_start')}d")
        lines += ["", f"LIQUIDITY CALENDAR ({when}): {lc.get('label')} — {lc.get('detail')}"]
    tm = snap.get("top_model")
    if tm:
        lines += ["", f"TOP MODEL ({snap.get('top_model_triggered',0)}/{snap.get('top_model_total',len(tm))} triggered):"]
        for t in tm:
            lines.append(f"  [{'TRIG' if t['triggered'] else '  - '}] {t['label']}: {t.get('value')} "
                         f"({'live' if t.get('live') else 'manual'})")
    return "\n".join(lines)


# ------------------------------------------------------------------- send
def send_snapshot(snap: dict, triggered: list[dict] | None = None,
                  digest: bool = False) -> bool:
    """Email a full snapshot of every indicator. Returns True on success.

    Subject reflects whether anything newly tripped; the body always contains
    the complete dashboard state so the recipient needn't open the live site.
    """
    triggered = triggered or []
    if not is_configured():
        logger.warning("Email not configured (SMTP_USER/SMTP_PASS) — skipping send")
        return False

    c = _cfg()
    overall = snap.get("overall_status", "normal").upper()
    if snap.get("sell_now"):
        subject = f"[AI Bubble Monitor] ⚑ SELL-NOW SIGNAL ACTIVE — {overall}"
    elif triggered:
        n = len(triggered)
        subject = f"[AI Bubble Monitor] {overall} — {n} indicator{'s' if n != 1 else ''} tripped"
    else:
        subject = f"[AI Bubble Monitor] Daily snapshot — {overall}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = c["user"]
    msg["To"] = c["recipient"]
    msg.attach(MIMEText(_render_plain(snap, triggered), "plain"))
    msg.attach(MIMEText(_render_html(snap, triggered), "html"))

    try:
        with smtplib.SMTP(c["host"], c["port"], timeout=30) as server:
            server.starttls()
            server.login(c["user"], c["password"])
            server.sendmail(c["user"], [c["recipient"]], msg.as_string())
        logger.info("Sent bubble-monitor snapshot to %s (%d trips, digest=%s)",
                    c["recipient"], len(triggered), digest)
        return True
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to send snapshot email: %s", e)
        return False

"""DeepSeek AI daily commentary for the AI-bubble monitor.

Feeds the day's scored snapshot to DeepSeek (OpenAI-compatible API) and returns a
short, grounded paragraph on the trend. Gracefully returns None if the key is
missing or the call fails, so the daily digest never breaks on it.

Env:
    DEEPSEEK_API_KEY   DeepSeek API key (stored in .env, gitignored)
"""

from __future__ import annotations

import os
import json
import logging
import urllib.request

logger = logging.getLogger("ai_commentary")

API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"

SYSTEM_PROMPT = (
    "You are the daily-note strategist for an AI-bubble monitor built on ONE "
    "specific thesis (from a market-analysis video). Reason strictly inside this "
    "framework:\n"
    "1. TWO-WAVE / GHOST-STORY WASHOUT: super-bubbles don't top in one wave. Scary "
    "narratives (rate fears, recession) wash weak retail hands out to institutions, "
    "then a second-wave melt-up follows. Don't read a scary tape as the top.\n"
    "2. CISCO PARADOX / CAPITAL-CYCLE RIGIDITY: upstream suppliers (Micron) print "
    "record margins and profits AT the top because of non-cancellable take-or-pay "
    "contracts; Cisco fell 88% while revenue kept GROWING. So IGNORE current "
    "earnings and ABSOLUTE capex. The real top-tell is the SECOND DERIVATIVE — the "
    "sequential (QoQ) growth RATE of downstream cloud capex (MSFT/GOOG/META/AMZN). "
    "When that rate peaks/rolls over — even with profits at record highs — the "
    "demand behind the take-or-pay backlog has stalled.\n"
    "3. LIQUIDITY IS THE FUEL: the bubble only bursts when liquidity dries up. Watch "
    "bank reserves (H.4.1), SOFR-IORB, TGA, SRF. A put-call inversion (calls richer "
    "than puts) with shrinking, drop-resistant spot = dealers forced to buy = the "
    "second-wave IGNITING (a melt-up/participate signal, NOT a sell).\n\n"
    "The framework's MECHANICAL SELL rules (these are pre-computed for you as "
    "'SELL-NOW trigger' tags and a SELL-NOW ACTIVE line — trust that state, do not "
    "invent your own): reserves rapidly breaking $2.5T = unconditionally liquidate; "
    "cloud-capex QoQ growth rolling over = liquidate immediately (the single most "
    "important top-escape signal); SOFR-IORB >3bps WITH reserves <$2.8T, or an SRF "
    "usage spike = structural top, clear positions; liquidity signals turning "
    "yellow AND capex rolling over together (resonance) = run, don't look back.\n\n"
    "OUTPUT: ONE tight paragraph (3-5 sentences, no bullet points, no headings, no "
    "preamble). Synthesize, don't list. Be specific and quantitative.\n"
    "- IF the data shows any SELL-NOW trigger ACTIVE (or SELL-NOW ACTIVE / confluence "
    "red or top): OPEN with the framework's directive plainly — that the rules say "
    "to SELL / liquidate now — name exactly which trigger fired and why, then the "
    "immediate implication. Be direct; do not soften or hedge the sell call.\n"
    "- IF nothing is triggered: stay analytical — lead with the overall state, the "
    "one or two most important readings (with numbers), note how close the nearest "
    "sell trigger is, and end with the single thing to watch next. Do NOT manufacture "
    "a sell call the data doesn't support.\n"
    "Weight the core signals (SOFR-IORB, reserves, TGA, SRF, cloud-capex QoQ rate, "
    "options skew) most; treat [context-only] indicators (e.g. ON RRP) as background "
    "only. If a 'Liquidity calendar' window is ACTIVE, briefly note the scheduled "
    "Treasury drain as a headwind that makes the reserve/TGA readings matter more — "
    "but it is context, not a trigger. No disclaimers."
)


def _summarize(snap: dict) -> str:
    """Compact, information-dense text description of the snapshot for the model."""
    lines = [f"Overall (confluence): {snap.get('overall_status', '?').upper()}"]
    conf = snap.get("confluence") or {}
    if conf.get("headline"):
        lines.append(f"Confluence read: {conf['headline']}")
    # which confluence conditions are met
    met = [c["label"] for grp in ("yellow", "red", "top") for c in conf.get(grp, []) if c.get("met")]
    lines.append("Confluence conditions currently MET: " + (", ".join(met) if met else "none"))

    if snap.get("sell_now"):
        reasons = "; ".join(f"{r['label']} ({r['action']})" for r in snap.get("sell_reasons", []))
        lines.append(f"SELL-NOW ACTIVE: {reasons}")

    lines.append("\nIndicators:")
    for m in snap.get("metrics", {}).values():
        ctx = " [context-only]" if m.get("context_only") else ""
        pct = f", {m['percentile']:.0f}th pctile" if m.get("percentile") is not None else ""
        sell = ""
        if m.get("sell_signal"):
            sell = f" [{'SELL-NOW' if m['sell_signal'].get('priority') == 'high' else 'sell-confirm'} trigger"
            sell += ", ACTIVE]" if m.get("sell_active") else "]"
        asof = f", latest {m['as_of_quarter']}" if m.get("as_of_quarter") else ""
        lines.append(
            f"- {m.get('label')}: {m.get('display_value')} "
            f"({m.get('status')}{pct}{asof}){ctx}{sell}"
        )

    tm = snap.get("top_model") or []
    if tm:
        trg = [t["label"] for t in tm if t.get("triggered")]
        lines.append(
            f"\nSecondary top-model: {snap.get('top_model_triggered')}/{snap.get('top_model_total')} "
            f"triggered ({', '.join(trg)})."
        )
    if snap.get("capex_updated"):
        lines.append("NOTE: a NEW cloud-capex quarter was filed today.")
    lc = snap.get("liquidity_calendar")
    if lc:
        when = (f"ACTIVE, peak ~{lc.get('peak')} ({lc.get('days_to_peak')}d away)"
                if lc.get("phase") == "active"
                else f"UPCOMING in {lc.get('days_to_start')}d")
        lines.append(f"\nLiquidity calendar ({when}): {lc.get('label')}. {lc.get('detail')}")
    return "\n".join(lines)


def generate_commentary(snap: dict, timeout: int = 45) -> str | None:
    """Return DeepSeek's one-paragraph daily note, or None on any failure."""
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        logger.info("DEEPSEEK_API_KEY not set — skipping AI commentary")
        return None

    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Today's readings:\n\n" + _summarize(snap)},
        ],
        "temperature": 0.4,
        "max_tokens": 320,
        "stream": False,
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
        text = data["choices"][0]["message"]["content"].strip()
        logger.info("DeepSeek commentary generated (%d chars)", len(text))
        return text
    except Exception as e:  # noqa: BLE001
        logger.error("DeepSeek commentary failed: %s", e)
        return None

#!/usr/bin/env python3
"""
generate_static_report.py

Reads configs/ai_moat_universe.yaml and produces a comprehensive markdown
report at reports/output/japan_chokepoint_framework_report.md.
"""

import yaml
from pathlib import Path
from datetime import date

# ── paths ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
YAML_PATH = ROOT / "configs" / "ai_moat_universe.yaml"
OUT_PATH  = ROOT / "reports" / "output" / "japan_chokepoint_framework_report.md"

REPORT_DATE = "February 10, 2026"

# ── helpers ────────────────────────────────────────────────────────────────

TIER_DEFINITIONS = {
    "tier_1": ("Tier 1 — True Monopoly / Near-Monopoly",
               ">80 % share, no viable alternative"),
    "tier_2": ("Tier 2 — Duopoly / Dominant Position",
               "50-80 % share, 1-2 alternatives"),
    "tier_3": ("Tier 3 — Oligopoly Leader",
               "30-50 % share, multiple competitors"),
}

THEME_LABELS = {
    "picks_and_shovels":    "Picks & Shovels",
    "hidden_monopolies":    "Hidden Monopolies",
    "packaging_bottleneck": "Packaging Bottleneck",
    "server_components":    "Server Components",
    "design_lock_in":       "Design Lock-In",
    "data_center_fabric":   "Data-Center Fabric",
    "ai_energy_grid":       "AI Energy Grid",
    "manufacturing_core":   "Manufacturing Core",
}

CATEGORY_TITLES = {
    "semiconductor_equipment":   "1. Semiconductor Equipment",
    "chemicals_materials":       "2. Specialty Chemicals & Materials",
    "packaging_substrates":      "3. Advanced Packaging & Substrates",
    "electronic_components":     "4. Electronic Components",
    "eda_design":                "5. EDA & Chip Design IP",
    "networking":                "6. Networking & Interconnect",
    "power_energy_infrastructure": "7. Power & Energy Infrastructure",
    "foundry_memory":            "8. Foundry & Memory",
}

# Sector mapping for the watchlist
CATEGORY_SECTOR = {
    "semiconductor_equipment":   "Semiconductor Equipment",
    "chemicals_materials":       "Specialty Chemicals",
    "packaging_substrates":      "Packaging / Substrates",
    "electronic_components":     "Electronic Components",
    "eda_design":                "EDA / Design IP",
    "networking":                "Networking",
    "power_energy_infrastructure": "Power Infrastructure",
    "foundry_memory":            "Foundry / Memory",
}


def composite_score(c: dict) -> float:
    dims = [
        c["market_dominance"],
        c["switching_costs"],
        c["technology_lockin"],
        c["supply_chain_criticality"],
        c["barriers_to_entry"],
    ]
    return round(sum(dims) / len(dims), 1)


def tier_label_short(tier: str) -> str:
    return tier.replace("_", " ").title().replace("Tier ", "T")


def build_report(data: dict) -> str:
    categories = data["categories"]
    lines: list[str] = []
    w = lines.append  # shorthand

    # ── Title block ────────────────────────────────────────────────────────
    w("# AI Infrastructure Investment Framework — Japanese Choke-Point Analysis")
    w("")
    w(f"**Date:** {REPORT_DATE}")
    w("")
    w("---")
    w("")

    # ── Executive summary ──────────────────────────────────────────────────
    w("## Executive Summary")
    w("")
    w("This report maps the **critical bottleneck positions** in the global AI")
    w("supply chain, with a special emphasis on Japanese companies that hold")
    w("near-monopoly or dominant positions in niche segments essential to AI")
    w("chip design, fabrication, packaging, and deployment. Each company is")
    w("scored on five moat dimensions (market dominance, switching costs,")
    w("technology lock-in, supply-chain criticality, and barriers to entry)")
    w("and assigned to one of three choke-point tiers.")
    w("")
    w("---")
    w("")

    # ── Choke-Point Tier Summary Table ─────────────────────────────────────
    w("## Choke-Point Tier Summary")
    w("")
    w("| Tier | Definition | Companies |")
    w("|------|-----------|-----------|")

    # Collect companies per tier
    tier_companies: dict[str, list[str]] = {"tier_1": [], "tier_2": [], "tier_3": []}
    for cat in categories.values():
        for c in cat["companies"]:
            tier_companies[c["choke_point_tier"]].append(c["name"])

    for tier_key in ("tier_1", "tier_2", "tier_3"):
        label, defn = TIER_DEFINITIONS[tier_key]
        names = ", ".join(sorted(tier_companies[tier_key]))
        w(f"| **{label}** | {defn} | {names} |")

    w("")
    w("---")
    w("")

    # ── Per-category sections ──────────────────────────────────────────────
    w("## Detailed Category Analysis")
    w("")

    for cat_key, cat in categories.items():
        title = CATEGORY_TITLES.get(cat_key, cat_key)
        theme_raw = cat.get("choke_point_theme", "")
        theme = THEME_LABELS.get(theme_raw, theme_raw)

        w(f"### {title}")
        w("")
        w(f"**Theme:** {theme}  ")
        w(f"**Description:** {cat['description']}")
        w("")
        w("| Company | Ticker (Local) | ADR / OTC | Country | Choke-Point Tier | Moat Description | AI Exposure % | Composite Moat Score |")
        w("|---------|---------------|-----------|---------|-----------------|------------------|--------------|---------------------|")

        sorted_cos = sorted(cat["companies"], key=lambda c: composite_score(c), reverse=True)
        for c in sorted_cos:
            adr = c.get("adr", "—")
            if not adr:
                adr = "—"
            tier_lbl = TIER_DEFINITIONS[c["choke_point_tier"]][0]
            cs = composite_score(c)
            moat_text = c["moat"].replace("|", "/")  # escape pipes
            w(f"| {c['name']} | `{c['ticker']}` | `{adr}` | {c['country']} | {tier_lbl} | {moat_text} | {c['ai_exposure_pct']}% | **{cs}** |")

        w("")
        w("---")
        w("")

    # ── USD-Accessible Japanese Moats ──────────────────────────────────────
    w("## USD-Accessible Japanese Moats")
    w("")
    w("Companies listed below are **Japanese-domiciled** and trade on US")
    w("exchanges via ADR or OTC tickers, enabling USD-denominated access to")
    w("these choke-point moats.")
    w("")
    w("| Rank | Company | Local Ticker | ADR / OTC Ticker | Choke-Point Tier | AI Exposure % | Composite Moat Score |")
    w("|------|---------|-------------|-----------------|-----------------|--------------|---------------------|")

    adr_list = []
    for cat in categories.values():
        for c in cat["companies"]:
            if c.get("adr") and c["country"] == "JP":
                adr_list.append(c)

    adr_list.sort(key=lambda c: composite_score(c), reverse=True)
    for rank, c in enumerate(adr_list, 1):
        tier_lbl = TIER_DEFINITIONS[c["choke_point_tier"]][0]
        cs = composite_score(c)
        w(f"| {rank} | {c['name']} | `{c['ticker']}` | `{c['adr']}` | {tier_lbl} | {c['ai_exposure_pct']}% | **{cs}** |")

    w("")
    w("---")
    w("")

    # ── Quick Reference Watchlist ──────────────────────────────────────────
    w("## Quick Reference Watchlist")
    w("")
    w("A compact reference of every company in the universe with a USD-")
    w("accessible ticker (ADR/OTC or direct US listing).")
    w("")
    w("| Company | Sector | USD Ticker (ADR) | Primary Moat |")
    w("|---------|--------|-----------------|-------------|")

    watchlist = []
    for cat_key, cat in categories.items():
        sector = CATEGORY_SECTOR.get(cat_key, cat_key)
        for c in cat["companies"]:
            usd_ticker = c.get("adr")
            # US-listed companies already trade in USD
            if not usd_ticker and c["country"] == "US":
                usd_ticker = c["ticker"]
            if not usd_ticker and c["country"] in ("NL", "GB", "IE"):
                usd_ticker = c["ticker"]  # Listed on US exchanges
            if usd_ticker:
                # Build a concise moat phrase
                moat_short = c["moat"].split(".")[0]  # first sentence
                watchlist.append((c["name"], sector, usd_ticker, moat_short, composite_score(c)))

    watchlist.sort(key=lambda x: x[4], reverse=True)
    for name, sector, ticker, moat_short, cs in watchlist:
        w(f"| {name} | {sector} | `{ticker}` | {moat_short} |")

    w("")
    w("---")
    w("")

    # ── Methodology ────────────────────────────────────────────────────────
    w("## Methodology & Scoring Notes")
    w("")
    w("Each company is rated on **five moat dimensions** (0-100 scale):")
    w("")
    w("| Dimension | What It Measures |")
    w("|-----------|-----------------|")
    w("| Market Dominance | Market share within the specific niche |")
    w("| Switching Costs | Difficulty for customers to replace the supplier |")
    w("| Technology Lock-In | Proprietary IP, trade secrets, know-how |")
    w("| Supply-Chain Criticality | Severity of the bottleneck if supplier is lost |")
    w("| Barriers to Entry | Capital, regulatory, and knowledge barriers for new entrants |")
    w("")
    w("**Composite Moat Score** = simple average of the five dimension scores.")
    w("")
    w("**AI Exposure %** is an estimate of the share of revenue directly tied")
    w("to AI workloads (training, inference, data-center build-out). Companies")
    w("with lower AI exposure may still be critical to the AI supply chain;")
    w("the percentage reflects revenue attribution, not strategic importance.")
    w("")
    w("---")
    w("")
    w("## Disclaimer")
    w("")
    w("This report is for **informational and educational purposes only**. It")
    w("does not constitute investment advice. Scores are qualitative estimates")
    w("and should be validated with independent research before making any")
    w("investment decisions.")
    w("")
    w(f"*Report generated on {REPORT_DATE}.*")
    w("")

    return "\n".join(lines)


# ── main ───────────────────────────────────────────────────────────────────
def main():
    with open(YAML_PATH, "r") as f:
        data = yaml.safe_load(f)

    report = build_report(data)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        f.write(report)

    print(f"Report written to {OUT_PATH}  ({len(report):,} characters)")


if __name__ == "__main__":
    main()

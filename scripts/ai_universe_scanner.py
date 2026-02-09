#!/usr/bin/env python3
"""AI Moat Universe Scanner - Scans all companies in the AI moat universe.

Produces a ranked overview of all companies with key metrics:
- Current price, market cap, P/E, margins
- Moat scores
- Price performance (1m, 3m, 6m, 1y)
- Revenue growth, earnings growth

Usage:
    python scripts/ai_universe_scanner.py
    python scripts/ai_universe_scanner.py --category semiconductor_equipment
    python scripts/ai_universe_scanner.py --top 20
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils.logger import setup_logger

logger = setup_logger("ai_scanner")

UNIVERSE_PATH = Path(__file__).resolve().parent.parent / "configs" / "ai_moat_universe.yaml"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "reports" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_universe(category_filter: str = "") -> list[dict]:
    """Load companies from the AI moat universe config."""
    with open(UNIVERSE_PATH) as f:
        data = yaml.safe_load(f)

    companies = []
    for cat_name, cat_items in data.get("categories", {}).items():
        if category_filter and cat_name != category_filter:
            continue
        desc = ""
        for item in cat_items if isinstance(cat_items, list) else []:
            pass
        # Handle the yaml structure - items are mixed with description
        if isinstance(cat_items, dict):
            desc = cat_items.get("description", "")
            items = [v for v in cat_items.values() if isinstance(v, dict) and "ticker" in v]
        elif isinstance(cat_items, list):
            items = [v for v in cat_items if isinstance(v, dict) and "ticker" in v]
        else:
            continue

        for item in items:
            item["category"] = cat_name
            companies.append(item)

    return companies


def parse_universe_yaml(category_filter: str = "") -> list[dict]:
    """More robust parser for the YAML universe file."""
    with open(UNIVERSE_PATH) as f:
        content = f.read()

    # Parse the yaml
    data = yaml.safe_load(content)
    companies = []

    for cat_name, cat_data in data.get("categories", {}).items():
        if category_filter and cat_name != category_filter:
            continue

        if not isinstance(cat_data, dict):
            continue

        desc = cat_data.get("description", cat_name)

        # Iterate through items that aren't 'description'
        for key, val in cat_data.items():
            if key == "description":
                continue
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict) and "ticker" in item:
                        item["category"] = cat_name
                        item["category_desc"] = desc
                        companies.append(item)
            elif isinstance(val, dict) and "ticker" in val:
                val["category"] = cat_name
                val["category_desc"] = desc
                companies.append(val)

    # If no companies found, try flat list parsing
    if not companies:
        for cat_name, cat_data in data.get("categories", {}).items():
            if category_filter and cat_name != category_filter:
                continue
            if isinstance(cat_data, list):
                for item in cat_data:
                    if isinstance(item, dict) and "ticker" in item:
                        item["category"] = cat_name
                        companies.append(item)

    return companies


def scan_company(comp: dict) -> dict:
    """Fetch live market data for a single company."""
    ticker = comp.get("adr") or comp["ticker"]
    name = comp.get("name", ticker)
    logger.info("Scanning %s (%s)", name, ticker)

    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="1y")

        if hist.empty:
            # Try the original ticker if ADR failed
            if comp.get("adr") and comp.get("adr") != comp["ticker"]:
                ticker = comp["ticker"]
                stock = yf.Ticker(ticker)
                info = stock.info
                hist = stock.history(period="1y")

        current = info.get("currentPrice") or info.get("regularMarketPrice")
        if current is None and not hist.empty:
            current = float(hist["Close"].iloc[-1])

        # Performance calculations
        perf = {}
        if not hist.empty and len(hist) > 0:
            current_p = hist["Close"].iloc[-1]
            if len(hist) >= 21:
                perf["1m"] = round((current_p / hist["Close"].iloc[-21] - 1) * 100, 1)
            if len(hist) >= 63:
                perf["3m"] = round((current_p / hist["Close"].iloc[-63] - 1) * 100, 1)
            if len(hist) >= 126:
                perf["6m"] = round((current_p / hist["Close"].iloc[-126] - 1) * 100, 1)
            if len(hist) >= 252:
                perf["1y"] = round((current_p / hist["Close"].iloc[0] - 1) * 100, 1)

        # Compute moat score from config values
        moat_dims = ["market_dominance", "switching_costs", "technology_lockin",
                      "supply_chain_criticality", "barriers_to_entry"]
        moat_weights = [0.20, 0.15, 0.15, 0.20, 0.15]
        moat_vals = [comp.get(d, 50) for d in moat_dims]
        # Add pricing_power estimate from margins
        pm = info.get("profitMargins")
        pricing_power = 50 + (min(pm * 100, 50) if pm else 0)
        moat_vals.append(pricing_power)
        moat_weights.append(0.15)
        moat_score = sum(v * w for v, w in zip(moat_vals, moat_weights))

        return {
            "ticker": comp["ticker"],
            "adr": comp.get("adr", ""),
            "name": name,
            "country": comp.get("country", ""),
            "category": comp.get("category", ""),
            "moat": comp.get("moat", ""),
            "ai_exposure_pct": comp.get("ai_exposure_pct", 0),
            "price": current,
            "market_cap_b": round(info.get("marketCap", 0) / 1e9, 1),
            "pe_trailing": info.get("trailingPE"),
            "pe_forward": info.get("forwardPE"),
            "profit_margin": round(info.get("profitMargins", 0) * 100, 1) if info.get("profitMargins") else None,
            "operating_margin": round(info.get("operatingMargins", 0) * 100, 1) if info.get("operatingMargins") else None,
            "roe": round(info.get("returnOnEquity", 0) * 100, 1) if info.get("returnOnEquity") else None,
            "revenue_growth": round(info.get("revenueGrowth", 0) * 100, 1) if info.get("revenueGrowth") else None,
            "earnings_growth": round(info.get("earningsGrowth", 0) * 100, 1) if info.get("earningsGrowth") else None,
            "dividend_yield": round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else None,
            "debt_to_equity": info.get("debtToEquity"),
            "perf_1m": perf.get("1m"),
            "perf_3m": perf.get("3m"),
            "perf_6m": perf.get("6m"),
            "perf_1y": perf.get("1y"),
            "moat_score": round(moat_score, 1),
            "currency": info.get("currency", ""),
        }
    except Exception as e:
        logger.error("Failed to scan %s: %s", name, e)
        return {
            "ticker": comp["ticker"],
            "name": name,
            "country": comp.get("country", ""),
            "category": comp.get("category", ""),
            "error": str(e),
        }


def generate_report(df: pd.DataFrame) -> str:
    """Generate markdown report from scan results."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# AI Production Moat Universe - Scan Report",
        f"*Generated: {timestamp}*",
        "",
        f"**Total Companies:** {len(df)} | **Categories:** {df['category'].nunique()}",
        "",
        "---",
        "",
    ]

    # Top 10 by moat score
    lines.append("## Top Companies by Moat Score")
    lines.append("")
    top = df.nlargest(15, "moat_score")[
        ["name", "ticker", "country", "moat_score", "ai_exposure_pct",
         "market_cap_b", "pe_forward", "revenue_growth", "perf_1y"]
    ]
    lines.append(top.to_markdown(index=False))
    lines.append("")

    # By category
    for cat in df["category"].unique():
        cat_df = df[df["category"] == cat].sort_values("moat_score", ascending=False)
        lines.append(f"## {cat.replace('_', ' ').title()}")
        lines.append("")
        cols = ["name", "ticker", "country", "moat_score", "price", "market_cap_b",
                "pe_forward", "profit_margin", "revenue_growth", "perf_3m", "perf_1y"]
        available = [c for c in cols if c in cat_df.columns]
        lines.append(cat_df[available].to_markdown(index=False))
        lines.append("")

    # Performance leaders
    if "perf_1y" in df.columns:
        lines.append("## Best 1-Year Performers")
        lines.append("")
        perf_df = df.dropna(subset=["perf_1y"]).nlargest(10, "perf_1y")
        lines.append(perf_df[["name", "ticker", "perf_1m", "perf_3m", "perf_6m", "perf_1y", "moat_score"]].to_markdown(index=False))
        lines.append("")

    # Value opportunities (low P/E + high moat)
    if "pe_forward" in df.columns:
        value = df.dropna(subset=["pe_forward"])
        value = value[(value["pe_forward"] > 0) & (value["pe_forward"] < 20) & (value["moat_score"] > 70)]
        if not value.empty:
            lines.append("## Value + Moat Opportunities (P/E < 20, Moat > 70)")
            lines.append("")
            lines.append(value[["name", "ticker", "pe_forward", "moat_score", "market_cap_b", "revenue_growth"]].to_markdown(index=False))
            lines.append("")

    lines.extend([
        "---",
        "*Disclaimer: Automated analysis for informational purposes only. Not financial advice.*",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Scan AI Moat Universe")
    parser.add_argument("--category", default="", help="Filter by category")
    parser.add_argument("--top", type=int, default=0, help="Show only top N by moat score")
    parser.add_argument("--output", default="", help="Output file path")
    args = parser.parse_args()

    print("Loading AI moat universe...")
    companies = parse_universe_yaml(args.category)
    print(f"Found {len(companies)} companies")

    if not companies:
        print("No companies found. Check configs/ai_moat_universe.yaml")
        return

    print("Scanning live market data...")
    results = []
    for i, comp in enumerate(companies, 1):
        print(f"  [{i}/{len(companies)}] {comp.get('name', comp['ticker'])}...")
        result = scan_company(comp)
        results.append(result)

    df = pd.DataFrame(results)

    # Filter errors
    if "error" in df.columns:
        errors = df[df["error"].notna()]
        if not errors.empty:
            print(f"\nWarning: {len(errors)} companies had errors:")
            for _, row in errors.iterrows():
                print(f"  - {row['name']}: {row.get('error', 'unknown')}")
        df = df[df.get("error", pd.Series(dtype=str)).isna() | ~df.columns.isin(["error"]).any()]

    if "moat_score" in df.columns:
        df = df.sort_values("moat_score", ascending=False)

    if args.top > 0:
        df = df.head(args.top)

    # Generate report
    report = generate_report(df)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = args.output or str(OUTPUT_DIR / f"ai_moat_scan_{timestamp}.md")
    Path(out_path).write_text(report)
    print(f"\nReport saved: {out_path}")

    # Save CSV
    csv_path = str(OUTPUT_DIR / f"ai_moat_scan_{timestamp}.csv")
    df.to_csv(csv_path, index=False)
    print(f"Data saved: {csv_path}")

    # Print summary
    print(f"\n{'='*70}")
    print("TOP 10 BY MOAT SCORE")
    print(f"{'='*70}")
    if "moat_score" in df.columns:
        summary = df.nlargest(10, "moat_score")[["name", "country", "moat_score", "market_cap_b", "pe_forward", "perf_1y"]]
        print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

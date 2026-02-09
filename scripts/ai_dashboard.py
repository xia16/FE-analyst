#!/usr/bin/env python3
"""AI Moat Portfolio Dashboard - Quick overview of your AI watchlist.

Shows a condensed dashboard of all AI moat companies with live data,
color-coded signals, and sortable output.

Usage:
    python scripts/ai_dashboard.py                    # Full universe
    python scripts/ai_dashboard.py --category semiconductor_equipment
    python scripts/ai_dashboard.py --sort perf_1y     # Sort by 1Y return
    python scripts/ai_dashboard.py --sort moat_score  # Sort by moat score
    python scripts/ai_dashboard.py --sort market_cap  # Sort by size
    python scripts/ai_dashboard.py --japan             # Japan only
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

logger = setup_logger("dashboard")

UNIVERSE_PATH = Path(__file__).resolve().parent.parent / "configs" / "ai_moat_universe.yaml"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "reports" / "output"


def load_companies(category: str = "", japan_only: bool = False) -> list[dict]:
    """Load from universe YAML."""
    with open(UNIVERSE_PATH) as f:
        data = yaml.safe_load(f)

    companies = []
    for cat_name, cat_data in data.get("categories", {}).items():
        if category and cat_name != category:
            continue
        if not isinstance(cat_data, dict):
            continue
        for item in cat_data.get("companies", []):
            if isinstance(item, dict) and "ticker" in item:
                if japan_only and item.get("country") != "JP":
                    continue
                item["category"] = cat_name
                companies.append(item)

    return companies


def quick_scan(comp: dict) -> dict | None:
    """Fast scan - just price, market cap, and performance."""
    ticker = comp.get("adr") or comp["ticker"]
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="6mo")
        info = stock.info

        if hist.empty:
            return None

        cur = hist["Close"].iloc[-1]
        perf_1m = round((cur / hist["Close"].iloc[-21] - 1) * 100, 1) if len(hist) >= 21 else None
        perf_3m = round((cur / hist["Close"].iloc[-63] - 1) * 100, 1) if len(hist) >= 63 else None

        # Moat score from config
        moat_dims = ["market_dominance", "switching_costs", "technology_lockin",
                     "supply_chain_criticality", "barriers_to_entry"]
        moat_weights = [0.20, 0.15, 0.15, 0.20, 0.15]
        moat_score = sum(comp.get(d, 50) * w for d, w in zip(moat_dims, moat_weights))
        # Approximate pricing power
        pm = info.get("profitMargins")
        moat_score += (50 + min((pm or 0) * 100, 50)) * 0.15

        return {
            "Name": comp.get("name", ticker)[:25],
            "Ticker": comp["ticker"],
            "Country": comp.get("country", ""),
            "Category": comp.get("category", "")[:15],
            "Price": round(cur, 2),
            "MCap $B": round(info.get("marketCap", 0) / 1e9, 1),
            "P/E": round(info.get("forwardPE", 0), 1) if info.get("forwardPE") else None,
            "Margin%": round((pm or 0) * 100, 1) if pm else None,
            "1M%": perf_1m,
            "3M%": perf_3m,
            "AI%": comp.get("ai_exposure_pct"),
            "Moat": round(moat_score, 0),
        }
    except Exception as e:
        logger.warning("Skip %s: %s", ticker, e)
        return None


def print_dashboard(df: pd.DataFrame, title: str = "AI Moat Dashboard"):
    """Print formatted dashboard to console."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"\n{'='*90}")
    print(f"  {title}")
    print(f"  {timestamp}")
    print(f"{'='*90}")
    print()

    # Color-code performance
    pd.set_option("display.max_columns", 15)
    pd.set_option("display.width", 120)
    pd.set_option("display.float_format", lambda x: f"{x:.1f}" if pd.notna(x) else "—")

    print(df.to_string(index=False))

    # Summary stats
    print(f"\n{'─'*90}")
    total_mcap = df["MCap $B"].sum()
    avg_pe = df["P/E"].dropna().mean()
    avg_moat = df["Moat"].dropna().mean()
    avg_1m = df["1M%"].dropna().mean()

    print(f"  Companies: {len(df)} | Total MCap: ${total_mcap:.0f}B | "
          f"Avg P/E: {avg_pe:.1f} | Avg Moat: {avg_moat:.0f} | "
          f"Avg 1M Return: {avg_1m:+.1f}%")

    # Top/bottom performers
    if "1M%" in df.columns and df["1M%"].notna().any():
        best = df.loc[df["1M%"].idxmax()]
        worst = df.loc[df["1M%"].idxmin()]
        print(f"  Best 1M:  {best['Name']} ({best['1M%']:+.1f}%)")
        print(f"  Worst 1M: {worst['Name']} ({worst['1M%']:+.1f}%)")

    print(f"{'='*90}\n")


def main():
    parser = argparse.ArgumentParser(description="AI Moat Dashboard")
    parser.add_argument("--category", default="", help="Filter by category")
    parser.add_argument("--japan", action="store_true", help="Japan companies only")
    parser.add_argument("--sort", default="Moat",
                        help="Sort column (Moat, MCap $B, P/E, 1M%%, 3M%%, AI%%)")
    parser.add_argument("--save", action="store_true", help="Save to CSV")
    args = parser.parse_args()

    companies = load_companies(category=args.category, japan_only=args.japan)
    print(f"Scanning {len(companies)} companies...")

    results = []
    for i, comp in enumerate(companies, 1):
        print(f"  [{i}/{len(companies)}] {comp.get('name', comp['ticker'])}...", end="\r")
        row = quick_scan(comp)
        if row:
            results.append(row)

    df = pd.DataFrame(results)

    # Sort
    sort_col = args.sort
    if sort_col in df.columns:
        df = df.sort_values(sort_col, ascending=False, na_position="last")
    elif sort_col.lower() == "moat":
        df = df.sort_values("Moat", ascending=False, na_position="last")

    title = "AI Moat Dashboard"
    if args.category:
        title += f" — {args.category.replace('_', ' ').title()}"
    if args.japan:
        title += " — Japan"

    print_dashboard(df, title)

    if args.save:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = OUTPUT_DIR / f"dashboard_{ts}.csv"
        df.to_csv(path, index=False)
        print(f"Saved: {path}")


if __name__ == "__main__":
    main()

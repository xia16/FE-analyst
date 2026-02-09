#!/usr/bin/env python3
"""AI Moat Company Comparisons - Side-by-side analysis of competing companies.

Run pre-built comparisons for key AI supply chain segments or custom groups.

Usage:
    python scripts/ai_comparisons.py euv              # EUV supply chain
    python scripts/ai_comparisons.py semicon_equip    # All semicon equipment
    python scripts/ai_comparisons.py wafers           # Silicon wafer makers
    python scripts/ai_comparisons.py packaging        # Advanced packaging
    python scripts/ai_comparisons.py eda              # EDA & design IP
    python scripts/ai_comparisons.py memory           # HBM/memory
    python scripts/ai_comparisons.py custom ASML TOELY LRCX AMAT KLAC
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_sources.market_data import MarketDataClient
from src.data_sources.fundamentals import FundamentalsClient
from src.analysis.risk import RiskAnalyzer
from src.utils.logger import setup_logger

logger = setup_logger("comparisons")

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "reports" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Pre-built comparison groups
COMPARISON_GROUPS = {
    "euv": {
        "title": "EUV Lithography Supply Chain",
        "tickers": ["ASML", "6920.T", "4063.T", "4185.T", "4186.T"],
        "labels": ["ASML (EUV machines)", "Lasertec (EUV inspection)", "Shin-Etsu (wafers+resist)",
                    "JSR (EUV resist)", "TOK (EUV resist)"],
    },
    "semicon_equip": {
        "title": "Semiconductor Equipment Leaders",
        "tickers": ["ASML", "AMAT", "LRCX", "KLAC", "8035.T", "6857.T", "6920.T", "6146.T"],
        "labels": ["ASML", "Applied Materials", "Lam Research", "KLA",
                    "Tokyo Electron", "Advantest", "Lasertec", "Disco"],
    },
    "wafers": {
        "title": "Silicon Wafer Manufacturers",
        "tickers": ["4063.T", "3436.T"],
        "labels": ["Shin-Etsu Chemical", "SUMCO"],
    },
    "packaging": {
        "title": "Advanced Packaging (CoWoS/HBM enablers)",
        "tickers": ["2801.T", "4062.T", "6967.T"],
        "labels": ["Ajinomoto (ABF film)", "Ibiden (substrates)", "Shinko Electric (substrates)"],
    },
    "eda": {
        "title": "EDA & Chip Design IP",
        "tickers": ["SNPS", "CDNS", "ARM"],
        "labels": ["Synopsys", "Cadence", "ARM Holdings"],
    },
    "memory": {
        "title": "AI Memory (HBM Players)",
        "tickers": ["MU", "000660.KS"],
        "labels": ["Micron", "SK Hynix"],
    },
    "networking": {
        "title": "AI Data Center Networking",
        "tickers": ["AVGO", "ANET", "APH"],
        "labels": ["Broadcom", "Arista Networks", "Amphenol"],
    },
    "japan_moats": {
        "title": "Japanese AI Moat Champions",
        "tickers": ["8035.T", "6920.T", "6857.T", "4063.T", "2801.T", "6981.T", "7741.T", "6146.T"],
        "labels": ["Tokyo Electron", "Lasertec", "Advantest", "Shin-Etsu",
                    "Ajinomoto", "Murata", "Hamamatsu", "Disco"],
    },
    "power_cooling": {
        "title": "AI Power & Cooling Infrastructure",
        "tickers": ["VRT", "MPWR", "6594.T"],
        "labels": ["Vertiv", "Monolithic Power", "Nidec"],
    },
}


def fetch_comparison_data(tickers: list[str], labels: list[str] | None = None) -> pd.DataFrame:
    """Fetch comprehensive comparison data for a list of tickers."""
    client = FundamentalsClient()
    market = MarketDataClient()
    risk_analyzer = RiskAnalyzer()

    rows = []
    for i, ticker in enumerate(tickers):
        label = labels[i] if labels and i < len(labels) else ticker
        print(f"  Fetching {label} ({ticker})...")

        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            ratios = client.get_key_ratios(ticker)

            # Price performance
            hist = stock.history(period="1y")
            perf = {}
            if not hist.empty:
                cur = hist["Close"].iloc[-1]
                if len(hist) >= 21:
                    perf["1m"] = round((cur / hist["Close"].iloc[-21] - 1) * 100, 1)
                if len(hist) >= 63:
                    perf["3m"] = round((cur / hist["Close"].iloc[-63] - 1) * 100, 1)
                if len(hist) >= 126:
                    perf["6m"] = round((cur / hist["Close"].iloc[-126] - 1) * 100, 1)
                if len(hist) >= 252:
                    perf["1y"] = round((cur / hist["Close"].iloc[0] - 1) * 100, 1)

            # Risk metrics
            try:
                risk = risk_analyzer.analyze(ticker)
            except Exception:
                risk = {}

            rows.append({
                "Company": label,
                "Ticker": ticker,
                "Price": info.get("currentPrice") or info.get("regularMarketPrice"),
                "Currency": info.get("currency", ""),
                "Mkt Cap ($B)": round(info.get("marketCap", 0) / 1e9, 1),
                "P/E (Fwd)": _rnd(ratios.get("pe_forward")),
                "P/E (Trail)": _rnd(ratios.get("pe_trailing")),
                "PEG": _rnd(ratios.get("peg_ratio")),
                "P/B": _rnd(ratios.get("pb_ratio")),
                "EV/EBITDA": _rnd(ratios.get("ev_ebitda")),
                "P/S": _rnd(ratios.get("ps_ratio")),
                "Gross Margin %": _pct(ratios.get("profit_margin")),
                "Op Margin %": _pct(ratios.get("operating_margin")),
                "ROE %": _pct(ratios.get("roe")),
                "ROA %": _pct(ratios.get("roa")),
                "Rev Growth %": _pct(ratios.get("revenue_growth")),
                "Earn Growth %": _pct(ratios.get("earnings_growth")),
                "D/E": _rnd(ratios.get("debt_to_equity")),
                "Current Ratio": _rnd(ratios.get("current_ratio")),
                "Div Yield %": _pct(ratios.get("dividend_yield")),
                "Perf 1M %": perf.get("1m"),
                "Perf 3M %": perf.get("3m"),
                "Perf 6M %": perf.get("6m"),
                "Perf 1Y %": perf.get("1y"),
                "Volatility": risk.get("volatility"),
                "Beta": risk.get("beta"),
                "Sharpe": risk.get("sharpe_ratio"),
                "Max DD %": round(risk.get("max_drawdown", 0) * 100, 1) if risk.get("max_drawdown") else None,
            })
        except Exception as e:
            logger.error("Failed %s: %s", ticker, e)
            rows.append({"Company": label, "Ticker": ticker, "Error": str(e)})

    return pd.DataFrame(rows)


def generate_comparison_report(title: str, df: pd.DataFrame) -> str:
    """Generate a markdown comparison report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# {title}",
        f"*Comparative Analysis — {timestamp}*",
        "",
        "---",
        "",
    ]

    # Valuation comparison
    val_cols = ["Company", "Ticker", "Mkt Cap ($B)", "P/E (Fwd)", "P/E (Trail)",
                "PEG", "P/B", "EV/EBITDA", "P/S"]
    available = [c for c in val_cols if c in df.columns]
    lines.extend([
        "## Valuation",
        "",
        df[available].to_markdown(index=False),
        "",
    ])

    # Profitability comparison
    prof_cols = ["Company", "Gross Margin %", "Op Margin %", "ROE %", "ROA %"]
    available = [c for c in prof_cols if c in df.columns]
    lines.extend([
        "## Profitability",
        "",
        df[available].to_markdown(index=False),
        "",
    ])

    # Growth comparison
    growth_cols = ["Company", "Rev Growth %", "Earn Growth %", "Mkt Cap ($B)"]
    available = [c for c in growth_cols if c in df.columns]
    lines.extend([
        "## Growth",
        "",
        df[available].to_markdown(index=False),
        "",
    ])

    # Performance
    perf_cols = ["Company", "Perf 1M %", "Perf 3M %", "Perf 6M %", "Perf 1Y %"]
    available = [c for c in perf_cols if c in df.columns]
    lines.extend([
        "## Price Performance",
        "",
        df[available].to_markdown(index=False),
        "",
    ])

    # Risk
    risk_cols = ["Company", "Volatility", "Beta", "Sharpe", "Max DD %"]
    available = [c for c in risk_cols if c in df.columns]
    lines.extend([
        "## Risk Profile",
        "",
        df[available].to_markdown(index=False),
        "",
    ])

    # Financial Health
    health_cols = ["Company", "D/E", "Current Ratio", "Div Yield %"]
    available = [c for c in health_cols if c in df.columns]
    lines.extend([
        "## Financial Health",
        "",
        df[available].to_markdown(index=False),
        "",
    ])

    # Rankings
    lines.extend([
        "## Rankings Summary",
        "",
    ])

    # Ensure numeric columns for ranking
    numeric_cols = ["P/E (Fwd)", "Op Margin %", "Rev Growth %", "Perf 1Y %", "Sharpe"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    rankings = []
    if "P/E (Fwd)" in df.columns:
        valid = df[df["P/E (Fwd)"].notna() & (df["P/E (Fwd)"] > 0)]
        if not valid.empty:
            cheapest = valid.nsmallest(1, "P/E (Fwd)")
            rankings.append(f"- **Cheapest (Fwd P/E):** {cheapest.iloc[0]['Company']} ({cheapest.iloc[0]['P/E (Fwd)']})")
    if "Op Margin %" in df.columns:
        valid = df[df["Op Margin %"].notna()]
        if not valid.empty:
            most_profitable = valid.nlargest(1, "Op Margin %")
            rankings.append(f"- **Most Profitable (Op Margin):** {most_profitable.iloc[0]['Company']} ({most_profitable.iloc[0]['Op Margin %']}%)")
    if "Rev Growth %" in df.columns:
        valid = df[df["Rev Growth %"].notna()]
        if not valid.empty:
            fastest = valid.nlargest(1, "Rev Growth %")
            rankings.append(f"- **Fastest Growing:** {fastest.iloc[0]['Company']} ({fastest.iloc[0]['Rev Growth %']}%)")
    if "Perf 1Y %" in df.columns:
        valid = df[df["Perf 1Y %"].notna()]
        if not valid.empty:
            best_perf = valid.nlargest(1, "Perf 1Y %")
            rankings.append(f"- **Best 1Y Performance:** {best_perf.iloc[0]['Company']} ({best_perf.iloc[0]['Perf 1Y %']}%)")
    if "Sharpe" in df.columns:
        valid = df[df["Sharpe"].notna()]
        if not valid.empty:
            best_ra = valid.nlargest(1, "Sharpe")
            rankings.append(f"- **Best Risk-Adjusted (Sharpe):** {best_ra.iloc[0]['Company']} ({best_ra.iloc[0]['Sharpe']})")

    lines.extend(rankings)
    lines.extend([
        "",
        "---",
        "*Disclaimer: Automated analysis for informational purposes only. Not financial advice.*",
    ])

    return "\n".join(lines)


def _rnd(val, decimals=2):
    if val is None:
        return None
    return round(val, decimals)

def _pct(val):
    if val is None:
        return None
    return round(val * 100, 1)


def main():
    parser = argparse.ArgumentParser(description="AI Moat Company Comparisons")
    parser.add_argument("group", help="Comparison group or 'custom'")
    parser.add_argument("tickers", nargs="*", help="Tickers (when group='custom')")
    parser.add_argument("--output", default="", help="Output file path")
    args = parser.parse_args()

    if args.group == "custom":
        if not args.tickers:
            print("Usage: python scripts/ai_comparisons.py custom TICK1 TICK2 ...")
            sys.exit(1)
        title = f"Custom Comparison: {', '.join(args.tickers)}"
        tickers = args.tickers
        labels = None
    elif args.group in COMPARISON_GROUPS:
        group = COMPARISON_GROUPS[args.group]
        title = group["title"]
        tickers = group["tickers"]
        labels = group.get("labels")
    elif args.group == "list":
        print("Available comparison groups:")
        for k, v in COMPARISON_GROUPS.items():
            print(f"  {k:20s} - {v['title']} ({len(v['tickers'])} companies)")
        sys.exit(0)
    else:
        print(f"Unknown group: {args.group}")
        print(f"Available: {', '.join(COMPARISON_GROUPS.keys())}, custom, list")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

    df = fetch_comparison_data(tickers, labels)
    report = generate_comparison_report(title, df)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = args.group.replace(" ", "_")
    out_path = args.output or str(OUTPUT_DIR / f"comparison_{slug}_{timestamp}.md")
    Path(out_path).write_text(report)
    print(f"\nReport saved: {out_path}")

    csv_path = str(OUTPUT_DIR / f"comparison_{slug}_{timestamp}.csv")
    df.to_csv(csv_path, index=False)
    print(f"Data saved: {csv_path}")

    print("\n" + report)


if __name__ == "__main__":
    main()

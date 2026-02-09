#!/usr/bin/env python3
"""AI Company Deep Dive - Full financial analyst report on a single company.

Produces a detailed investment memo covering:
- Company overview & moat analysis
- Financial statements (income, balance sheet, cash flow)
- Key ratios & peer comparison
- Technical analysis & price action
- Valuation (DCF + comparables)
- Risk assessment
- News sentiment
- Investment thesis (bull/bear/base cases)

Usage:
    python scripts/ai_deep_dive.py 8035.T              # Tokyo Electron
    python scripts/ai_deep_dive.py ASML                 # ASML
    python scripts/ai_deep_dive.py TOELY --peers ASML LRCX AMAT KLAC
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_sources.market_data import MarketDataClient
from src.data_sources.fundamentals import FundamentalsClient
from src.data_sources.news_sentiment import NewsSentimentClient
from src.data_sources.macro_data import MacroDataClient
from src.analysis.technical import TechnicalAnalyzer
from src.analysis.risk import RiskAnalyzer
from src.analysis.valuation import ValuationAnalyzer
from src.utils.logger import setup_logger

logger = setup_logger("deep_dive")

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "reports" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_profile(ticker: str) -> dict:
    """Fetch comprehensive company profile."""
    stock = yf.Ticker(ticker)
    info = stock.info
    return {
        "name": info.get("longName") or info.get("shortName", ticker),
        "ticker": ticker,
        "sector": info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
        "country": info.get("country", "N/A"),
        "market_cap": info.get("marketCap", 0),
        "market_cap_b": round(info.get("marketCap", 0) / 1e9, 2),
        "employees": info.get("fullTimeEmployees"),
        "website": info.get("website", ""),
        "description": info.get("longBusinessSummary", ""),
        "currency": info.get("currency", "USD"),
        "exchange": info.get("exchange", ""),
    }


def get_financials_summary(ticker: str) -> dict:
    """Pull and summarize financial statements."""
    client = FundamentalsClient()

    income = client.get_income_statement(ticker)
    balance = client.get_balance_sheet(ticker)
    cashflow = client.get_cash_flow(ticker)

    result = {"income": {}, "balance": {}, "cashflow": {}}

    # Income statement highlights
    if not income.empty:
        for metric in ["Total Revenue", "Gross Profit", "Operating Income",
                       "Net Income", "EBITDA", "Basic EPS"]:
            if metric in income.index:
                row = income.loc[metric]
                result["income"][metric] = {
                    str(col.date() if hasattr(col, 'date') else col): _fmt_num(val)
                    for col, val in row.items()
                }

        # Compute margins
        if "Total Revenue" in income.index and "Gross Profit" in income.index:
            rev = income.loc["Total Revenue"]
            gp = income.loc["Gross Profit"]
            result["income"]["Gross Margin %"] = {
                str(col.date() if hasattr(col, 'date') else col): f"{(gp[col]/rev[col]*100):.1f}%"
                for col in rev.index if rev[col] and rev[col] != 0
            }
        if "Total Revenue" in income.index and "Operating Income" in income.index:
            rev = income.loc["Total Revenue"]
            oi = income.loc["Operating Income"]
            result["income"]["Operating Margin %"] = {
                str(col.date() if hasattr(col, 'date') else col): f"{(oi[col]/rev[col]*100):.1f}%"
                for col in rev.index if rev[col] and rev[col] != 0
            }
        if "Total Revenue" in income.index and "Net Income" in income.index:
            rev = income.loc["Total Revenue"]
            ni = income.loc["Net Income"]
            result["income"]["Net Margin %"] = {
                str(col.date() if hasattr(col, 'date') else col): f"{(ni[col]/rev[col]*100):.1f}%"
                for col in rev.index if rev[col] and rev[col] != 0
            }

    # Balance sheet highlights
    if not balance.empty:
        for metric in ["Total Assets", "Total Liabilities Net Minority Interest",
                       "Stockholders Equity", "Total Debt", "Cash And Cash Equivalents"]:
            if metric in balance.index:
                row = balance.loc[metric]
                result["balance"][metric] = {
                    str(col.date() if hasattr(col, 'date') else col): _fmt_num(val)
                    for col, val in row.items()
                }

    # Cash flow highlights
    if not cashflow.empty:
        for metric in ["Operating Cash Flow", "Capital Expenditure", "Free Cash Flow"]:
            if metric in cashflow.index:
                row = cashflow.loc[metric]
                result["cashflow"][metric] = {
                    str(col.date() if hasattr(col, 'date') else col): _fmt_num(val)
                    for col, val in row.items()
                }

    return result


def get_ratios_table(ticker: str) -> dict:
    """Get comprehensive ratio analysis."""
    client = FundamentalsClient()
    return client.get_key_ratios(ticker)


def get_peer_comparison(ticker: str, peers: list[str]) -> pd.DataFrame:
    """Compare key metrics against peers."""
    client = FundamentalsClient()
    all_tickers = [ticker] + peers

    rows = []
    for t in all_tickers:
        try:
            ratios = client.get_key_ratios(t)
            info = yf.Ticker(t).info
            rows.append({
                "Ticker": t,
                "Name": info.get("shortName", t),
                "Mkt Cap ($B)": round(info.get("marketCap", 0) / 1e9, 1),
                "P/E (Fwd)": ratios.get("pe_forward"),
                "P/B": ratios.get("pb_ratio"),
                "EV/EBITDA": ratios.get("ev_ebitda"),
                "Gross Margin": f"{ratios.get('profit_margin', 0)*100:.1f}%" if ratios.get("profit_margin") else None,
                "Op Margin": f"{ratios.get('operating_margin', 0)*100:.1f}%" if ratios.get("operating_margin") else None,
                "ROE": f"{ratios.get('roe', 0)*100:.1f}%" if ratios.get("roe") else None,
                "Rev Growth": f"{ratios.get('revenue_growth', 0)*100:.1f}%" if ratios.get("revenue_growth") else None,
                "D/E": ratios.get("debt_to_equity"),
                "Div Yield": f"{ratios.get('dividend_yield', 0)*100:.2f}%" if ratios.get("dividend_yield") else None,
            })
        except Exception as e:
            logger.warning("Peer %s failed: %s", t, e)

    return pd.DataFrame(rows)


def generate_deep_dive_report(
    ticker: str, peers: list[str] | None = None
) -> str:
    """Generate the full deep dive report as markdown."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"  [1/7] Company profile...")
    profile = get_profile(ticker)

    print(f"  [2/7] Financial statements...")
    financials = get_financials_summary(ticker)

    print(f"  [3/7] Key ratios...")
    ratios = get_ratios_table(ticker)

    print(f"  [4/7] Technical analysis...")
    market = MarketDataClient()
    tech = TechnicalAnalyzer()
    price_df = market.get_price_history(ticker, period="1y")
    signals = tech.get_signals(price_df) if not price_df.empty else {}
    support_res = tech.get_support_resistance(price_df) if not price_df.empty else {}

    print(f"  [5/7] Risk analysis...")
    risk_analyzer = RiskAnalyzer()
    risk = risk_analyzer.analyze(ticker)

    print(f"  [6/7] Valuation...")
    val_analyzer = ValuationAnalyzer()
    try:
        dcf = val_analyzer.dcf_valuation(ticker)
    except Exception as e:
        dcf = {"error": str(e)}

    print(f"  [7/7] Peer comparison...")
    if peers:
        peer_df = get_peer_comparison(ticker, peers)
    else:
        peer_df = pd.DataFrame()

    # ===== BUILD REPORT =====
    lines = []

    # Header
    lines.extend([
        f"# Investment Deep Dive: {profile['name']} ({ticker})",
        f"*Financial Analyst Report — {timestamp}*",
        "",
        "---",
        "",
    ])

    # Executive Summary
    lines.extend([
        "## 1. Executive Summary",
        "",
        f"| | |",
        f"|---|---|",
        f"| **Company** | {profile['name']} |",
        f"| **Ticker** | {ticker} |",
        f"| **Sector** | {profile['sector']} |",
        f"| **Industry** | {profile['industry']} |",
        f"| **Country** | {profile['country']} |",
        f"| **Market Cap** | ${profile['market_cap_b']}B |",
        f"| **Employees** | {profile.get('employees', 'N/A'):,} |" if profile.get('employees') else f"| **Employees** | N/A |",
        f"| **Currency** | {profile['currency']} |",
        "",
    ])

    if profile.get("description"):
        desc = profile["description"][:500]
        lines.extend([f"> {desc}", ""])

    # Key Ratios
    lines.extend([
        "## 2. Key Financial Ratios",
        "",
        "| Metric | Value |",
        "|--------|-------|",
    ])
    ratio_display = {
        "pe_trailing": "P/E (Trailing)",
        "pe_forward": "P/E (Forward)",
        "peg_ratio": "PEG Ratio",
        "pb_ratio": "P/B Ratio",
        "ps_ratio": "P/S Ratio",
        "ev_ebitda": "EV/EBITDA",
        "profit_margin": "Profit Margin",
        "operating_margin": "Operating Margin",
        "roe": "Return on Equity",
        "roa": "Return on Assets",
        "debt_to_equity": "Debt/Equity",
        "current_ratio": "Current Ratio",
        "dividend_yield": "Dividend Yield",
        "revenue_growth": "Revenue Growth",
        "earnings_growth": "Earnings Growth",
    }
    for key, label in ratio_display.items():
        val = ratios.get(key)
        if val is not None:
            if "margin" in key or "growth" in key or key in ["roe", "roa", "dividend_yield"]:
                lines.append(f"| {label} | {val*100:.1f}% |")
            else:
                lines.append(f"| {label} | {val:.2f} |")
    lines.append("")

    # Financial Statements
    lines.extend([
        "## 3. Financial Statements (Annual)",
        "",
    ])

    for section_name, section_key in [
        ("Income Statement", "income"),
        ("Balance Sheet", "balance"),
        ("Cash Flow Statement", "cashflow"),
    ]:
        section = financials.get(section_key, {})
        if section:
            lines.append(f"### {section_name}")
            lines.append("")

            # Get all years
            all_years = set()
            for metric_data in section.values():
                all_years.update(metric_data.keys())
            years = sorted(all_years, reverse=True)[:4]

            header = "| Metric | " + " | ".join(years) + " |"
            sep = "|--------|" + "|".join(["-------"] * len(years)) + "|"
            lines.append(header)
            lines.append(sep)

            for metric, data in section.items():
                row = f"| {metric} | "
                row += " | ".join(str(data.get(y, "—")) for y in years)
                row += " |"
                lines.append(row)
            lines.append("")

    # Technical Analysis
    lines.extend([
        "## 4. Technical Analysis",
        "",
    ])
    if signals:
        lines.extend([
            "### Signals",
            "",
            "| Indicator | Signal | Detail |",
            "|-----------|--------|--------|",
        ])
        for name, sig in signals.items():
            lines.append(
                f"| {name.upper()} | **{sig.get('signal', 'N/A')}** | {sig.get('reason', '')} |"
            )
        lines.append("")

    if support_res:
        lines.extend([
            "### Support & Resistance",
            "",
            f"- **Current Price:** {support_res.get('current', 'N/A'):.2f}",
            f"- **Support:** {support_res.get('support', 'N/A'):.2f}",
            f"- **Resistance:** {support_res.get('resistance', 'N/A'):.2f}",
            "",
        ])

    # Risk Profile
    lines.extend([
        "## 5. Risk Assessment",
        "",
    ])
    if "error" not in risk:
        lines.extend([
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| **Risk Level** | {risk.get('risk_level', 'N/A')} |",
            f"| Annualized Volatility | {risk.get('volatility', 'N/A')} |",
            f"| Beta (vs SPY) | {risk.get('beta', 'N/A')} |",
            f"| Sharpe Ratio | {risk.get('sharpe_ratio', 'N/A')} |",
            f"| Sortino Ratio | {risk.get('sortino_ratio', 'N/A')} |",
            f"| Max Drawdown | {risk.get('max_drawdown', 'N/A')} |",
            f"| Value at Risk (95%) | {risk.get('var_95', 'N/A')} |",
            f"| Conditional VaR (95%) | {risk.get('cvar_95', 'N/A')} |",
            "",
        ])

    # Valuation
    lines.extend([
        "## 6. Valuation",
        "",
    ])
    if "error" not in dcf:
        lines.extend([
            "### DCF Analysis",
            "",
            f"| Parameter | Value |",
            f"|-----------|-------|",
            f"| Current FCF | {_fmt_num(dcf.get('current_fcf', 0))} |",
            f"| Growth Rate | {dcf.get('growth_rate', 0)*100:.1f}% |",
            f"| Terminal Growth | {dcf.get('terminal_growth', 0)*100:.1f}% |",
            f"| Discount Rate (WACC) | {dcf.get('discount_rate', 0)*100:.1f}% |",
            f"| **Intrinsic Value/Share** | **${dcf.get('intrinsic_per_share', 0):.2f}** |",
            f"| Current Price | ${dcf.get('current_price', 0):.2f} |",
            f"| Margin of Safety | {dcf.get('margin_of_safety_pct', 0):.1f}% |",
            f"| **Verdict** | **{dcf.get('verdict', 'N/A')}** |",
            "",
        ])
    else:
        lines.extend([f"DCF not available: {dcf.get('error', 'unknown')}", ""])

    # Peer Comparison
    if not peer_df.empty:
        lines.extend([
            "## 7. Peer Comparison",
            "",
            peer_df.to_markdown(index=False),
            "",
        ])

    # Disclaimer
    lines.extend([
        "---",
        "",
        "*Disclaimer: This is an automated analysis for informational purposes only. "
        "It does not constitute financial advice. Always conduct your own research "
        "and consult with qualified financial professionals before making investment decisions.*",
    ])

    return "\n".join(lines)


def _fmt_num(val) -> str:
    """Format large numbers for readability."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "—"
    try:
        val = float(val)
    except (TypeError, ValueError):
        return str(val)

    if abs(val) >= 1e12:
        return f"${val/1e12:.1f}T"
    elif abs(val) >= 1e9:
        return f"${val/1e9:.1f}B"
    elif abs(val) >= 1e6:
        return f"${val/1e6:.1f}M"
    elif abs(val) >= 1e3:
        return f"${val/1e3:.1f}K"
    else:
        return f"${val:.2f}"


def main():
    parser = argparse.ArgumentParser(description="AI Company Deep Dive Analysis")
    parser.add_argument("ticker", help="Stock ticker symbol")
    parser.add_argument("--peers", nargs="*", default=None,
                        help="Peer tickers for comparison")
    parser.add_argument("--output", default="", help="Output file path")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  DEEP DIVE: {args.ticker}")
    print(f"{'='*60}\n")

    report = generate_deep_dive_report(args.ticker, peers=args.peers)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = args.output or str(OUTPUT_DIR / f"deep_dive_{args.ticker}_{timestamp}.md")
    Path(out_path).write_text(report)
    print(f"\nReport saved: {out_path}")

    # Print to console too
    print("\n" + report)


if __name__ == "__main__":
    main()

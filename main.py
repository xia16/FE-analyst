#!/usr/bin/env python3
"""FE-Analyst: Stock & Company Analysis Platform.

Usage:
    python main.py analyze AAPL
    python main.py compare AAPL MSFT GOOGL
    python main.py screen value
    python main.py quote AAPL
"""

import argparse
import json
import sys

from src.config import SETTINGS
from src.utils.logger import setup_logger

logger = setup_logger("main", SETTINGS.get("app", {}).get("log_level", "INFO"))


def cmd_analyze(args):
    """Run full analysis on a single stock."""
    from src.reports.generator import ReportGenerator

    gen = ReportGenerator()
    report = gen.full_report(args.ticker)
    print(report)


def cmd_compare(args):
    """Compare multiple stocks side by side."""
    from src.reports.generator import ReportGenerator

    gen = ReportGenerator()
    report = gen.compare_report(args.tickers)
    print(report)


def cmd_screen(args):
    """Run a pre-built stock screen."""
    from src.data_sources.screener import StockScreener

    screener = StockScreener()
    screen_map = {
        "value": screener.value_stocks,
        "growth": screener.growth_stocks,
        "momentum": screener.momentum_stocks,
        "dividend": screener.dividend_stocks,
    }
    func = screen_map.get(args.strategy)
    if func is None:
        print(f"Unknown strategy: {args.strategy}")
        print(f"Available: {', '.join(screen_map.keys())}")
        sys.exit(1)

    df = func()
    print(df.to_string())


def cmd_quote(args):
    """Get real-time quote for a ticker."""
    from src.data_sources.market_data import MarketDataClient

    client = MarketDataClient()
    quote = client.get_quote(args.ticker)
    print(json.dumps(quote, indent=2))


def cmd_fundamentals(args):
    """Print key fundamentals for a ticker."""
    from src.data_sources.fundamentals import FundamentalsClient

    client = FundamentalsClient()
    ratios = client.get_key_ratios(args.ticker)
    profile = client.get_company_profile(args.ticker)
    print(f"\n{'='*50}")
    print(f"  {profile.get('name', args.ticker)} ({args.ticker})")
    print(f"  {profile.get('sector', '')} / {profile.get('industry', '')}")
    print(f"{'='*50}")
    for k, v in ratios.items():
        if k != "ticker" and v is not None:
            print(f"  {k:25s}: {v}")


def cmd_risk(args):
    """Risk analysis for a ticker."""
    from src.analysis.risk import RiskAnalyzer

    analyzer = RiskAnalyzer()
    result = analyzer.analyze(args.ticker)
    print(json.dumps(result, indent=2, default=str))


def cmd_macro(args):
    """Show current economic indicators."""
    from src.data_sources.macro_data import MacroDataClient

    client = MacroDataClient()
    indicators = client.get_economic_indicators()
    yields_ = client.get_treasury_yields()

    print("\n--- Economic Indicators ---")
    for k, v in indicators.items():
        print(f"  {k:20s}: {v}")

    print("\n--- Treasury Yields ---")
    for k, v in yields_.items():
        print(f"  {k:20s}: {v}%")


def main():
    parser = argparse.ArgumentParser(
        description="FE-Analyst: Stock & Company Analysis Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # analyze
    p = subparsers.add_parser("analyze", help="Full analysis report for a stock")
    p.add_argument("ticker", help="Stock ticker symbol")
    p.set_defaults(func=cmd_analyze)

    # compare
    p = subparsers.add_parser("compare", help="Compare multiple stocks")
    p.add_argument("tickers", nargs="+", help="Stock ticker symbols")
    p.set_defaults(func=cmd_compare)

    # screen
    p = subparsers.add_parser("screen", help="Run stock screener")
    p.add_argument("strategy", choices=["value", "growth", "momentum", "dividend"])
    p.set_defaults(func=cmd_screen)

    # quote
    p = subparsers.add_parser("quote", help="Get real-time quote")
    p.add_argument("ticker", help="Stock ticker symbol")
    p.set_defaults(func=cmd_quote)

    # fundamentals
    p = subparsers.add_parser("fundamentals", help="Show key fundamentals")
    p.add_argument("ticker", help="Stock ticker symbol")
    p.set_defaults(func=cmd_fundamentals)

    # risk
    p = subparsers.add_parser("risk", help="Risk analysis")
    p.add_argument("ticker", help="Stock ticker symbol")
    p.set_defaults(func=cmd_risk)

    # macro
    p = subparsers.add_parser("macro", help="Economic indicators snapshot")
    p.set_defaults(func=cmd_macro)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()

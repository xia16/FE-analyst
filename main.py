#!/usr/bin/env python3
"""FE-Analyst: Stock & Company Analysis Platform.

Usage:
    python main.py analyze TSMC                          # full analysis
    python main.py analyze ASML --profile quick          # quick scan
    python main.py analyze "Tokyo Electron" --profile deep_dive
    python main.py compare ASML LRCX AMAT KLAC           # side-by-side
    python main.py scan --watchlist japan_champions       # scan a watchlist
    python main.py scan --category semiconductor_equipment
    python main.py screen value                           # finviz screener
    python main.py quote AAPL                             # real-time quote
    python main.py fundamentals AAPL                      # key ratios
    python main.py risk AAPL                              # risk metrics
    python main.py macro                                  # economic dashboard
"""

import argparse
import json
import sys

import yaml

from src.config import SETTINGS, PROJECT_ROOT
from src.resolver import TickerResolver
from src.pipeline.context import PipelineContext
from src.pipeline.engine import PipelineEngine
from src.pipeline import steps as S
from src.pipeline.registry import get_registry
from src.utils.logger import setup_logger

logger = setup_logger("main", SETTINGS.get("app", {}).get("log_level", "INFO"))


def _load_profiles() -> dict:
    path = PROJECT_ROOT / "configs" / "profiles.yaml"
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _load_watchlists() -> dict:
    path = PROJECT_ROOT / "configs" / "watchlists.yaml"
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


PROFILES = _load_profiles()
WATCHLISTS = _load_watchlists()
resolver = TickerResolver()


def _build_steps(profile_config: dict):
    """Convert profile config into step functions + template name."""
    step_map = {
        "fetch_price_data": S.fetch_price_data,
        "fetch_fundamentals": S.fetch_fundamentals,
        "fetch_news": S.fetch_news,
    }
    step_funcs = []
    for name in profile_config.get("steps", []):
        func = step_map.get(name)
        if func:
            step_funcs.append(func)

    analyzers = profile_config.get("analyzers", "all")
    if analyzers == "all":
        step_funcs.append(S.run_registered_analyzers)
    else:
        step_funcs.append(S.run_specific_analyzers(analyzers))

    step_funcs.append(S.compute_scores)
    template = profile_config.get("template", "deep_dive.md.j2")
    return step_funcs, template


def _load_universe_meta(tickers: list[str]) -> dict[str, dict]:
    """Load moat metadata for tickers from universe YAML."""
    path = PROJECT_ROOT / "configs" / "ai_moat_universe.yaml"
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f)

    meta = {}
    ticker_set = set(tickers) | set(t.upper() for t in tickers)

    for cat_data in (data or {}).get("categories", {}).values():
        if not isinstance(cat_data, dict):
            continue
        for item in cat_data.get("companies", []):
            if isinstance(item, dict) and "ticker" in item:
                t = item["ticker"]
                adr = item.get("adr", "")
                if t in ticker_set or (adr and adr in ticker_set):
                    meta[adr or t] = item
    return meta


# ============================================================
# COMMANDS
# ============================================================

def cmd_analyze(args):
    """Run analysis pipeline on ticker(s)."""
    tickers = resolver.resolve_many(args.tickers)
    profile_name = args.profile
    profile_config = PROFILES.get(profile_name)
    if not profile_config:
        print(f"Unknown profile: {profile_name}")
        print(f"Available: {', '.join(PROFILES.keys())}")
        sys.exit(1)

    step_funcs, template = _build_steps(profile_config)
    ctx = PipelineContext(
        tickers=tickers,
        profile_name=profile_name,
        company_meta=_load_universe_meta(tickers),
    )

    engine = PipelineEngine()
    report_path = engine.run(ctx, step_funcs, template=template)
    print(f"\nReport saved: {report_path}")
    print(report_path.read_text())


def cmd_compare(args):
    """Run comparison pipeline."""
    tickers = resolver.resolve_many(args.tickers)
    profile_config = PROFILES.get("comparison", PROFILES.get("quick", {}))
    step_funcs, template = _build_steps(profile_config)

    ctx = PipelineContext(
        tickers=tickers,
        profile_name="comparison",
        company_meta=_load_universe_meta(tickers),
    )
    engine = PipelineEngine()
    report_path = engine.run(ctx, step_funcs, template="comparison.md.j2")
    print(f"\nReport saved: {report_path}")
    print(report_path.read_text())


def cmd_scan(args):
    """Scan a watchlist or universe category."""
    if args.watchlist:
        tickers = WATCHLISTS.get(args.watchlist, [])
        if not tickers:
            print(f"Unknown watchlist: {args.watchlist}")
            print(f"Available: {', '.join(WATCHLISTS.keys())}")
            sys.exit(1)
    elif args.category:
        path = PROJECT_ROOT / "configs" / "ai_moat_universe.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        tickers = []
        cat_data = data.get("categories", {}).get(args.category, {})
        if isinstance(cat_data, dict):
            for item in cat_data.get("companies", []):
                if isinstance(item, dict) and "ticker" in item:
                    tickers.append(item.get("adr") or item["ticker"])
        if not tickers:
            print(f"No companies in category: {args.category}")
            sys.exit(1)
    else:
        tickers = WATCHLISTS.get("default", [])

    tickers = resolver.resolve_many(tickers)
    profile_config = PROFILES.get("screening", PROFILES.get("quick", {}))
    step_funcs, _ = _build_steps(profile_config)

    ctx = PipelineContext(
        tickers=tickers,
        profile_name="screening",
        company_meta=_load_universe_meta(tickers),
    )
    engine = PipelineEngine()
    report_path = engine.run(ctx, step_funcs, template="screening.md.j2")
    print(f"\nReport saved: {report_path}")
    print(report_path.read_text())


def cmd_screen(args):
    """Run finviz stock screener."""
    from src.data_sources.screener import StockScreener
    screener = StockScreener()
    func = getattr(screener, f"{args.strategy}_stocks", None)
    if func:
        print(func().to_string())


def cmd_quote(args):
    """Get real-time quote."""
    from src.data_sources.market_data import MarketDataClient
    ticker = resolver.resolve(args.ticker)
    client = MarketDataClient()
    print(json.dumps(client.get_quote(ticker), indent=2))


def cmd_fundamentals(args):
    """Show key fundamentals."""
    from src.data_sources.fundamentals import FundamentalsClient
    ticker = resolver.resolve(args.ticker)
    client = FundamentalsClient()
    ratios = client.get_key_ratios(ticker)
    profile = client.get_company_profile(ticker)
    print(f"\n{'='*50}")
    print(f"  {profile.get('name', ticker)} ({ticker})")
    print(f"  {profile.get('sector', '')} / {profile.get('industry', '')}")
    print(f"{'='*50}")
    for k, v in ratios.items():
        if k != "ticker" and v is not None:
            print(f"  {k:25s}: {v}")


def cmd_risk(args):
    """Risk analysis."""
    from src.analysis.risk import RiskAnalyzer
    ticker = resolver.resolve(args.ticker)
    analyzer = RiskAnalyzer()
    print(json.dumps(analyzer.analyze(ticker), indent=2, default=str))


def cmd_macro(args):
    """Economic indicators."""
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
    sub = parser.add_subparsers(dest="command", help="Commands")

    # analyze
    p = sub.add_parser("analyze", help="Run analysis pipeline")
    p.add_argument("tickers", nargs="+", help="Tickers or company names")
    p.add_argument("--profile", default="full", choices=list(PROFILES.keys()),
                    help="Run profile (default: full)")
    p.set_defaults(func=cmd_analyze)

    # compare
    p = sub.add_parser("compare", help="Compare multiple stocks")
    p.add_argument("tickers", nargs="+")
    p.set_defaults(func=cmd_compare)

    # scan
    p = sub.add_parser("scan", help="Scan watchlist or category")
    p.add_argument("--watchlist", default="", help="Watchlist name")
    p.add_argument("--category", default="", help="Universe category")
    p.set_defaults(func=cmd_scan)

    # screen
    p = sub.add_parser("screen", help="Stock screener")
    p.add_argument("strategy", choices=["value", "growth", "momentum", "dividend"])
    p.set_defaults(func=cmd_screen)

    # quote
    p = sub.add_parser("quote", help="Real-time quote")
    p.add_argument("ticker")
    p.set_defaults(func=cmd_quote)

    # fundamentals
    p = sub.add_parser("fundamentals", help="Key fundamentals")
    p.add_argument("ticker")
    p.set_defaults(func=cmd_fundamentals)

    # risk
    p = sub.add_parser("risk", help="Risk analysis")
    p.add_argument("ticker")
    p.set_defaults(func=cmd_risk)

    # macro
    p = sub.add_parser("macro", help="Economic indicators")
    p.set_defaults(func=cmd_macro)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(0)
    args.func(args)


if __name__ == "__main__":
    main()

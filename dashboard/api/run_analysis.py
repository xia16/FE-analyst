"""Thin runner that executes stock analysis and prints JSON to stdout.

Called by the dashboard API server as a subprocess using the main project venv.
Usage: python run_analysis.py TICKER
"""

import sys
import json
import math
import logging
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Patch yfinance BEFORE importing any analysis modules —
# gives all engines retry-on-429 and a shared .info cache.
from src.utils.yf_session import patch_yfinance
patch_yfinance()

# Force ALL loggers to stderr AFTER imports so we catch module-level handlers
from src.analysis.scoring import StockScorer
from src.data_sources.insider_congress import InsiderCongressClient

# Redirect every handler on every logger to stderr
for name in list(logging.Logger.manager.loggerDict) + [None]:
    logger = logging.getLogger(name)
    for handler in logger.handlers:
        if hasattr(handler, 'stream'):
            handler.stream = sys.stderr
# Also patch root
for handler in logging.root.handlers:
    if hasattr(handler, 'stream'):
        handler.stream = sys.stderr


def _sanitize(obj):
    """Replace NaN/Infinity with None for valid JSON."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


def analyze(ticker: str) -> dict:
    """Run all analysis engines and return composite result."""
    # Composite scoring (fundamental, valuation, technical, sentiment, risk)
    scorer = StockScorer()
    result = scorer.score(ticker)

    # Moat analysis (try to import, graceful fallback)
    try:
        from src.analysis.moat import MoatAnalyzer
        moat = MoatAnalyzer()
        moat_result = moat.score_moat(ticker)
        result["moat"] = moat_result
    except Exception as e:
        result["moat"] = {"error": str(e)}

    # Insider + Congressional trading data
    try:
        insider = InsiderCongressClient()
        result["insider_congress"] = insider.get_insider_summary(ticker)
    except Exception as e:
        result["insider_congress"] = {"error": str(e), "signal": "NEUTRAL"}

    # Company profile
    try:
        from src.data_sources.fundamentals import FundamentalsClient
        fund = FundamentalsClient()
        result["profile"] = fund.get_company_profile(ticker)
        result["ratios"] = fund.get_key_ratios(ticker)
    except Exception as e:
        result["profile"] = {"error": str(e)}
        result["ratios"] = {}

    # --- Phase 1E: New analysis modules ---

    # International analysis (ADR premium/discount, FX sensitivity)
    try:
        from src.analysis.international import InternationalAnalyzer
        intl = InternationalAnalyzer()
        result["international"] = intl.analyze(ticker)
    except Exception as e:
        result["international"] = {"error": str(e)}

    # Earnings estimates (calendar, revisions, history)
    try:
        from src.data_sources.earnings_estimates import EarningsEstimatesClient
        earnings = EarningsEstimatesClient()
        result["earnings_estimates"] = {
            "calendar": earnings.get_earnings_calendar(ticker),
            "revisions": earnings.get_estimate_revisions(ticker),
            "history": earnings.get_earnings_history(ticker),
        }
    except Exception as e:
        result["earnings_estimates"] = {"error": str(e)}

    # Short interest data
    try:
        from src.data_sources.short_interest import ShortInterestClient
        short = ShortInterestClient()
        result["short_interest"] = short.get_short_interest(ticker)
    except Exception as e:
        result["short_interest"] = {"error": str(e)}

    # Whale / institutional tracking
    try:
        from src.data_sources.whale_tracking import WhaleTrackingClient
        whale = WhaleTrackingClient()
        result["whale_tracking"] = {
            "holders": whale.get_institutional_holders(ticker),
            "sentiment": whale.get_fund_sentiment(ticker),
        }
    except Exception as e:
        result["whale_tracking"] = {"error": str(e)}

    # Catalyst calendar
    try:
        from src.data_sources.catalyst_calendar import CatalystCalendarClient
        catalyst = CatalystCalendarClient()
        result["catalysts"] = catalyst.get_catalysts(ticker)
    except Exception as e:
        result["catalysts"] = {"error": str(e)}

    # SEC filings (8-K events, 10-K risk factors, risk factor changes)
    try:
        from src.data_sources.sec_filings import SECFilingsClient
        sec = SECFilingsClient()
        result["sec_analysis"] = sec.analyze(ticker)
    except Exception as e:
        result["sec_analysis"] = {"error": str(e)}

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: python run_analysis.py TICKER"}))
        sys.exit(1)

    ticker = sys.argv[1].upper()
    try:
        result = analyze(ticker)
        print(json.dumps(_sanitize(result), default=str))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

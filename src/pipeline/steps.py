"""Built-in pipeline steps: fetch, analyze, score.

Each step is a function: (PipelineContext) -> None
"""

from __future__ import annotations

from src.pipeline.context import PipelineContext
from src.pipeline.registry import get_registry
from src.data_sources.market_data import MarketDataClient
from src.data_sources.fundamentals import FundamentalsClient
from src.data_sources.news_sentiment import NewsSentimentClient
from src.utils.logger import setup_logger

logger = setup_logger("steps")


# ============================================================
# FETCH STEPS
# ============================================================

def fetch_price_data(ctx: PipelineContext) -> None:
    """Fetch OHLCV price history for all tickers."""
    client = MarketDataClient()
    for ticker in ctx.tickers:
        logger.info("Fetching price data: %s", ticker)
        ctx.price_data[ticker] = client.get_price_history(ticker, period="1y")


def fetch_fundamentals(ctx: PipelineContext) -> None:
    """Fetch key ratios, profile, and financial statements."""
    client = FundamentalsClient()
    for ticker in ctx.tickers:
        logger.info("Fetching fundamentals: %s", ticker)
        ctx.fundamentals_data[ticker] = {
            "ratios": client.get_key_ratios(ticker),
            "profile": client.get_company_profile(ticker),
        }
        ctx.financials_data[ticker] = {
            "income": client.get_income_statement(ticker),
            "balance": client.get_balance_sheet(ticker),
            "cashflow": client.get_cash_flow(ticker),
        }


def fetch_news(ctx: PipelineContext) -> None:
    """Fetch news + sentiment for all tickers."""
    client = NewsSentimentClient()
    for ticker in ctx.tickers:
        logger.info("Fetching news: %s", ticker)
        ctx.news_data[ticker] = client.get_news_with_sentiment(ticker)


# ============================================================
# ANALYZE STEPS
# ============================================================

def run_registered_analyzers(ctx: PipelineContext) -> None:
    """Run every analyzer registered in the AnalyzerRegistry."""
    registry = get_registry()
    for ticker in ctx.tickers:
        for name, analyzer in registry.items():
            logger.info("Analyzing %s with %s", ticker, name)
            try:
                result = analyzer.analyze(ticker, ctx)
                ctx.set_analysis(ticker, name, result)
            except Exception as e:
                logger.error("%s failed for %s: %s", name, ticker, e)
                ctx.set_analysis(ticker, name, {"error": str(e), "score": None})


def run_specific_analyzers(analyzer_names: list[str]):
    """Factory: returns a step that runs only the named analyzers."""
    def _step(ctx: PipelineContext) -> None:
        registry = get_registry()
        for ticker in ctx.tickers:
            for name in analyzer_names:
                analyzer = registry.get(name)
                if analyzer is None:
                    logger.warning("Analyzer not found: %s", name)
                    continue
                try:
                    result = analyzer.analyze(ticker, ctx)
                    ctx.set_analysis(ticker, name, result)
                except Exception as e:
                    logger.error("%s failed for %s: %s", name, ticker, e)
                    ctx.set_analysis(ticker, name, {"error": str(e), "score": None})
    _step.__name__ = f"analyze_{'_'.join(analyzer_names)}"
    return _step


# ============================================================
# SCORE STEP
# ============================================================

def compute_scores(ctx: PipelineContext) -> None:
    """Compute composite investment scores from analysis results."""
    registry = get_registry()
    weights = registry.get_weights()

    for ticker in ctx.tickers:
        analyses = ctx.analysis_results.get(ticker, {})
        component_scores = {}

        for name, result in analyses.items():
            if isinstance(result, dict) and "score" in result and result["score"] is not None:
                component_scores[name] = result["score"]
            # Skip engines with None/missing scores instead of defaulting to 50

        available_weight = sum(weights.get(k, 0.1) for k in component_scores)
        if available_weight > 0:
            composite = sum(
                component_scores[k] * weights.get(k, 0.1) / available_weight
                for k in component_scores
            )
        else:
            composite = 50.0

        # Minimum coverage threshold — refuse recommendation if <50% weight succeeded
        insufficient_data = available_weight < 0.50

        if insufficient_data:
            rec = "INSUFFICIENT DATA"
        elif composite >= 75:
            rec = "STRONG BUY"
        elif composite >= 60:
            rec = "BUY"
        elif composite >= 45:
            rec = "HOLD"
        elif composite >= 30:
            rec = "SELL"
        else:
            rec = "STRONG SELL"

        ctx.scores[ticker] = {
            "composite_score": round(composite, 1),
            "recommendation": rec,
            "component_scores": {k: round(v, 1) for k, v in component_scores.items()},
            "weights": weights,
            "weight_coverage_pct": round(available_weight * 100, 1),
        }

"""LLM-powered sentiment analysis aggregator.

Gathers raw data from news, Reddit, analyst recommendations, and insider
trades, then passes everything to Claude for holistic sentiment analysis.
"""

from src.data_sources.news_sentiment import NewsSentimentClient
from src.data_sources.alternative_data import AlternativeDataClient
from src.data_sources.llm_sentiment import LLMSentimentClient
from src.utils.logger import setup_logger

logger = setup_logger("sentiment_analysis")


class SentimentAnalyzer:
    """Gather multi-source data and analyze sentiment via LLM."""

    def __init__(self):
        self.news_client = NewsSentimentClient()
        self.alt_client = AlternativeDataClient()
        self.llm_client = LLMSentimentClient()

    def analyze(self, ticker: str) -> dict:
        """Gather all data sources and run LLM sentiment analysis."""
        logger.info("Gathering sentiment data for %s", ticker)

        # 1. Fetch news headlines
        news = self.news_client.get_company_news(ticker)
        logger.info("  News articles: %d", len(news))

        # 2. Fetch Reddit posts
        reddit_posts = []
        try:
            reddit_posts = self.alt_client.get_reddit_sentiment(ticker)
        except Exception as e:
            logger.warning("  Reddit fetch failed: %s", e)
        logger.info("  Reddit posts: %d", len(reddit_posts))

        # 3. Fetch analyst recommendations
        analyst_recs = []
        try:
            recs_df = self.alt_client.get_analyst_recommendations(ticker)
            if recs_df is not None and not recs_df.empty:
                analyst_recs = recs_df.iloc[:10].to_dict("records")
        except Exception as e:
            logger.warning("  Analyst recs fetch failed: %s", e)
        logger.info("  Analyst recommendations: %d", len(analyst_recs))

        # 4. Fetch insider trades
        insider_trades = []
        try:
            insider_trades = self.alt_client.get_insider_trades(ticker)
        except Exception as e:
            logger.warning("  Insider trades fetch failed: %s", e)
        logger.info("  Insider trades: %d", len(insider_trades))

        # 5. Send everything to LLM for analysis
        result = self.llm_client.analyze(
            ticker=ticker,
            news=news,
            reddit_posts=reddit_posts,
            analyst_recs=analyst_recs,
            insider_trades=insider_trades,
        )

        # Attach raw source counts for transparency
        result["source_counts"] = {
            "news_articles": len(news),
            "reddit_posts": len(reddit_posts),
            "analyst_recommendations": len(analyst_recs),
            "insider_trades": len(insider_trades),
        }

        return result


# --- Plugin adapter for pipeline ---
from src.analysis.base import BaseAnalyzer as _BaseAnalyzer


class SentimentAnalyzerPlugin(_BaseAnalyzer):
    name = "sentiment"
    default_weight = 0.10

    def __init__(self):
        self._analyzer = SentimentAnalyzer()

    def analyze(self, ticker, ctx):
        result = self._analyzer.analyze(ticker)
        # Convert -1..1 score to 0-100 scale for composite scoring
        overall = result.get("overall_score", 0)
        score = max(0, min(100, 50 + overall * 100))
        result["score"] = round(score, 1)
        return result

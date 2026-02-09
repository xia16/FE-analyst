"""News and sentiment data client.

Primary: Finnhub news | Sentiment: FinBERT (local model)
"""

import pandas as pd

from src.config import Keys
from src.utils.cache import DataCache
from src.utils.logger import setup_logger

logger = setup_logger("news_sentiment")
cache = DataCache("news")


class NewsSentimentClient:
    """Fetch financial news and compute sentiment scores."""

    def get_company_news(
        self, ticker: str, date_from: str = "", date_to: str = ""
    ) -> list[dict]:
        """Get recent news for a company via Finnhub."""
        if not Keys.FINNHUB:
            logger.warning("No Finnhub API key configured")
            return []

        import finnhub
        from datetime import datetime, timedelta

        if not date_from:
            date_from = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        if not date_to:
            date_to = datetime.now().strftime("%Y-%m-%d")

        client = finnhub.Client(api_key=Keys.FINNHUB)
        news = client.company_news(ticker, _from=date_from, to=date_to)

        return [
            {
                "headline": item.get("headline"),
                "summary": item.get("summary"),
                "source": item.get("source"),
                "url": item.get("url"),
                "datetime": item.get("datetime"),
                "category": item.get("category"),
            }
            for item in news
        ]

    def get_market_news(self, category: str = "general") -> list[dict]:
        """Get general market news."""
        if not Keys.FINNHUB:
            return []

        import finnhub

        client = finnhub.Client(api_key=Keys.FINNHUB)
        return client.general_news(category, min_id=0)

    def analyze_sentiment(self, texts: list[str]) -> list[dict]:
        """Run FinBERT sentiment analysis on a list of texts.

        Returns list of {text, label, score} where label is
        positive/negative/neutral.
        """
        from transformers import pipeline

        logger.info("Running FinBERT on %d texts", len(texts))
        classifier = pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert",
            truncation=True,
            max_length=512,
        )

        results = classifier(texts)
        return [
            {"text": text[:100], "label": r["label"], "score": round(r["score"], 4)}
            for text, r in zip(texts, results)
        ]

    def get_news_with_sentiment(self, ticker: str) -> pd.DataFrame:
        """Fetch news and attach sentiment scores."""
        news = self.get_company_news(ticker)
        if not news:
            return pd.DataFrame()

        headlines = [n["headline"] for n in news if n.get("headline")]
        sentiments = self.analyze_sentiment(headlines)

        df = pd.DataFrame(news)
        if sentiments:
            sent_df = pd.DataFrame(sentiments)
            df["sentiment_label"] = sent_df["label"].values[: len(df)]
            df["sentiment_score"] = sent_df["score"].values[: len(df)]
        return df

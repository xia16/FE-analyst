"""Sentiment analysis aggregator."""

import pandas as pd

from src.data_sources.news_sentiment import NewsSentimentClient
from src.data_sources.alternative_data import AlternativeDataClient
from src.utils.logger import setup_logger

logger = setup_logger("sentiment_analysis")


class SentimentAnalyzer:
    """Aggregate sentiment from multiple sources."""

    def __init__(self):
        self.news_client = NewsSentimentClient()
        self.alt_client = AlternativeDataClient()

    def analyze(self, ticker: str) -> dict:
        """Get aggregate sentiment score from all sources."""
        results = {"ticker": ticker, "sources": {}}

        # News sentiment
        news_df = self.news_client.get_news_with_sentiment(ticker)
        if not news_df.empty and "sentiment_label" in news_df.columns:
            counts = news_df["sentiment_label"].value_counts().to_dict()
            total = len(news_df)
            results["sources"]["news"] = {
                "positive_pct": round(counts.get("positive", 0) / total * 100, 1),
                "negative_pct": round(counts.get("negative", 0) / total * 100, 1),
                "neutral_pct": round(counts.get("neutral", 0) / total * 100, 1),
                "article_count": total,
            }

        # Reddit sentiment
        reddit_posts = self.alt_client.get_reddit_sentiment(ticker)
        if reddit_posts:
            avg_score = sum(p["score"] for p in reddit_posts) / len(reddit_posts)
            avg_ratio = sum(p["upvote_ratio"] for p in reddit_posts) / len(reddit_posts)
            results["sources"]["reddit"] = {
                "post_count": len(reddit_posts),
                "avg_score": round(avg_score, 1),
                "avg_upvote_ratio": round(avg_ratio, 3),
            }

        # Analyst recommendations
        recs = self.alt_client.get_analyst_recommendations(ticker)
        if recs is not None and not recs.empty:
            latest = recs.iloc[:5]
            results["sources"]["analysts"] = latest.to_dict("records")

        # Compute overall score (-1 to 1)
        scores = []
        if "news" in results["sources"]:
            ns = results["sources"]["news"]
            scores.append((ns["positive_pct"] - ns["negative_pct"]) / 100)
        if "reddit" in results["sources"]:
            rs = results["sources"]["reddit"]
            scores.append(rs["avg_upvote_ratio"] - 0.5)  # normalize around 0

        if scores:
            results["overall_score"] = round(sum(scores) / len(scores), 3)
            if results["overall_score"] > 0.2:
                results["overall_label"] = "BULLISH"
            elif results["overall_score"] < -0.2:
                results["overall_label"] = "BEARISH"
            else:
                results["overall_label"] = "NEUTRAL"
        else:
            results["overall_score"] = 0
            results["overall_label"] = "NO DATA"

        return results

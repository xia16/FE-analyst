"""Alternative data client - Reddit sentiment, insider trading, etc."""

import pandas as pd

from src.config import Keys
from src.utils.logger import setup_logger

logger = setup_logger("alt_data")


class AlternativeDataClient:
    """Fetch alternative / non-traditional data sources."""

    def get_reddit_sentiment(
        self, ticker: str, subreddit: str = "wallstreetbets", limit: int = 50
    ) -> list[dict]:
        """Scrape Reddit posts mentioning a ticker."""
        if not Keys.REDDIT_CLIENT_ID:
            logger.warning("No Reddit API credentials configured")
            return []

        import praw

        reddit = praw.Reddit(
            client_id=Keys.REDDIT_CLIENT_ID,
            client_secret=Keys.REDDIT_CLIENT_SECRET,
            user_agent=Keys.REDDIT_USER_AGENT,
        )

        logger.info("Searching r/%s for %s", subreddit, ticker)
        sub = reddit.subreddit(subreddit)
        posts = []
        for post in sub.search(ticker, limit=limit, sort="new"):
            posts.append({
                "title": post.title,
                "score": post.score,
                "num_comments": post.num_comments,
                "created_utc": post.created_utc,
                "upvote_ratio": post.upvote_ratio,
                "url": post.url,
            })
        return posts

    def get_insider_trades(self, ticker: str) -> list[dict]:
        """Get insider trading data via Finnhub."""
        if not Keys.FINNHUB:
            logger.warning("No Finnhub key for insider trades")
            return []

        import finnhub

        client = finnhub.Client(api_key=Keys.FINNHUB)
        data = client.stock_insider_transactions(ticker)
        return data.get("data", [])

    def get_institutional_ownership(self, ticker: str) -> pd.DataFrame:
        """Get institutional holders from yfinance."""
        import yfinance as yf

        stock = yf.Ticker(ticker)
        return stock.institutional_holders

    def get_analyst_recommendations(self, ticker: str) -> pd.DataFrame:
        """Get analyst recommendations."""
        import yfinance as yf

        stock = yf.Ticker(ticker)
        return stock.recommendations

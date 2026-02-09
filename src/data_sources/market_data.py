"""Market data client - prices, volume, OHLCV data.

Primary: yfinance | Fallback: finnhub, alpaca
"""

import pandas as pd
import yfinance as yf

from src.config import Keys
from src.utils.cache import DataCache
from src.utils.logger import setup_logger

logger = setup_logger("market_data")
cache = DataCache("price_historical")


class MarketDataClient:
    """Fetch historical and current market data."""

    def get_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        """Get OHLCV price history for a ticker.

        Args:
            ticker: Stock symbol (e.g. "AAPL")
            period: Data period - 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,max
            interval: Data interval - 1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo
        """
        cache_key = f"{ticker}_{period}_{interval}"
        cached = cache.get_df(cache_key)
        if cached is not None:
            logger.info("Cache hit: %s", cache_key)
            return cached

        logger.info("Fetching price history: %s (period=%s)", ticker, period)
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)

        if not df.empty:
            cache.set_df(cache_key, df)
        return df

    def get_current_price(self, ticker: str) -> dict:
        """Get the latest price and basic info."""
        stock = yf.Ticker(ticker)
        info = stock.fast_info
        return {
            "ticker": ticker,
            "price": info.last_price,
            "market_cap": info.market_cap,
            "currency": info.currency,
        }

    def get_multiple(self, tickers: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
        """Fetch price history for multiple tickers."""
        results = {}
        for t in tickers:
            results[t] = self.get_price_history(t, period=period)
        return results

    def get_quote(self, ticker: str) -> dict:
        """Get real-time quote via finnhub (if key available)."""
        if not Keys.FINNHUB:
            logger.warning("No Finnhub key, falling back to yfinance")
            return self.get_current_price(ticker)

        import finnhub

        client = finnhub.Client(api_key=Keys.FINNHUB)
        quote = client.quote(ticker)
        return {
            "ticker": ticker,
            "current": quote["c"],
            "high": quote["h"],
            "low": quote["l"],
            "open": quote["o"],
            "prev_close": quote["pc"],
            "change": quote["d"],
            "change_pct": quote["dp"],
        }

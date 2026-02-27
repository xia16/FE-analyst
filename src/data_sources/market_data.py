"""Market data client - prices, volume, OHLCV data.

Primary: yfinance | Fallback: TwelveData REST API
"""

import pandas as pd
import requests as req_lib
import yfinance as yf

from src.config import Keys
from src.utils.cache import DataCache
from src.utils.logger import setup_logger

logger = setup_logger("market_data")
cache = DataCache("price_historical")

# TwelveData period → approximate calendar days for outputsize
_PERIOD_TO_DAYS = {
    "1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180,
    "1y": 365, "2y": 730, "5y": 1825, "10y": 3650, "max": 5000,
}


def _fetch_twelvedata_history(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Fetch OHLCV from TwelveData REST API (fallback when yfinance is rate-limited).

    TwelveData free tier: 800 calls/day, 8 calls/min.
    Returns DataFrame with yfinance-compatible column names (Open, High, Low, Close, Volume).
    """
    api_key = Keys.TWELVE_DATA
    if not api_key:
        logger.debug("No TwelveData API key, skipping fallback")
        return pd.DataFrame()

    # Map yfinance interval to TwelveData format
    interval_map = {"1d": "1day", "1wk": "1week", "1mo": "1month"}
    td_interval = interval_map.get(interval, "1day")

    days = _PERIOD_TO_DAYS.get(period, 365)
    outputsize = min(days, 5000)

    try:
        logger.info("TwelveData fallback: %s (period=%s, outputsize=%d)", ticker, period, outputsize)
        resp = req_lib.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": ticker,
                "interval": td_interval,
                "outputsize": outputsize,
                "apikey": api_key,
                "format": "JSON",
            },
            timeout=30,
        )
        data = resp.json()

        if data.get("status") == "error":
            logger.warning("TwelveData error for %s: %s", ticker, data.get("message", "unknown"))
            return pd.DataFrame()

        values = data.get("values", [])
        if not values:
            return pd.DataFrame()

        df = pd.DataFrame(values)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime").sort_index()

        # Rename to match yfinance column names
        df = df.rename(columns={
            "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "volume": "Volume",
        })
        for col in ["Open", "High", "Low", "Close"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "Volume" in df.columns:
            df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0).astype(int)

        logger.info("TwelveData: got %d rows for %s", len(df), ticker)
        return df

    except Exception as e:
        logger.warning("TwelveData fetch failed for %s: %s", ticker, e)
        return pd.DataFrame()


class MarketDataClient:
    """Fetch historical and current market data."""

    def get_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        """Get OHLCV price history for a ticker.

        Tries yfinance first, falls back to TwelveData if yfinance returns
        empty data (usually due to Yahoo Finance rate limiting / 429 errors).

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

        # Primary: yfinance
        logger.info("Fetching price history: %s (period=%s)", ticker, period)
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval=interval)
        except Exception as e:
            logger.warning("yfinance history failed for %s: %s", ticker, e)
            df = pd.DataFrame()

        # Fallback: TwelveData (if yfinance returned empty/failed)
        if df.empty:
            df = _fetch_twelvedata_history(ticker, period, interval)

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

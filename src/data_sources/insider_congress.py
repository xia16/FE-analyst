"""Insider trading + Congressional trading data aggregator.

Sources:
1. House Stock Watcher (free S3 JSON, no API key)
2. Senate Stock Watcher (free S3 JSON, no API key)
3. Finnhub insider transactions (existing FINNHUB key)
"""

import json
import time
import urllib.request
from datetime import datetime, timedelta

from src.config import Keys
from src.utils.logger import setup_logger

logger = setup_logger("insider_congress")

HOUSE_URL = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"
SENATE_URL = "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"


class InsiderCongressClient:
    """Fetch and aggregate insider + congressional trading data."""

    _house_cache: list | None = None
    _house_cache_time: float = 0
    _senate_cache: list | None = None
    _senate_cache_time: float = 0
    _CACHE_TTL = 3600  # 1 hour

    # ------------------------------------------------------------------
    # Congressional trading (House + Senate)
    # ------------------------------------------------------------------

    def _fetch_json(self, url: str, timeout: int = 60) -> list:
        """Fetch JSON from URL."""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "FE-Analyst/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", url, e)
            return []

    def _get_house_data(self) -> list:
        """Get House trades with 1hr in-memory cache."""
        now = time.time()
        if InsiderCongressClient._house_cache is not None and now - InsiderCongressClient._house_cache_time < self._CACHE_TTL:
            return InsiderCongressClient._house_cache
        logger.info("Fetching House Stock Watcher data...")
        data = self._fetch_json(HOUSE_URL)
        InsiderCongressClient._house_cache = data
        InsiderCongressClient._house_cache_time = now
        return data

    def _get_senate_data(self) -> list:
        """Get Senate trades with 1hr in-memory cache."""
        now = time.time()
        if InsiderCongressClient._senate_cache is not None and now - InsiderCongressClient._senate_cache_time < self._CACHE_TTL:
            return InsiderCongressClient._senate_cache
        logger.info("Fetching Senate Stock Watcher data...")
        data = self._fetch_json(SENATE_URL)
        InsiderCongressClient._senate_cache = data
        InsiderCongressClient._senate_cache_time = now
        return data

    def get_congressional_trades(self, ticker: str, days: int = 365) -> list[dict]:
        """Get recent congressional trades for a ticker."""
        ticker_upper = ticker.upper()
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        trades = []

        # House trades
        for t in self._get_house_data():
            t_ticker = (t.get("ticker") or "").upper().strip()
            if t_ticker != ticker_upper:
                continue
            tx_date = t.get("transaction_date", "")
            if tx_date and tx_date >= cutoff:
                trades.append({
                    "date": tx_date,
                    "disclosure_date": t.get("disclosure_date", ""),
                    "name": t.get("representative", "Unknown"),
                    "chamber": "House",
                    "type": t.get("type", "Unknown"),
                    "amount_range": t.get("amount", ""),
                    "ticker": ticker_upper,
                    "description": t.get("asset_description", ""),
                })

        # Senate trades
        for t in self._get_senate_data():
            t_ticker = (t.get("ticker") or "").upper().strip()
            if t_ticker != ticker_upper:
                continue
            tx_date = t.get("transaction_date", "")
            if tx_date and tx_date >= cutoff:
                trades.append({
                    "date": tx_date,
                    "disclosure_date": t.get("disclosure_date", ""),
                    "name": t.get("senator", t.get("first_name", "")) + " " + t.get("last_name", ""),
                    "chamber": "Senate",
                    "type": t.get("type", "Unknown"),
                    "amount_range": t.get("amount", ""),
                    "ticker": ticker_upper,
                    "description": t.get("asset_description", ""),
                })

        # Deduplicate and sort
        seen = set()
        unique = []
        for t in trades:
            key = (t["date"], t["name"].strip(), t["type"])
            if key not in seen:
                seen.add(key)
                unique.append(t)

        unique.sort(key=lambda x: x.get("date", ""), reverse=True)
        return unique[:50]

    # ------------------------------------------------------------------
    # Insider trading (SEC Form 4 via Finnhub)
    # ------------------------------------------------------------------

    def get_insider_trades(self, ticker: str) -> list[dict]:
        """Get insider transactions via Finnhub."""
        if not Keys.FINNHUB:
            logger.warning("No Finnhub key for insider trades")
            return []

        try:
            import finnhub
            client = finnhub.Client(api_key=Keys.FINNHUB)
            data = client.stock_insider_transactions(ticker)
            raw = data.get("data", [])

            # Normalize to common format
            trades = []
            for t in raw[:30]:
                trades.append({
                    "date": t.get("transactionDate", ""),
                    "filing_date": t.get("filingDate", ""),
                    "name": t.get("name", "Unknown"),
                    "title": "",
                    "transaction_code": t.get("transactionCode", ""),
                    "shares": t.get("share", 0),
                    "change": t.get("change", 0),
                    "price": t.get("transactionPrice", 0),
                    "value": abs(t.get("change", 0)) * (t.get("transactionPrice", 0) or 0),
                })
            return trades
        except Exception as e:
            logger.warning("Finnhub insider trades failed for %s: %s", ticker, e)
            return []

    # ------------------------------------------------------------------
    # Combined summary with signal
    # ------------------------------------------------------------------

    def get_insider_summary(self, ticker: str, days: int = 180) -> dict:
        """Combined insider + congressional summary with buy/sell signal."""
        insider_trades = self.get_insider_trades(ticker)
        congress_trades = self.get_congressional_trades(ticker, days=days)

        # Insider buy/sell count (P=Purchase, S=Sale)
        insider_buys = sum(1 for t in insider_trades if t.get("transaction_code") == "P")
        insider_sells = sum(1 for t in insider_trades if t.get("transaction_code") == "S")

        # Congressional buy/sell count
        buy_types = {"purchase", "buy"}
        sell_types = {"sale", "sell", "sale (full)", "sale (partial)", "sale_full", "sale_partial"}
        congress_buys = sum(1 for t in congress_trades if t.get("type", "").lower() in buy_types)
        congress_sells = sum(1 for t in congress_trades if t.get("type", "").lower() in sell_types)

        total_buys = insider_buys + congress_buys
        total_sells = insider_sells + congress_sells

        if total_buys > total_sells * 1.5 and total_buys >= 2:
            signal = "BULLISH"
        elif total_sells > total_buys * 1.5 and total_sells >= 2:
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"

        return {
            "ticker": ticker,
            "signal": signal,
            "insider_trades": insider_trades[:20],
            "insider_buys": insider_buys,
            "insider_sells": insider_sells,
            "congressional_trades": congress_trades[:20],
            "congress_buys": congress_buys,
            "congress_sells": congress_sells,
            "total_buys": total_buys,
            "total_sells": total_sells,
        }

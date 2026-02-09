"""Fundamental data client - financials, ratios, company info.

Primary: yfinance + SimFin | Fallback: finnhub, FMP
"""

import pandas as pd
import yfinance as yf

from src.config import Keys
from src.utils.cache import DataCache
from src.utils.logger import setup_logger

logger = setup_logger("fundamentals")
cache = DataCache("fundamentals")


class FundamentalsClient:
    """Fetch financial statements and company fundamentals."""

    def get_income_statement(self, ticker: str, quarterly: bool = False) -> pd.DataFrame:
        """Get income statement data."""
        cache_key = f"income_{ticker}_{'q' if quarterly else 'a'}"
        cached = cache.get_df(cache_key)
        if cached is not None:
            return cached

        logger.info("Fetching income statement: %s", ticker)
        stock = yf.Ticker(ticker)
        df = stock.quarterly_income_stmt if quarterly else stock.income_stmt
        if not df.empty:
            cache.set_df(cache_key, df)
        return df

    def get_balance_sheet(self, ticker: str, quarterly: bool = False) -> pd.DataFrame:
        """Get balance sheet data."""
        cache_key = f"balance_{ticker}_{'q' if quarterly else 'a'}"
        cached = cache.get_df(cache_key)
        if cached is not None:
            return cached

        logger.info("Fetching balance sheet: %s", ticker)
        stock = yf.Ticker(ticker)
        df = stock.quarterly_balance_sheet if quarterly else stock.balance_sheet
        if not df.empty:
            cache.set_df(cache_key, df)
        return df

    def get_cash_flow(self, ticker: str, quarterly: bool = False) -> pd.DataFrame:
        """Get cash flow statement."""
        cache_key = f"cashflow_{ticker}_{'q' if quarterly else 'a'}"
        cached = cache.get_df(cache_key)
        if cached is not None:
            return cached

        logger.info("Fetching cash flow: %s", ticker)
        stock = yf.Ticker(ticker)
        df = stock.quarterly_cashflow if quarterly else stock.cashflow
        if not df.empty:
            cache.set_df(cache_key, df)
        return df

    def get_key_ratios(self, ticker: str) -> dict:
        """Get key financial ratios and metrics."""
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "ticker": ticker,
            "pe_trailing": info.get("trailingPE"),
            "pe_forward": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "pb_ratio": info.get("priceToBook"),
            "ps_ratio": info.get("priceToSalesTrailing12Months"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "profit_margin": info.get("profitMargins"),
            "operating_margin": info.get("operatingMargins"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            "dividend_yield": info.get("dividendYield"),
            "payout_ratio": info.get("payoutRatio"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
        }

    def get_company_profile(self, ticker: str) -> dict:
        """Get company overview / profile."""
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "ticker": ticker,
            "name": info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "employees": info.get("fullTimeEmployees"),
            "country": info.get("country"),
            "website": info.get("website"),
            "description": info.get("longBusinessSummary"),
        }

    def get_peers(self, ticker: str) -> list[str]:
        """Get peer/comparable companies via finnhub."""
        if not Keys.FINNHUB:
            logger.warning("No Finnhub key; cannot fetch peers")
            return []

        import finnhub

        client = finnhub.Client(api_key=Keys.FINNHUB)
        return client.company_peers(ticker)

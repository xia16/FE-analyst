"""Macro / economic data client.

Sources: FRED, BLS, World Bank, US Treasury
"""

import pandas as pd

from src.config import Keys
from src.utils.cache import DataCache
from src.utils.logger import setup_logger

logger = setup_logger("macro_data")
cache = DataCache("macro_data")


class MacroDataClient:
    """Fetch macroeconomic indicators."""

    def get_fred_series(self, series_id: str, start: str = "2015-01-01") -> pd.Series:
        """Get a FRED data series (e.g., GDP, CPI, unemployment)."""
        cache_key = f"fred_{series_id}_{start}"
        cached = cache.get_df(cache_key)
        if cached is not None:
            return cached.squeeze()

        if not Keys.FRED:
            logger.warning("No FRED API key")
            return pd.Series(dtype=float)

        from fredapi import Fred

        logger.info("Fetching FRED series: %s", series_id)
        fred = Fred(api_key=Keys.FRED)
        data = fred.get_series(series_id, observation_start=start)

        cache.set_df(cache_key, data.to_frame(name=series_id))
        return data

    def get_treasury_yields(self) -> dict:
        """Get current US Treasury yields."""
        series_map = {
            "3m": "DGS3MO",
            "2y": "DGS2",
            "5y": "DGS5",
            "10y": "DGS10",
            "30y": "DGS30",
        }
        yields = {}
        for label, series_id in series_map.items():
            data = self.get_fred_series(series_id)
            if not data.empty:
                yields[label] = data.iloc[-1]
        return yields

    def get_risk_free_rate(self) -> float:
        """Get current 10-year Treasury yield as risk-free rate."""
        data = self.get_fred_series("DGS10")
        if data.empty:
            return 0.04  # fallback
        return float(data.iloc[-1]) / 100

    def get_economic_indicators(self) -> dict:
        """Get key economic indicators snapshot."""
        indicators = {
            "gdp_growth": "A191RL1Q225SBEA",
            "unemployment": "UNRATE",
            "cpi_yoy": "CPIAUCSL",
            "fed_funds_rate": "FEDFUNDS",
            "sp500": "SP500",
            "vix": "VIXCLS",
        }
        results = {}
        for name, series_id in indicators.items():
            data = self.get_fred_series(series_id)
            if not data.empty:
                results[name] = float(data.iloc[-1])
        return results

    def get_world_bank_indicator(
        self, indicator: str = "NY.GDP.MKTP.CD", country: str = "US"
    ) -> pd.DataFrame:
        """Fetch World Bank data (no API key needed)."""
        import wbdata

        logger.info("Fetching World Bank: %s for %s", indicator, country)
        data = wbdata.get_dataframe({indicator: "value"}, country=country)
        return data

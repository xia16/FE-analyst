"""Stock screening and filtering."""

import pandas as pd
from finvizfinance.screener.overview import Overview

from src.utils.logger import setup_logger

logger = setup_logger("screener")


class StockScreener:
    """Screen stocks using finviz filters."""

    def screen(self, filters: dict | None = None) -> pd.DataFrame:
        """Run a stock screen with given filters.

        Args:
            filters: Dict of finviz filter parameters, e.g.:
                {
                    "Market Cap.": "Large ($10bln to $200bln)",
                    "P/E": "Under 20",
                    "Dividend Yield": "Over 2%",
                    "Country": "USA",
                }

        Returns:
            DataFrame of matching stocks.
        """
        logger.info("Running stock screen with filters: %s", filters)
        overview = Overview()
        if filters:
            overview.set_filter(filters_dict=filters)
        return overview.screener_view()

    def value_stocks(self) -> pd.DataFrame:
        """Pre-built screen: undervalued stocks."""
        return self.screen({
            "P/E": "Under 15",
            "P/B": "Under 2",
            "Dividend Yield": "Over 2%",
            "Market Cap.": "+Mid (over $2bln)",
        })

    def growth_stocks(self) -> pd.DataFrame:
        """Pre-built screen: high-growth stocks."""
        return self.screen({
            "EPS growth next 5 years": "Over 15%",
            "Sales growth past 5 years": "Over 10%",
            "Market Cap.": "+Mid (over $2bln)",
        })

    def momentum_stocks(self) -> pd.DataFrame:
        """Pre-built screen: momentum plays."""
        return self.screen({
            "Performance (Month)": "Over 10%",
            "Performance (Quarter)": "Over 20%",
            "Average Volume": "Over 1M",
        })

    def dividend_stocks(self) -> pd.DataFrame:
        """Pre-built screen: dividend income stocks."""
        return self.screen({
            "Dividend Yield": "Over 3%",
            "Payout Ratio": "Under 60%",
            "Market Cap.": "+Large (over $10bln)",
        })

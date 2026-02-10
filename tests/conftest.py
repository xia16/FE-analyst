"""Shared pytest fixtures for FE-Analyst test suite.

Provides synthetic financial data with fixed random seed for reproducibility.
All fixtures are independent of external APIs.
"""

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# 1. OHLCV fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_ohlcv():
    """Generate a synthetic OHLCV DataFrame with 252 rows and realistic prices.

    Uses a geometric Brownian motion model seeded at 42 for reproducibility.
    Starting price ~150, daily drift ~0.04%, daily vol ~1.5%.
    """
    np.random.seed(42)
    n = 252
    dates = pd.bdate_range(start="2023-01-02", periods=n)
    drift = 0.0004
    vol = 0.015
    log_returns = np.random.normal(drift, vol, n)
    close = 150.0 * np.exp(np.cumsum(log_returns))

    # Build OHLCV from close
    high = close * (1 + np.abs(np.random.normal(0.002, 0.005, n)))
    low = close * (1 - np.abs(np.random.normal(0.002, 0.005, n)))
    open_ = close * (1 + np.random.normal(0, 0.003, n))
    volume = np.random.randint(1_000_000, 10_000_000, n).astype(float)

    df = pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        },
        index=dates,
    )
    return df


# ---------------------------------------------------------------------------
# 2. Daily returns fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_returns():
    """Daily returns series with 252 observations, seeded at 42."""
    np.random.seed(42)
    n = 252
    dates = pd.bdate_range(start="2023-01-02", periods=n)
    returns = np.random.normal(0.0004, 0.015, n)
    return pd.Series(returns, index=dates, name="returns")


# ---------------------------------------------------------------------------
# 3. Income statement fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_income_statement():
    """Mock income statement DataFrame with 4 annual periods.

    Rows are line-item labels (index), columns are dates (most-recent first).
    """
    dates = pd.to_datetime(["2023-12-31", "2022-12-31", "2021-12-31", "2020-12-31"])
    data = {
        dates[0]: {
            "Total Revenue": 120_000_000,
            "Cost Of Revenue": 72_000_000,
            "Gross Profit": 48_000_000,
            "Operating Income": 30_000_000,
            "EBIT": 28_000_000,
            "EBITDA": 35_000_000,
            "Pretax Income": 26_000_000,
            "Tax Provision": 5_460_000,
            "Net Income": 20_540_000,
            "Interest Expense": 2_000_000,
        },
        dates[1]: {
            "Total Revenue": 110_000_000,
            "Cost Of Revenue": 68_200_000,
            "Gross Profit": 41_800_000,
            "Operating Income": 26_000_000,
            "EBIT": 24_500_000,
            "EBITDA": 31_000_000,
            "Pretax Income": 23_000_000,
            "Tax Provision": 4_830_000,
            "Net Income": 18_170_000,
            "Interest Expense": 1_500_000,
        },
        dates[2]: {
            "Total Revenue": 100_000_000,
            "Cost Of Revenue": 65_000_000,
            "Gross Profit": 35_000_000,
            "Operating Income": 22_000_000,
            "EBIT": 21_000_000,
            "EBITDA": 27_000_000,
            "Pretax Income": 19_500_000,
            "Tax Provision": 4_095_000,
            "Net Income": 15_405_000,
            "Interest Expense": 1_500_000,
        },
        dates[3]: {
            "Total Revenue": 90_000_000,
            "Cost Of Revenue": 60_300_000,
            "Gross Profit": 29_700_000,
            "Operating Income": 18_000_000,
            "EBIT": 17_000_000,
            "EBITDA": 23_000_000,
            "Pretax Income": 15_500_000,
            "Tax Provision": 3_255_000,
            "Net Income": 12_245_000,
            "Interest Expense": 1_500_000,
        },
    }
    df = pd.DataFrame(data)
    return df


# ---------------------------------------------------------------------------
# 4. Balance sheet fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_balance_sheet():
    """Mock balance sheet DataFrame with 4 annual periods."""
    dates = pd.to_datetime(["2023-12-31", "2022-12-31", "2021-12-31", "2020-12-31"])
    data = {
        dates[0]: {
            "Total Assets": 200_000_000,
            "Total Liabilities Net Minority Interest": 90_000_000,
            "Stockholders Equity": 110_000_000,
            "Current Assets": 60_000_000,
            "Current Liabilities": 30_000_000,
            "Total Debt": 50_000_000,
            "Long Term Debt": 45_000_000,
            "Cash And Cash Equivalents": 25_000_000,
            "Net Receivables": 15_000_000,
            "Inventory": 10_000_000,
            "Accounts Payable": 8_000_000,
            "Retained Earnings": 80_000_000,
            "Working Capital": 30_000_000,
            "Ordinary Shares Number": 10_000_000,
        },
        dates[1]: {
            "Total Assets": 185_000_000,
            "Total Liabilities Net Minority Interest": 85_000_000,
            "Stockholders Equity": 100_000_000,
            "Current Assets": 55_000_000,
            "Current Liabilities": 32_000_000,
            "Total Debt": 55_000_000,
            "Long Term Debt": 50_000_000,
            "Cash And Cash Equivalents": 20_000_000,
            "Net Receivables": 14_000_000,
            "Inventory": 12_000_000,
            "Accounts Payable": 9_000_000,
            "Retained Earnings": 70_000_000,
            "Working Capital": 23_000_000,
            "Ordinary Shares Number": 10_000_000,
        },
        dates[2]: {
            "Total Assets": 170_000_000,
            "Total Liabilities Net Minority Interest": 80_000_000,
            "Stockholders Equity": 90_000_000,
            "Current Assets": 50_000_000,
            "Current Liabilities": 28_000_000,
            "Total Debt": 52_000_000,
            "Long Term Debt": 47_000_000,
            "Cash And Cash Equivalents": 18_000_000,
            "Net Receivables": 13_000_000,
            "Inventory": 11_000_000,
            "Accounts Payable": 7_500_000,
            "Retained Earnings": 60_000_000,
            "Working Capital": 22_000_000,
            "Ordinary Shares Number": 10_000_000,
        },
        dates[3]: {
            "Total Assets": 160_000_000,
            "Total Liabilities Net Minority Interest": 78_000_000,
            "Stockholders Equity": 82_000_000,
            "Current Assets": 45_000_000,
            "Current Liabilities": 27_000_000,
            "Total Debt": 51_000_000,
            "Long Term Debt": 46_000_000,
            "Cash And Cash Equivalents": 15_000_000,
            "Net Receivables": 12_000_000,
            "Inventory": 10_000_000,
            "Accounts Payable": 7_000_000,
            "Retained Earnings": 50_000_000,
            "Working Capital": 18_000_000,
            "Ordinary Shares Number": 10_500_000,
        },
    }
    df = pd.DataFrame(data)
    return df


# ---------------------------------------------------------------------------
# 5. Cash flow fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_cash_flow():
    """Mock cash flow DataFrame with 4 annual periods."""
    dates = pd.to_datetime(["2023-12-31", "2022-12-31", "2021-12-31", "2020-12-31"])
    data = {
        dates[0]: {
            "Operating Cash Flow": 28_000_000,
            "Capital Expenditure": -8_000_000,
            "Free Cash Flow": 20_000_000,
        },
        dates[1]: {
            "Operating Cash Flow": 25_000_000,
            "Capital Expenditure": -7_000_000,
            "Free Cash Flow": 18_000_000,
        },
        dates[2]: {
            "Operating Cash Flow": 22_000_000,
            "Capital Expenditure": -6_500_000,
            "Free Cash Flow": 15_500_000,
        },
        dates[3]: {
            "Operating Cash Flow": 19_000_000,
            "Capital Expenditure": -6_000_000,
            "Free Cash Flow": 13_000_000,
        },
    }
    df = pd.DataFrame(data)
    return df

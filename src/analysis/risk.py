"""Risk analysis - volatility, VaR, drawdown, beta."""

import numpy as np
import pandas as pd

from src.data_sources.market_data import MarketDataClient
from src.utils.logger import setup_logger

logger = setup_logger("risk")


class RiskAnalyzer:
    """Assess investment risk for a stock."""

    def __init__(self):
        self.market = MarketDataClient()

    def analyze(self, ticker: str, benchmark: str = "SPY", period: str = "2y") -> dict:
        """Full risk analysis for a ticker."""
        df = self.market.get_price_history(ticker, period=period)
        bench_df = self.market.get_price_history(benchmark, period=period)

        if df.empty:
            return {"error": "No price data"}

        returns = df["Close"].pct_change().dropna()
        bench_returns = bench_df["Close"].pct_change().dropna()

        # Align dates
        aligned = pd.concat([returns, bench_returns], axis=1, join="inner")
        aligned.columns = ["stock", "benchmark"]

        result = {
            "ticker": ticker,
            "period": period,
            "volatility": self._annualized_volatility(returns),
            "sharpe_ratio": self._sharpe_ratio(returns),
            "sortino_ratio": self._sortino_ratio(returns),
            "max_drawdown": self._max_drawdown(df["Close"]),
            "beta": self._beta(aligned["stock"], aligned["benchmark"]),
            "var_95": self._value_at_risk(returns, confidence=0.95),
            "cvar_95": self._conditional_var(returns, confidence=0.95),
        }

        # Risk rating
        vol = result["volatility"]
        if vol < 0.15:
            result["risk_level"] = "LOW"
        elif vol < 0.30:
            result["risk_level"] = "MODERATE"
        elif vol < 0.50:
            result["risk_level"] = "HIGH"
        else:
            result["risk_level"] = "VERY HIGH"

        return result

    @staticmethod
    def _annualized_volatility(returns: pd.Series) -> float:
        return round(float(returns.std() * np.sqrt(252)), 4)

    @staticmethod
    def _sharpe_ratio(returns: pd.Series, risk_free_annual: float = 0.04) -> float:
        rf_daily = risk_free_annual / 252
        excess = returns - rf_daily
        if excess.std() == 0:
            return 0.0
        return round(float(excess.mean() / excess.std() * np.sqrt(252)), 4)

    @staticmethod
    def _sortino_ratio(returns: pd.Series, risk_free_annual: float = 0.04) -> float:
        rf_daily = risk_free_annual / 252
        excess = returns - rf_daily
        downside = excess[excess < 0]
        if downside.std() == 0:
            return 0.0
        return round(float(excess.mean() / downside.std() * np.sqrt(252)), 4)

    @staticmethod
    def _max_drawdown(prices: pd.Series) -> float:
        cummax = prices.cummax()
        drawdown = (prices - cummax) / cummax
        return round(float(drawdown.min()), 4)

    @staticmethod
    def _beta(stock_returns: pd.Series, bench_returns: pd.Series) -> float:
        cov = stock_returns.cov(bench_returns)
        var = bench_returns.var()
        if var == 0:
            return 0.0
        return round(float(cov / var), 4)

    @staticmethod
    def _value_at_risk(returns: pd.Series, confidence: float = 0.95) -> float:
        return round(float(np.percentile(returns, (1 - confidence) * 100)), 4)

    @staticmethod
    def _conditional_var(returns: pd.Series, confidence: float = 0.95) -> float:
        var = np.percentile(returns, (1 - confidence) * 100)
        return round(float(returns[returns <= var].mean()), 4)

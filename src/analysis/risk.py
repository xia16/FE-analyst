"""Risk analysis - volatility, VaR, drawdown, beta.

Enhanced with dynamic benchmark selection (SPY vs Nikkei vs sector ETF),
tail risk metrics (skewness, kurtosis), and liquidity risk assessment.
"""

import numpy as np
import pandas as pd

from src.data_sources.market_data import MarketDataClient
from src.utils.logger import setup_logger

logger = setup_logger("risk")

# Dynamic benchmark mapping by country / exchange
COUNTRY_BENCHMARKS = {
    "Japan": "EWJ",          # iShares MSCI Japan
    "Taiwan": "EWT",         # iShares MSCI Taiwan
    "South Korea": "EWY",    # iShares MSCI South Korea
    "Netherlands": "EWN",    # iShares MSCI Netherlands
    "Germany": "EWG",        # iShares MSCI Germany
    "France": "EWQ",         # iShares MSCI France
    "China": "MCHI",         # iShares MSCI China
    "United Kingdom": "EWU",
    "Israel": "EIS",
}

# Sector ETF benchmarks
SECTOR_BENCHMARKS = {
    "Technology": "XLK",
    "Semiconductors": "SOXX",
    "Communication Services": "XLC",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Healthcare": "XLV",
    "Industrials": "XLI",
    "Financial Services": "XLF",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Basic Materials": "XLB",
}


class RiskAnalyzer:
    """Assess investment risk for a stock."""

    def __init__(self):
        self.market = MarketDataClient()

    def _select_benchmark(self, ticker: str) -> tuple[str, str]:
        """Dynamically select the most appropriate benchmark for a stock.

        Returns (benchmark_ticker, reason) based on the stock's country
        and sector, falling back to SPY for US stocks.
        """
        try:
            import yfinance as yf
            info = yf.Ticker(ticker).info
            country = info.get("country", "United States") or "United States"
            sector = info.get("sector", "")
            industry = info.get("industry", "")

            # Non-US stocks: use country ETF
            if country != "United States" and country in COUNTRY_BENCHMARKS:
                return COUNTRY_BENCHMARKS[country], f"Country benchmark ({country})"

            # Semiconductor stocks get SOXX
            if "semiconductor" in (industry or "").lower() or "Semiconductors" in (sector or ""):
                return "SOXX", f"Sector benchmark (Semiconductors)"

            # Other US stocks: use sector ETF if available
            if sector in SECTOR_BENCHMARKS:
                return SECTOR_BENCHMARKS[sector], f"Sector benchmark ({sector})"

        except Exception as e:
            logger.debug("Benchmark selection failed for %s: %s — defaulting to SPY", ticker, e)

        return "SPY", "S&P 500 (default)"

    def analyze(self, ticker: str, benchmark: str | None = None, period: str = "2y") -> dict:
        """Full risk analysis for a ticker with dynamic benchmark."""
        # Dynamic benchmark selection
        if benchmark is None:
            benchmark, bench_reason = self._select_benchmark(ticker)
        else:
            bench_reason = "User-specified"

        df = self.market.get_price_history(ticker, period=period)
        bench_df = self.market.get_price_history(benchmark, period=period)

        # Fallback to SPY if country ETF fails
        if bench_df.empty and benchmark != "SPY":
            logger.warning("Benchmark %s returned no data, falling back to SPY", benchmark)
            benchmark = "SPY"
            bench_reason = "S&P 500 (fallback)"
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
            "benchmark": benchmark,
            "benchmark_reason": bench_reason,
            "period": period,
            "volatility": self._annualized_volatility(returns),
            "sharpe_ratio": self._sharpe_ratio(returns),
            "sortino_ratio": self._sortino_ratio(returns),
            "max_drawdown": self._max_drawdown(df["Close"]),
            "beta": self._beta(aligned["stock"], aligned["benchmark"]),
            "var_95": self._value_at_risk(returns, confidence=0.95),
            "cvar_95": self._conditional_var(returns, confidence=0.95),
        }

        # --- NEW: Tail risk metrics ---
        result["skewness"] = round(float(returns.skew()), 4) if len(returns) > 10 else None
        result["kurtosis"] = round(float(returns.kurtosis()), 4) if len(returns) > 10 else None

        # Negative skew + high kurtosis = fat left tails (crash risk)
        if result["skewness"] is not None and result["kurtosis"] is not None:
            if result["skewness"] < -0.5 and result["kurtosis"] > 3:
                result["tail_risk"] = "ELEVATED — negative skew with fat tails"
            elif result["kurtosis"] > 5:
                result["tail_risk"] = "HIGH — extreme kurtosis (frequent large moves)"
            else:
                result["tail_risk"] = "NORMAL"

        # --- NEW: Liquidity risk ---
        result["liquidity"] = self._liquidity_assessment(df)

        # --- NEW: Correlation with benchmark ---
        if len(aligned) > 20:
            result["correlation"] = round(float(aligned["stock"].corr(aligned["benchmark"])), 4)

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
    def _liquidity_assessment(df: pd.DataFrame) -> dict:
        """Assess liquidity risk from volume data."""
        try:
            if "Volume" not in df.columns:
                return {"signal": "NO DATA"}

            vol = df["Volume"].tail(20)
            avg_vol = float(vol.mean())
            min_vol = float(vol.min())

            result = {
                "avg_daily_volume_20d": int(avg_vol),
                "min_daily_volume_20d": int(min_vol),
            }

            # Dollar volume estimate
            latest_price = float(df["Close"].iloc[-1])
            dollar_vol = avg_vol * latest_price
            result["avg_dollar_volume_20d"] = round(dollar_vol, 0)

            if dollar_vol < 500_000:
                result["signal"] = "ILLIQUID"
                result["detail"] = "Very low dollar volume — significant execution risk"
            elif dollar_vol < 5_000_000:
                result["signal"] = "LOW LIQUIDITY"
                result["detail"] = "Low dollar volume — may face slippage"
            elif dollar_vol < 50_000_000:
                result["signal"] = "ADEQUATE"
                result["detail"] = "Adequate liquidity for moderate positions"
            else:
                result["signal"] = "HIGHLY LIQUID"
                result["detail"] = "High liquidity — minimal execution risk"

            return result
        except Exception:
            return {"signal": "NO DATA"}

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


# --- Plugin adapter for pipeline ---
from src.analysis.base import BaseAnalyzer as _BaseAnalyzer


class RiskAnalyzerPlugin(_BaseAnalyzer):
    name = "risk"
    default_weight = 0.15

    def __init__(self):
        self._analyzer = RiskAnalyzer()

    def analyze(self, ticker, ctx):
        result = self._analyzer.analyze(ticker)
        vol = result.get("volatility", 0.3)
        score = max(0, min(100, (1 - vol) * 100))

        # Penalize tail risk
        if result.get("tail_risk", "").startswith("HIGH"):
            score = max(0, score - 10)
        elif result.get("tail_risk", "").startswith("ELEVATED"):
            score = max(0, score - 5)

        # Penalize illiquidity
        liquidity = result.get("liquidity", {}).get("signal", "")
        if liquidity == "ILLIQUID":
            score = max(0, score - 15)
        elif liquidity == "LOW LIQUIDITY":
            score = max(0, score - 5)

        result["score"] = round(score, 1)
        return result

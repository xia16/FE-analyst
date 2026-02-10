"""Institutional-grade risk analysis engine.

Computes volatility, VaR/CVaR, tail risk, factor decomposition, rolling risk,
stress testing, correlation analysis, and composite risk classification.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from src.data_sources.market_data import MarketDataClient
from src.utils.logger import setup_logger

logger = setup_logger("risk")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TRADING_DAYS: int = 252
RISK_FREE_ANNUAL: float = 0.04  # fallback; overridden when macro data available

HISTORICAL_SCENARIOS: dict[str, dict[str, Any]] = {
    "2008 Financial Crisis": {"drawdown": -0.38, "duration_months": 12},
    "2020 COVID Crash": {"drawdown": -0.34, "duration_months": 1},
    "2022 Rate Shock": {"drawdown": -0.25, "duration_months": 9},
    "Flash Crash": {"drawdown": -0.07, "duration_months": 0},
}

SECTOR_ETF_MAP: dict[str, str] = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financials": "XLF",
    "Energy": "XLE",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}


def _round(value: float, decimals: int = 4) -> float:
    """Safe rounding that handles NaN / Inf."""
    if not np.isfinite(value):
        return 0.0
    return round(float(value), decimals)


# ---------------------------------------------------------------------------
# Core Risk Engine
# ---------------------------------------------------------------------------
class RiskAnalyzer:
    """Hedge-fund-grade risk analytics for a single equity."""

    def __init__(self) -> None:
        self.market = MarketDataClient()

    # -----------------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------------
    def analyze(
        self,
        ticker: str,
        benchmark: str = "SPY",
        period: str = "2y",
        risk_free_annual: float = RISK_FREE_ANNUAL,
        sector: str | None = None,
    ) -> dict[str, Any]:
        """Run the full risk analysis suite for *ticker*.

        Parameters
        ----------
        ticker : str
            Stock symbol.
        benchmark : str
            Benchmark ticker (default ``"SPY"``).
        period : str
            Look-back window understood by yfinance.
        risk_free_annual : float
            Annualised risk-free rate.
        sector : str | None
            GICS sector name (used for sector-ETF correlation).

        Returns
        -------
        dict
            Nested dictionary with all risk metrics and a top-level ``"score"``
            key (0--100, higher means *less risky*).
        """
        # -- Fetch price data ------------------------------------------------
        df = self.market.get_price_history(ticker, period=period)
        bench_df = self.market.get_price_history(benchmark, period=period)

        if df.empty:
            logger.warning("No price data for %s", ticker)
            return {"error": "No price data", "ticker": ticker, "score": 50}

        prices = df["Close"]
        returns = prices.pct_change().dropna()

        if len(returns) < 30:
            logger.warning("Insufficient history for %s (%d points)", ticker, len(returns))
            return {"error": "Insufficient history", "ticker": ticker, "score": 50}

        bench_prices = bench_df["Close"] if not bench_df.empty else pd.Series(dtype=float)
        bench_returns = bench_prices.pct_change().dropna() if not bench_prices.empty else pd.Series(dtype=float)

        # Align stock and benchmark on common dates
        aligned = pd.concat([returns, bench_returns], axis=1, join="inner")
        aligned.columns = ["stock", "benchmark"]

        rf_daily = risk_free_annual / TRADING_DAYS

        # -- Build result dict -----------------------------------------------
        result: dict[str, Any] = {"ticker": ticker, "benchmark": benchmark, "period": period}

        result["basic_metrics"] = self._basic_metrics(
            returns, prices, aligned, rf_daily, risk_free_annual,
        )
        result["tail_risk"] = self._tail_risk_metrics(returns)
        result["factor_model"] = self._factor_model(
            ticker, returns, rf_daily, period,
        )
        result["rolling_risk"] = self._rolling_risk(
            returns, aligned, rf_daily,
        )
        result["stress_testing"] = self._stress_testing(
            returns, result["basic_metrics"].get("beta", 1.0),
        )
        result["correlation_analysis"] = self._correlation_analysis(
            returns, prices, aligned, bench_prices, sector,
        )

        # -- Classification --------------------------------------------------
        classification = self._risk_classification(result)
        result["risk_classification"] = classification
        result["score"] = classification["risk_score"]

        return result

    # -----------------------------------------------------------------------
    # 1. Basic Risk Metrics
    # -----------------------------------------------------------------------
    def _basic_metrics(
        self,
        returns: pd.Series,
        prices: pd.Series,
        aligned: pd.DataFrame,
        rf_daily: float,
        rf_annual: float,
    ) -> dict[str, Any]:
        stock_ret = aligned["stock"]
        bench_ret = aligned["benchmark"]

        ann_vol = self._annualized_volatility(returns)
        beta = self._beta(stock_ret, bench_ret)
        max_dd = self._max_drawdown(prices)
        dd_duration = self._max_drawdown_duration(prices)

        ann_return = _round(float(returns.mean()) * TRADING_DAYS)
        bench_ann_return = _round(float(bench_ret.mean()) * TRADING_DAYS) if len(bench_ret) > 0 else 0.0

        tracking_error = self._tracking_error(stock_ret, bench_ret)
        info_ratio = (
            _round((ann_return - bench_ann_return) / tracking_error)
            if tracking_error > 0 else 0.0
        )
        treynor = (
            _round((ann_return - rf_annual) / beta)
            if beta != 0 else 0.0
        )
        calmar = (
            _round(ann_return / abs(max_dd))
            if max_dd != 0 else 0.0
        )

        return {
            "annualized_volatility": ann_vol,
            "annualized_return": ann_return,
            "sharpe_ratio": self._sharpe_ratio(returns, rf_daily),
            "sortino_ratio": self._sortino_ratio(returns, rf_daily),
            "max_drawdown": max_dd,
            "max_drawdown_duration_days": dd_duration,
            "beta": beta,
            "var_95": self._value_at_risk(returns, 0.95),
            "var_99": self._value_at_risk(returns, 0.99),
            "cvar_95": self._conditional_var(returns, 0.95),
            "cvar_99": self._conditional_var(returns, 0.99),
            "calmar_ratio": calmar,
            "information_ratio": info_ratio,
            "treynor_ratio": treynor,
            "tracking_error": tracking_error,
        }

    # -----------------------------------------------------------------------
    # 2. Tail Risk Metrics
    # -----------------------------------------------------------------------
    @staticmethod
    def _tail_risk_metrics(returns: pd.Series) -> dict[str, Any]:
        skew = _round(float(returns.skew()))
        kurt = _round(float(returns.kurtosis()))  # pandas returns excess kurtosis

        n = len(returns)
        jb_stat = (n / 6.0) * (skew ** 2 + (kurt ** 2) / 4.0)
        jb_pvalue = 1.0 - float(scipy_stats.chi2.cdf(jb_stat, df=2))

        sorted_ret = returns.sort_values()
        bottom_5_pct = sorted_ret.iloc[: max(1, int(len(sorted_ret) * 0.05))]
        top_5_pct = sorted_ret.iloc[-max(1, int(len(sorted_ret) * 0.05)):]
        tail_ratio = (
            _round(float(top_5_pct.mean()) / abs(float(bottom_5_pct.mean())))
            if abs(float(bottom_5_pct.mean())) > 1e-10 else 0.0
        )

        negative_returns = returns[returns < 0]
        gain_to_pain = (
            _round(float(returns.sum()) / abs(float(negative_returns.sum())))
            if abs(float(negative_returns.sum())) > 1e-10 else 0.0
        )

        return {
            "skewness": skew,
            "excess_kurtosis": kurt,
            "jarque_bera_statistic": _round(jb_stat),
            "jarque_bera_pvalue": _round(jb_pvalue),
            "is_normal_distribution": jb_pvalue > 0.05,
            "tail_ratio": tail_ratio,
            "gain_to_pain_ratio": gain_to_pain,
        }

    # -----------------------------------------------------------------------
    # 3. Factor Model Decomposition
    # -----------------------------------------------------------------------
    def _factor_model(
        self,
        ticker: str,
        returns: pd.Series,
        rf_daily: float,
        period: str,
    ) -> dict[str, Any]:
        """Fama-French-style factor decomposition via OLS."""
        try:
            # Fetch factor-proxy ETFs
            etf_tickers = ["SPY", "IWM", "IWD", "IWF"]
            etf_data: dict[str, pd.Series] = {}
            for etf in etf_tickers:
                etf_df = self.market.get_price_history(etf, period=period)
                if etf_df.empty:
                    logger.warning("Could not fetch %s for factor model", etf)
                    return {"error": f"Missing factor data ({etf})"}
                etf_data[etf] = etf_df["Close"].pct_change().dropna()

            # Build factor series
            all_series = {"stock": returns}
            all_series.update(etf_data)
            factor_df = pd.DataFrame(all_series).dropna()

            if len(factor_df) < 60:
                return {"error": "Insufficient overlapping data for factor model"}

            excess_stock = factor_df["stock"].values - rf_daily  # Y
            mkt_excess = factor_df["SPY"].values - rf_daily      # Market factor
            smb = factor_df["IWM"].values - factor_df["SPY"].values  # Size proxy
            hml = factor_df["IWD"].values - factor_df["IWF"].values  # Value proxy

            # Momentum factor: 12-1 month momentum of the stock itself
            # Use trailing 252-day return minus trailing 21-day return
            stock_cum = (1 + factor_df["stock"]).cumprod()
            mom_raw = stock_cum / stock_cum.shift(TRADING_DAYS) - 1
            mom_short = stock_cum / stock_cum.shift(21) - 1
            momentum = (mom_raw - mom_short).fillna(0).values

            # Design matrix (with intercept)
            X = np.column_stack([
                np.ones(len(excess_stock)),
                mkt_excess,
                smb,
                hml,
                momentum,
            ])
            Y = excess_stock

            # OLS via numpy
            coeffs, residuals, rank, sv = np.linalg.lstsq(X, Y, rcond=None)

            alpha = _round(coeffs[0] * TRADING_DAYS)  # annualize
            betas = {
                "market": _round(coeffs[1]),
                "size_smb": _round(coeffs[2]),
                "value_hml": _round(coeffs[3]),
                "momentum": _round(coeffs[4]),
            }

            # R-squared
            y_hat = X @ coeffs
            ss_res = float(np.sum((Y - y_hat) ** 2))
            ss_tot = float(np.sum((Y - np.mean(Y)) ** 2))
            r_squared = _round(1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0

            # Residual volatility (annualised)
            residuals_arr = Y - y_hat
            residual_vol = _round(float(np.std(residuals_arr)) * np.sqrt(TRADING_DAYS))

            return {
                "alpha_annualized": alpha,
                "factor_betas": betas,
                "r_squared": r_squared,
                "residual_volatility": residual_vol,
                "num_observations": len(Y),
            }
        except Exception as exc:
            logger.error("Factor model failed for %s: %s", ticker, exc)
            return {"error": str(exc)}

    # -----------------------------------------------------------------------
    # 4. Rolling Risk Analysis
    # -----------------------------------------------------------------------
    def _rolling_risk(
        self,
        returns: pd.Series,
        aligned: pd.DataFrame,
        rf_daily: float,
    ) -> dict[str, Any]:
        windows = [30, 60, 90]
        rolling: dict[str, Any] = {}

        for w in windows:
            label = f"{w}d"
            if len(returns) < w:
                rolling[label] = {"error": f"Insufficient data for {w}-day window"}
                continue

            roll_vol = returns.rolling(w).std() * np.sqrt(TRADING_DAYS)
            roll_sharpe = (
                returns.rolling(w).mean() - rf_daily
            ) / returns.rolling(w).std() * np.sqrt(TRADING_DAYS)

            # Rolling beta
            stock_roll = aligned["stock"]
            bench_roll = aligned["benchmark"]
            roll_cov = stock_roll.rolling(w).cov(bench_roll)
            roll_var = bench_roll.rolling(w).var()
            roll_beta = roll_cov / roll_var.replace(0, np.nan)

            current_vol = _round(float(roll_vol.iloc[-1])) if pd.notna(roll_vol.iloc[-1]) else None
            current_sharpe = _round(float(roll_sharpe.iloc[-1])) if pd.notna(roll_sharpe.iloc[-1]) else None
            current_beta = _round(float(roll_beta.iloc[-1])) if len(roll_beta) > 0 and pd.notna(roll_beta.iloc[-1]) else None

            # Trend detection: compare latest value to the median of the last 3 values
            vol_series = roll_vol.dropna()
            if len(vol_series) >= 5:
                recent = vol_series.iloc[-5:]
                if recent.iloc[-1] > recent.iloc[0] * 1.05:
                    vol_trend = "increasing"
                elif recent.iloc[-1] < recent.iloc[0] * 0.95:
                    vol_trend = "decreasing"
                else:
                    vol_trend = "stable"
            else:
                vol_trend = "insufficient_data"

            rolling[label] = {
                "volatility": current_vol,
                "sharpe_ratio": current_sharpe,
                "beta": current_beta,
                "volatility_trend": vol_trend,
            }

        # Regime change detection: current 30d vol vs full-sample rolling 30d vol
        regime_shift = False
        if len(returns) >= 60:
            roll_vol_30 = returns.rolling(30).std().dropna() * np.sqrt(TRADING_DAYS)
            mean_vol = float(roll_vol_30.mean())
            std_vol = float(roll_vol_30.std())
            current_30d_vol = float(roll_vol_30.iloc[-1])
            if std_vol > 0 and current_30d_vol > mean_vol + 1.5 * std_vol:
                regime_shift = True

        rolling["regime_shift_detected"] = regime_shift

        return rolling

    # -----------------------------------------------------------------------
    # 5. Stress Testing
    # -----------------------------------------------------------------------
    @staticmethod
    def _stress_testing(returns: pd.Series, beta: float) -> dict[str, Any]:
        daily_vol = float(returns.std())

        scenario_results: dict[str, dict[str, Any]] = {}
        for name, params in HISTORICAL_SCENARIOS.items():
            estimated_loss = _round(params["drawdown"] * beta)
            scenario_results[name] = {
                "scenario_drawdown": params["drawdown"],
                "duration_months": params["duration_months"],
                "estimated_portfolio_loss": estimated_loss,
            }

        sigma_moves = {
            "2_sigma_daily_loss": _round(-2.0 * daily_vol),
            "3_sigma_daily_loss": _round(-3.0 * daily_vol),
            "2_sigma_dollar_pct": _round(-2.0 * daily_vol * 100),
            "3_sigma_dollar_pct": _round(-3.0 * daily_vol * 100),
        }

        return {
            "historical_scenarios": scenario_results,
            "sigma_moves": sigma_moves,
            "current_daily_vol": _round(daily_vol),
        }

    # -----------------------------------------------------------------------
    # 6. Correlation Analysis
    # -----------------------------------------------------------------------
    def _correlation_analysis(
        self,
        returns: pd.Series,
        prices: pd.Series,
        aligned: pd.DataFrame,
        bench_prices: pd.Series,
        sector: str | None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}

        stock_ret = aligned["stock"]
        bench_ret = aligned["benchmark"]

        # Full-period correlation with benchmark
        if len(stock_ret) > 1:
            result["benchmark_correlation"] = _round(float(stock_ret.corr(bench_ret)))
        else:
            result["benchmark_correlation"] = None

        # Rolling 60-day correlation
        if len(stock_ret) >= 60:
            roll_corr = stock_ret.rolling(60).corr(bench_ret).dropna()
            result["rolling_60d_correlation_current"] = _round(float(roll_corr.iloc[-1])) if len(roll_corr) > 0 else None
            result["rolling_60d_correlation_mean"] = _round(float(roll_corr.mean())) if len(roll_corr) > 0 else None
            result["rolling_60d_correlation_min"] = _round(float(roll_corr.min())) if len(roll_corr) > 0 else None
            result["rolling_60d_correlation_max"] = _round(float(roll_corr.max())) if len(roll_corr) > 0 else None
        else:
            result["rolling_60d_correlation_current"] = None
            result["rolling_60d_correlation_mean"] = None
            result["rolling_60d_correlation_min"] = None
            result["rolling_60d_correlation_max"] = None

        # Drawdown correlation: correlation during benchmark drawdown periods
        if len(bench_ret) > 20 and not bench_prices.empty:
            bench_cummax = bench_prices.cummax()
            bench_dd = (bench_prices - bench_cummax) / bench_cummax
            # Periods where benchmark is in drawdown > 5%
            dd_mask = bench_dd < -0.05
            # Align mask with returns
            dd_mask_aligned = dd_mask.reindex(aligned.index).fillna(False)
            if dd_mask_aligned.sum() > 10:
                dd_stock = stock_ret[dd_mask_aligned]
                dd_bench = bench_ret[dd_mask_aligned]
                result["drawdown_correlation"] = _round(float(dd_stock.corr(dd_bench)))
            else:
                result["drawdown_correlation"] = None
        else:
            result["drawdown_correlation"] = None

        # Sector ETF correlation
        if sector and sector in SECTOR_ETF_MAP:
            try:
                sector_etf = SECTOR_ETF_MAP[sector]
                sector_df = self.market.get_price_history(sector_etf, period="2y")
                if not sector_df.empty:
                    sector_ret = sector_df["Close"].pct_change().dropna()
                    combined = pd.concat([returns, sector_ret], axis=1, join="inner")
                    combined.columns = ["stock", "sector"]
                    if len(combined) > 20:
                        result["sector_etf"] = sector_etf
                        result["sector_correlation"] = _round(float(combined["stock"].corr(combined["sector"])))
                    else:
                        result["sector_etf"] = sector_etf
                        result["sector_correlation"] = None
                else:
                    result["sector_etf"] = None
                    result["sector_correlation"] = None
            except Exception as exc:
                logger.warning("Sector correlation failed: %s", exc)
                result["sector_etf"] = None
                result["sector_correlation"] = None
        else:
            result["sector_etf"] = None
            result["sector_correlation"] = None

        return result

    # -----------------------------------------------------------------------
    # 7. Risk Classification
    # -----------------------------------------------------------------------
    @staticmethod
    def _risk_classification(result: dict[str, Any]) -> dict[str, Any]:
        """Produce a composite risk score (0-100, 100 = least risky) and tier."""
        basic = result.get("basic_metrics", {})
        tail = result.get("tail_risk", {})
        factor = result.get("factor_model", {})
        rolling = result.get("rolling_risk", {})

        flags: list[str] = []
        score_components: dict[str, float] = {}

        # --- Volatility component (0-30 points) ---
        vol = basic.get("annualized_volatility", 0.3)
        # Map: <10% vol -> 30pts, >60% vol -> 0pts
        vol_score = max(0.0, min(30.0, 30.0 * (1.0 - (vol - 0.10) / 0.50)))
        score_components["volatility"] = _round(vol_score, 2)
        if vol > 0.40:
            flags.append("high_volatility")

        # --- Drawdown component (0-25 points) ---
        max_dd = abs(basic.get("max_drawdown", -0.2))
        # Map: <10% dd -> 25pts, >50% dd -> 0pts
        dd_score = max(0.0, min(25.0, 25.0 * (1.0 - (max_dd - 0.10) / 0.40)))
        score_components["drawdown"] = _round(dd_score, 2)
        if max_dd > 0.30:
            flags.append("severe_drawdown")

        # --- Tail risk component (0-20 points) ---
        skew = tail.get("skewness", 0.0)
        kurt = tail.get("excess_kurtosis", 0.0)

        tail_score = 20.0
        if skew < -0.5:
            tail_score -= min(10.0, abs(skew) * 5.0)
            flags.append("negative_skew")
        if kurt > 3.0:
            tail_score -= min(10.0, (kurt - 3.0) * 2.0)
            flags.append("fat_tails")
        tail_score = max(0.0, tail_score)
        score_components["tail_risk"] = _round(tail_score, 2)

        # --- Beta / factor concentration component (0-15 points) ---
        beta = basic.get("beta", 1.0)
        # Map: beta 0.5->15, beta 2.0->0
        beta_score = max(0.0, min(15.0, 15.0 * (1.0 - (abs(beta) - 0.5) / 1.5)))
        score_components["beta"] = _round(beta_score, 2)
        if abs(beta) > 1.5:
            flags.append("high_beta")

        factor_betas = factor.get("factor_betas", {})
        if factor_betas:
            size_exp = abs(factor_betas.get("size_smb", 0.0))
            value_exp = abs(factor_betas.get("value_hml", 0.0))
            mom_exp = abs(factor_betas.get("momentum", 0.0))
            if max(size_exp, value_exp, mom_exp) > 0.5:
                flags.append("factor_concentration")

        # --- Risk-adjusted return bonus (0-10 points) ---
        sharpe = basic.get("sharpe_ratio", 0.0)
        # Map: sharpe < 0 -> 0pts, sharpe > 2 -> 10pts
        sharpe_score = max(0.0, min(10.0, sharpe * 5.0))
        score_components["risk_adjusted_return"] = _round(sharpe_score, 2)

        # --- Regime shift penalty ---
        if rolling.get("regime_shift_detected", False):
            flags.append("regime_shift")

        # Composite score
        raw_score = sum(score_components.values())
        # Apply regime-shift penalty
        if "regime_shift" in flags:
            raw_score = max(0.0, raw_score - 5.0)

        risk_score = _round(max(0.0, min(100.0, raw_score)), 1)

        # Tier
        if risk_score >= 75:
            tier = "CONSERVATIVE"
        elif risk_score >= 50:
            tier = "MODERATE"
        elif risk_score >= 25:
            tier = "AGGRESSIVE"
        else:
            tier = "SPECULATIVE"

        return {
            "risk_score": risk_score,
            "risk_tier": tier,
            "risk_flags": flags,
            "score_components": score_components,
        }

    # ===================================================================
    # Static helper methods
    # ===================================================================

    @staticmethod
    def _annualized_volatility(returns: pd.Series) -> float:
        return _round(float(returns.std()) * np.sqrt(TRADING_DAYS))

    @staticmethod
    def _sharpe_ratio(returns: pd.Series, rf_daily: float) -> float:
        excess = returns - rf_daily
        std = float(excess.std())
        if std == 0:
            return 0.0
        return _round(float(excess.mean()) / std * np.sqrt(TRADING_DAYS))

    @staticmethod
    def _sortino_ratio(returns: pd.Series, rf_daily: float) -> float:
        excess = returns - rf_daily
        downside = excess[excess < 0]
        ds_std = float(downside.std())
        if ds_std == 0:
            return 0.0
        return _round(float(excess.mean()) / ds_std * np.sqrt(TRADING_DAYS))

    @staticmethod
    def _max_drawdown(prices: pd.Series) -> float:
        cummax = prices.cummax()
        drawdown = (prices - cummax) / cummax
        return _round(float(drawdown.min()))

    @staticmethod
    def _max_drawdown_duration(prices: pd.Series) -> int:
        """Return the longest drawdown duration in trading days."""
        cummax = prices.cummax()
        in_drawdown = prices < cummax
        if not in_drawdown.any():
            return 0
        # Group consecutive drawdown days
        groups = (~in_drawdown).cumsum()
        dd_groups = groups[in_drawdown]
        if dd_groups.empty:
            return 0
        durations = dd_groups.groupby(dd_groups).count()
        return int(durations.max())

    @staticmethod
    def _beta(stock_returns: pd.Series, bench_returns: pd.Series) -> float:
        if len(bench_returns) < 2:
            return 0.0
        cov = float(stock_returns.cov(bench_returns))
        var = float(bench_returns.var())
        if var == 0:
            return 0.0
        return _round(cov / var)

    @staticmethod
    def _tracking_error(stock_returns: pd.Series, bench_returns: pd.Series) -> float:
        if len(stock_returns) < 2:
            return 0.0
        diff = stock_returns - bench_returns
        return _round(float(diff.std()) * np.sqrt(TRADING_DAYS))

    @staticmethod
    def _value_at_risk(returns: pd.Series, confidence: float = 0.95) -> float:
        return _round(float(np.percentile(returns, (1 - confidence) * 100)))

    @staticmethod
    def _conditional_var(returns: pd.Series, confidence: float = 0.95) -> float:
        var = np.percentile(returns, (1 - confidence) * 100)
        tail = returns[returns <= var]
        if tail.empty:
            return _round(float(var))
        return _round(float(tail.mean()))


# ---------------------------------------------------------------------------
# Plugin adapter for pipeline
# ---------------------------------------------------------------------------
from src.analysis.base import BaseAnalyzer as _BaseAnalyzer  # noqa: E402


class RiskAnalyzerPlugin(_BaseAnalyzer):
    """Pipeline-compatible adapter for :class:`RiskAnalyzer`."""

    name = "risk"
    default_weight = 0.15

    def __init__(self) -> None:
        self._analyzer = RiskAnalyzer()

    def analyze(self, ticker: str, ctx: Any) -> dict[str, Any]:
        """Run full risk analysis and return results with a ``score`` key.

        Parameters
        ----------
        ticker : str
            Stock symbol.
        ctx : PipelineContext
            Pipeline context (used to look up sector metadata if available).
        """
        # Attempt to pull sector from pipeline context metadata
        sector: str | None = None
        if ctx is not None:
            meta = getattr(ctx, "company_meta", {})
            ticker_meta = meta.get(ticker, {})
            sector = ticker_meta.get("sector")

        result = self._analyzer.analyze(ticker, sector=sector)

        # Ensure top-level "score" key exists (required by BaseAnalyzer contract)
        if "score" not in result:
            result["score"] = 50.0
        return result

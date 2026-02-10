"""Portfolio construction, optimization, and analysis.

Provides hedge-fund-grade portfolio construction tools including mean-variance
optimization (Markowitz), risk parity, Black-Litterman, position sizing via
Kelly criterion and volatility targeting, and full portfolio analytics with
efficient frontier computation.

This is a standalone utility module (no pipeline plugin adapter).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.optimize import minimize

from src.data_sources.market_data import MarketDataClient
from src.utils.logger import setup_logger

logger = setup_logger("portfolio")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TRADING_DAYS = 252


def _to_float(val: Any) -> float:
    """Coerce numpy/pandas scalar to plain float for JSON serialization."""
    return round(float(val), 6)


def _regularize_cov(cov: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    """Add small ridge to diagonal to avoid singular covariance matrices."""
    return cov + np.eye(cov.shape[0]) * eps


def _fetch_returns(
    market: MarketDataClient,
    tickers: list[str],
    period: str = "2y",
) -> pd.DataFrame:
    """Fetch daily returns for a list of tickers, aligned on common dates.

    Returns a DataFrame whose columns are tickers and rows are daily returns.
    """
    frames: dict[str, pd.Series] = {}
    for t in tickers:
        df = market.get_price_history(t, period=period)
        if df.empty:
            logger.warning("No price data for %s, skipping", t)
            continue
        frames[t] = df["Close"].pct_change().dropna()

    if not frames:
        raise ValueError("No valid price data for any of the supplied tickers")

    combined = pd.concat(frames, axis=1, join="inner")
    combined.columns = list(frames.keys())

    if combined.empty:
        raise ValueError("No overlapping dates across the supplied tickers")

    return combined


# =========================================================================
# 1. PortfolioOptimizer
# =========================================================================


class PortfolioOptimizer:
    """Construct optimal portfolios using various methodologies."""

    def __init__(self, period: str = "2y") -> None:
        self.market = MarketDataClient()
        self.period = period

    # ----- internal helpers ------------------------------------------------

    def _get_return_stats(
        self, tickers: list[str]
    ) -> tuple[np.ndarray, np.ndarray, list[str]]:
        """Return (mean_annual_returns, cov_annual, valid_tickers)."""
        returns_df = _fetch_returns(self.market, tickers, period=self.period)
        valid_tickers = list(returns_df.columns)
        mean_daily = returns_df.mean().values
        cov_daily = returns_df.cov().values

        mu = mean_daily * _TRADING_DAYS
        cov = _regularize_cov(cov_daily * _TRADING_DAYS)
        return mu, cov, valid_tickers

    @staticmethod
    def _portfolio_return(weights: np.ndarray, mu: np.ndarray) -> float:
        return float(weights @ mu)

    @staticmethod
    def _portfolio_volatility(weights: np.ndarray, cov: np.ndarray) -> float:
        return float(np.sqrt(weights @ cov @ weights))

    # ----- 1a. Mean-Variance Optimization ---------------------------------

    def optimize_mean_variance(
        self,
        tickers: list[str],
        target_return: float | None = None,
        risk_free_rate: float = 0.04,
    ) -> dict:
        """Markowitz mean-variance optimization.

        If *target_return* is given, minimise variance subject to achieving
        that return.  Otherwise find the maximum-Sharpe-ratio (tangency)
        portfolio.  Also always computes the global minimum-variance portfolio.

        Args:
            tickers: List of stock symbols.
            target_return: Desired annual portfolio return (e.g. 0.12 for 12 %).
            risk_free_rate: Annual risk-free rate for Sharpe calculation.

        Returns:
            Dict with optimal_weights, expected_return, expected_volatility,
            sharpe_ratio, and the min_variance_portfolio.
        """
        mu, cov, valid = self._get_return_stats(tickers)
        n = len(valid)

        if n == 1:
            return self._single_asset_result(valid[0], mu[0], cov[0, 0], risk_free_rate)

        bounds = tuple((0.0, 1.0) for _ in range(n))
        sum_to_one = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
        w0 = np.ones(n) / n

        # -- minimum-variance portfolio ------------------------------------
        def variance_obj(w: np.ndarray) -> float:
            return float(w @ cov @ w)

        min_var_res = minimize(
            variance_obj, w0, method="SLSQP", bounds=bounds,
            constraints=[sum_to_one], options={"maxiter": 1000, "ftol": 1e-12},
        )
        mv_weights = min_var_res.x
        mv_ret = self._portfolio_return(mv_weights, mu)
        mv_vol = self._portfolio_volatility(mv_weights, cov)
        mv_sharpe = (mv_ret - risk_free_rate) / mv_vol if mv_vol > 0 else 0.0

        min_variance_portfolio = {
            "weights": {valid[i]: _to_float(mv_weights[i]) for i in range(n)},
            "expected_return": _to_float(mv_ret),
            "expected_volatility": _to_float(mv_vol),
            "sharpe_ratio": _to_float(mv_sharpe),
        }

        # -- optimal portfolio (target-return or max-Sharpe) ---------------
        if target_return is not None:
            ret_constraint = {
                "type": "eq",
                "fun": lambda w: w @ mu - target_return,
            }
            opt_res = minimize(
                variance_obj, w0, method="SLSQP", bounds=bounds,
                constraints=[sum_to_one, ret_constraint],
                options={"maxiter": 1000, "ftol": 1e-12},
            )
        else:
            # maximise Sharpe  =>  minimise negative Sharpe
            def neg_sharpe(w: np.ndarray) -> float:
                ret = w @ mu
                vol = np.sqrt(w @ cov @ w)
                if vol < 1e-12:
                    return 1e6
                return -(ret - risk_free_rate) / vol

            opt_res = minimize(
                neg_sharpe, w0, method="SLSQP", bounds=bounds,
                constraints=[sum_to_one], options={"maxiter": 1000, "ftol": 1e-12},
            )

        opt_w = opt_res.x
        opt_ret = self._portfolio_return(opt_w, mu)
        opt_vol = self._portfolio_volatility(opt_w, cov)
        opt_sharpe = (opt_ret - risk_free_rate) / opt_vol if opt_vol > 0 else 0.0

        return {
            "method": "mean_variance",
            "tickers": valid,
            "optimal_weights": {valid[i]: _to_float(opt_w[i]) for i in range(n)},
            "expected_return": _to_float(opt_ret),
            "expected_volatility": _to_float(opt_vol),
            "sharpe_ratio": _to_float(opt_sharpe),
            "risk_free_rate": risk_free_rate,
            "target_return": target_return,
            "min_variance_portfolio": min_variance_portfolio,
        }

    # ----- 1b. Risk Parity ------------------------------------------------

    def optimize_risk_parity(self, tickers: list[str]) -> dict:
        """Risk-parity portfolio: equalise each asset's contribution to risk.

        Marginal risk contribution for asset *i*:
            MRC_i = w_i * (Cov @ w)_i / sigma_p

        We minimise the sum of squared differences between each MRC and
        the target (sigma_p / n).

        Returns:
            Dict with weights, risk_contributions, and total_risk.
        """
        mu, cov, valid = self._get_return_stats(tickers)
        n = len(valid)

        if n == 1:
            vol = float(np.sqrt(cov[0, 0]))
            return {
                "method": "risk_parity",
                "tickers": valid,
                "weights": {valid[0]: 1.0},
                "risk_contributions": {valid[0]: 1.0},
                "total_risk": _to_float(vol),
            }

        def _risk_contrib(w: np.ndarray) -> np.ndarray:
            port_vol = np.sqrt(w @ cov @ w)
            if port_vol < 1e-12:
                return np.zeros(n)
            marginal = (cov @ w) * w / port_vol
            return marginal

        def _objective(w: np.ndarray) -> float:
            rc = _risk_contrib(w)
            target = np.mean(rc)
            return float(np.sum((rc - target) ** 2))

        bounds = tuple((1e-6, 1.0) for _ in range(n))
        sum_to_one = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
        w0 = np.ones(n) / n

        res = minimize(
            _objective, w0, method="SLSQP", bounds=bounds,
            constraints=[sum_to_one], options={"maxiter": 1000, "ftol": 1e-14},
        )
        opt_w = res.x
        rc = _risk_contrib(opt_w)
        total_risk = self._portfolio_volatility(opt_w, cov)

        # normalise risk contributions to fractions of total
        rc_sum = rc.sum()
        rc_frac = rc / rc_sum if rc_sum > 0 else np.ones(n) / n

        return {
            "method": "risk_parity",
            "tickers": valid,
            "weights": {valid[i]: _to_float(opt_w[i]) for i in range(n)},
            "risk_contributions": {valid[i]: _to_float(rc_frac[i]) for i in range(n)},
            "total_risk": _to_float(total_risk),
        }

    # ----- 1c. Black-Litterman -------------------------------------------

    def optimize_black_litterman(
        self,
        tickers: list[str],
        views: list[dict[str, Any]],
        view_confidences: list[float],
        market_caps: dict[str, float] | None = None,
        risk_free_rate: float = 0.04,
        tau: float = 0.05,
    ) -> dict:
        """Simplified Black-Litterman model.

        Combines market-implied equilibrium returns with subjective investor
        views to produce posterior expected returns, then optimises weights.

        Args:
            tickers: List of stock symbols.
            views: List of dicts ``{"ticker": str, "expected_return": float}``.
            view_confidences: Confidence in each view (0-1 scale, higher = more
                confident).  Length must match *views*.
            market_caps: Optional market-cap dict ``{ticker: cap}``.  If None,
                fetched via yfinance.
            risk_free_rate: Annual risk-free rate.
            tau: Scaling factor for uncertainty of equilibrium returns.

        Returns:
            Dict with posterior_returns, optimal_weights.
        """
        mu, cov, valid = self._get_return_stats(tickers)
        n = len(valid)
        ticker_idx = {t: i for i, t in enumerate(valid)}

        # -- market-implied equilibrium returns (pi) -----------------------
        if market_caps is None:
            market_caps = {}
            for t in valid:
                try:
                    info = yf.Ticker(t).fast_info
                    market_caps[t] = float(info.market_cap)
                except Exception:
                    market_caps[t] = 1.0  # fallback equal weight
                    logger.warning("Could not fetch market cap for %s", t)

        caps = np.array([market_caps.get(t, 1.0) for t in valid])
        w_mkt = caps / caps.sum()

        # risk aversion coefficient delta:  delta = (mu_mkt - rf) / var_mkt
        mkt_ret = float(w_mkt @ mu)
        mkt_var = float(w_mkt @ cov @ w_mkt)
        delta = (mkt_ret - risk_free_rate) / mkt_var if mkt_var > 0 else 2.5

        pi = delta * cov @ w_mkt  # equilibrium excess returns

        # -- pick matrix P and view vector Q --------------------------------
        k = len(views)
        if k == 0 or k != len(view_confidences):
            raise ValueError(
                "views and view_confidences must be non-empty and same length"
            )

        P = np.zeros((k, n))
        Q = np.zeros(k)
        for vi, view in enumerate(views):
            t = view["ticker"]
            if t not in ticker_idx:
                raise ValueError(f"View ticker '{t}' not in valid tickers {valid}")
            P[vi, ticker_idx[t]] = 1.0
            Q[vi] = view["expected_return"]

        # -- Omega: diagonal uncertainty of views --------------------------
        #   confidence=1 => very certain => small variance
        omega_diag = np.array([
            tau * (P[i] @ cov @ P[i].T) / max(c, 0.01)
            for i, c in enumerate(view_confidences)
        ])
        Omega = np.diag(omega_diag)

        # -- posterior returns ---------------------------------------------
        tau_cov = tau * cov
        tau_cov_inv = np.linalg.inv(tau_cov)
        Omega_inv = np.linalg.inv(Omega)

        posterior_cov = np.linalg.inv(tau_cov_inv + P.T @ Omega_inv @ P)
        posterior_mu = posterior_cov @ (tau_cov_inv @ pi + P.T @ Omega_inv @ Q)

        # -- optimise weights using posterior returns ----------------------
        def neg_sharpe(w: np.ndarray) -> float:
            ret = w @ posterior_mu
            vol = np.sqrt(w @ cov @ w)
            if vol < 1e-12:
                return 1e6
            return -(ret - risk_free_rate) / vol

        bounds = tuple((0.0, 1.0) for _ in range(n))
        sum_to_one = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
        w0 = np.ones(n) / n

        opt_res = minimize(
            neg_sharpe, w0, method="SLSQP", bounds=bounds,
            constraints=[sum_to_one], options={"maxiter": 1000, "ftol": 1e-12},
        )
        opt_w = opt_res.x
        opt_ret = float(opt_w @ posterior_mu)
        opt_vol = self._portfolio_volatility(opt_w, cov)

        return {
            "method": "black_litterman",
            "tickers": valid,
            "posterior_returns": {valid[i]: _to_float(posterior_mu[i]) for i in range(n)},
            "equilibrium_returns": {valid[i]: _to_float(pi[i]) for i in range(n)},
            "optimal_weights": {valid[i]: _to_float(opt_w[i]) for i in range(n)},
            "expected_return": _to_float(opt_ret),
            "expected_volatility": _to_float(opt_vol),
            "tau": tau,
            "delta": _to_float(delta),
        }

    # ----- 1d. Equal Risk Contribution ------------------------------------

    def optimize_equal_risk(
        self,
        tickers: list[str],
        risk_budgets: list[float] | None = None,
    ) -> dict:
        """Equal-risk-contribution (generalised risk parity).

        If *risk_budgets* is provided, each asset's risk contribution is
        proportional to its budget.  Default: equal budget for all assets.

        Returns:
            Dict with weights, risk_contributions, risk_budgets, total_risk.
        """
        mu, cov, valid = self._get_return_stats(tickers)
        n = len(valid)

        if risk_budgets is None:
            budgets = np.ones(n) / n
        else:
            if len(risk_budgets) != n:
                raise ValueError("risk_budgets length must equal number of tickers")
            budgets = np.array(risk_budgets, dtype=float)
            budgets = budgets / budgets.sum()  # normalise

        if n == 1:
            vol = float(np.sqrt(cov[0, 0]))
            return {
                "method": "equal_risk_contribution",
                "tickers": valid,
                "weights": {valid[0]: 1.0},
                "risk_contributions": {valid[0]: 1.0},
                "risk_budgets": {valid[0]: 1.0},
                "total_risk": _to_float(vol),
            }

        def _objective(w: np.ndarray) -> float:
            port_vol = np.sqrt(w @ cov @ w)
            if port_vol < 1e-12:
                return 1e6
            rc = (cov @ w) * w / port_vol
            rc_frac = rc / rc.sum() if rc.sum() > 0 else np.ones(n) / n
            return float(np.sum((rc_frac - budgets) ** 2))

        bounds = tuple((1e-6, 1.0) for _ in range(n))
        sum_to_one = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
        w0 = np.ones(n) / n

        res = minimize(
            _objective, w0, method="SLSQP", bounds=bounds,
            constraints=[sum_to_one], options={"maxiter": 1000, "ftol": 1e-14},
        )
        opt_w = res.x
        port_vol = self._portfolio_volatility(opt_w, cov)

        rc = (cov @ opt_w) * opt_w / port_vol if port_vol > 0 else np.zeros(n)
        rc_sum = rc.sum()
        rc_frac = rc / rc_sum if rc_sum > 0 else np.ones(n) / n

        return {
            "method": "equal_risk_contribution",
            "tickers": valid,
            "weights": {valid[i]: _to_float(opt_w[i]) for i in range(n)},
            "risk_contributions": {valid[i]: _to_float(rc_frac[i]) for i in range(n)},
            "risk_budgets": {valid[i]: _to_float(budgets[i]) for i in range(n)},
            "total_risk": _to_float(port_vol),
        }

    # ----- helpers (single-asset edge case) --------------------------------

    @staticmethod
    def _single_asset_result(
        ticker: str, mu_val: float, var_val: float, rf: float
    ) -> dict:
        vol = float(np.sqrt(var_val))
        sharpe = (mu_val - rf) / vol if vol > 0 else 0.0
        single = {
            "weights": {ticker: 1.0},
            "expected_return": _to_float(mu_val),
            "expected_volatility": _to_float(vol),
            "sharpe_ratio": _to_float(sharpe),
        }
        return {
            "method": "mean_variance",
            "tickers": [ticker],
            "optimal_weights": {ticker: 1.0},
            "expected_return": _to_float(mu_val),
            "expected_volatility": _to_float(vol),
            "sharpe_ratio": _to_float(sharpe),
            "risk_free_rate": rf,
            "target_return": None,
            "min_variance_portfolio": single,
        }


# =========================================================================
# 2. PositionSizer
# =========================================================================


class PositionSizer:
    """Determine how much capital to allocate to a single position."""

    def __init__(self) -> None:
        self.market = MarketDataClient()

    # ----- 2a. Kelly Criterion --------------------------------------------

    @staticmethod
    def kelly_size(
        win_rate: float,
        avg_win: float,
        avg_loss: float,
    ) -> dict:
        """Optimal position size via the Kelly criterion.

        Full Kelly: f* = (p*b - q) / b
            where p = win_rate, q = 1 - p, b = avg_win / avg_loss

        Half Kelly (recommended for real trading) = f* / 2.

        Args:
            win_rate: Historical probability of a winning trade (0-1).
            avg_win:  Average profit on winning trades (as positive float).
            avg_loss: Average loss on losing trades (as positive float).

        Returns:
            Dict with full_kelly_fraction, half_kelly_fraction,
            recommended_pct.
        """
        if avg_loss <= 0:
            raise ValueError("avg_loss must be positive")
        if not 0.0 <= win_rate <= 1.0:
            raise ValueError("win_rate must be between 0 and 1")

        p = win_rate
        q = 1.0 - p
        b = avg_win / avg_loss

        full_kelly = (p * b - q) / b if b > 0 else 0.0
        full_kelly = max(full_kelly, 0.0)  # never recommend negative sizing
        half_kelly = full_kelly / 2.0

        return {
            "full_kelly_fraction": _to_float(full_kelly),
            "half_kelly_fraction": _to_float(half_kelly),
            "recommended_pct": _to_float(half_kelly * 100),
            "edge": _to_float(p * b - q),
            "win_rate": _to_float(p),
            "payoff_ratio": _to_float(b),
        }

    # ----- 2b. Volatility-Based Sizing ------------------------------------

    def vol_size(
        self,
        ticker: str,
        target_vol: float = 0.15,
        portfolio_value: float = 100_000.0,
        period: str = "1y",
    ) -> dict:
        """Size a position so it contributes *target_vol* to the portfolio.

        Position dollar amount = (target_vol * portfolio_value) /
                                 asset_annualised_vol

        Args:
            ticker: Stock symbol.
            target_vol: Target annualised volatility contribution (e.g. 0.15).
            portfolio_value: Total portfolio value in dollars.
            period: Lookback period for volatility estimate.

        Returns:
            Dict with shares, dollar_amount, pct_of_portfolio.
        """
        df = self.market.get_price_history(ticker, period=period)
        if df.empty:
            raise ValueError(f"No price data for {ticker}")

        returns = df["Close"].pct_change().dropna()
        asset_vol = float(returns.std() * np.sqrt(_TRADING_DAYS))
        price = float(df["Close"].iloc[-1])

        if asset_vol < 1e-10:
            logger.warning("Asset %s has near-zero volatility", ticker)
            dollar_amount = portfolio_value
        else:
            dollar_amount = (target_vol * portfolio_value) / asset_vol

        shares = int(dollar_amount / price) if price > 0 else 0
        actual_dollar = shares * price
        pct = actual_dollar / portfolio_value if portfolio_value > 0 else 0.0

        return {
            "ticker": ticker,
            "shares": shares,
            "dollar_amount": _to_float(actual_dollar),
            "pct_of_portfolio": _to_float(pct * 100),
            "asset_volatility": _to_float(asset_vol),
            "current_price": _to_float(price),
            "target_vol": target_vol,
            "portfolio_value": _to_float(portfolio_value),
        }

    # ----- 2c. Risk-Based Sizing ------------------------------------------

    def risk_size(
        self,
        ticker: str,
        max_loss_pct: float = 0.02,
        stop_loss_pct: float = 0.05,
        portfolio_value: float = 100_000.0,
    ) -> dict:
        """Size a position using a fixed-risk / stop-loss approach.

        Max loss per trade = portfolio_value * max_loss_pct
        Position size (dollars) = max_loss / stop_loss_pct
        Shares = dollar_amount / price

        Args:
            ticker: Stock symbol.
            max_loss_pct: Maximum acceptable loss as fraction of portfolio
                (e.g. 0.02 = 2 %).
            stop_loss_pct: Distance to stop-loss as fraction of entry price
                (e.g. 0.05 = 5 % below entry).
            portfolio_value: Total portfolio value in dollars.

        Returns:
            Dict with shares, dollar_amount, max_loss_dollars.
        """
        price_info = self.market.get_current_price(ticker)
        price = float(price_info["price"])

        if price <= 0:
            raise ValueError(f"Invalid price for {ticker}: {price}")
        if stop_loss_pct <= 0:
            raise ValueError("stop_loss_pct must be positive")

        max_loss = portfolio_value * max_loss_pct
        dollar_amount = max_loss / stop_loss_pct
        shares = int(dollar_amount / price)
        actual_dollar = shares * price

        return {
            "ticker": ticker,
            "shares": shares,
            "dollar_amount": _to_float(actual_dollar),
            "max_loss_dollars": _to_float(max_loss),
            "current_price": _to_float(price),
            "max_loss_pct": max_loss_pct,
            "stop_loss_pct": stop_loss_pct,
            "portfolio_value": _to_float(portfolio_value),
        }


# =========================================================================
# 3. PortfolioAnalyzer
# =========================================================================


class PortfolioAnalyzer:
    """Analyse an existing or proposed portfolio allocation."""

    def __init__(self, period: str = "2y") -> None:
        self.market = MarketDataClient()
        self.period = period

    # ----- 3a. Portfolio Risk Decomposition --------------------------------

    def analyze_portfolio(
        self,
        tickers: list[str],
        weights: list[float],
        risk_free_rate: float = 0.04,
    ) -> dict:
        """Full risk decomposition of a portfolio.

        Returns portfolio return, volatility, Sharpe ratio, correlation
        matrix, individual risk contributions, diversification ratio,
        and concentration metrics (HHI, effective N).

        Args:
            tickers: Stock symbols.
            weights: Portfolio weights (must sum to ~1.0).
            risk_free_rate: Annual risk-free rate.

        Returns:
            Dict with portfolio-level and per-asset analytics.
        """
        if len(tickers) != len(weights):
            raise ValueError("tickers and weights must be the same length")

        w = np.array(weights, dtype=float)
        w = w / w.sum()  # normalise just in case

        returns_df = _fetch_returns(self.market, tickers, period=self.period)
        valid = list(returns_df.columns)
        # align weights to valid tickers
        valid_idx = [tickers.index(t) for t in valid]
        w = np.array([weights[i] for i in valid_idx], dtype=float)
        w = w / w.sum()
        n = len(valid)

        mu = returns_df.mean().values * _TRADING_DAYS
        cov = _regularize_cov(returns_df.cov().values * _TRADING_DAYS)
        vols = np.sqrt(np.diag(cov))

        port_ret = float(w @ mu)
        port_vol = float(np.sqrt(w @ cov @ w))
        sharpe = (port_ret - risk_free_rate) / port_vol if port_vol > 0 else 0.0

        # correlation matrix
        std_outer = np.outer(vols, vols)
        corr = cov / std_outer
        np.fill_diagonal(corr, 1.0)

        # risk contributions
        if port_vol > 0:
            mcr = (cov @ w) / port_vol  # marginal contribution to risk
            rc = w * mcr  # absolute risk contribution
            rc_pct = rc / port_vol  # fraction of total vol
        else:
            mcr = np.zeros(n)
            rc = np.zeros(n)
            rc_pct = np.ones(n) / n

        # diversification ratio
        weighted_vol = float(np.sum(w * vols))
        div_ratio = weighted_vol / port_vol if port_vol > 0 else 1.0

        # concentration
        hhi = float(np.sum(w ** 2))
        effective_n = 1.0 / hhi if hhi > 0 else n

        return {
            "tickers": valid,
            "weights": {valid[i]: _to_float(w[i]) for i in range(n)},
            "portfolio_return": _to_float(port_ret),
            "portfolio_volatility": _to_float(port_vol),
            "sharpe_ratio": _to_float(sharpe),
            "risk_free_rate": risk_free_rate,
            "correlation_matrix": {
                valid[i]: {valid[j]: _to_float(corr[i, j]) for j in range(n)}
                for i in range(n)
            },
            "individual_volatilities": {valid[i]: _to_float(vols[i]) for i in range(n)},
            "marginal_risk_contributions": {valid[i]: _to_float(mcr[i]) for i in range(n)},
            "risk_contributions": {valid[i]: _to_float(rc[i]) for i in range(n)},
            "risk_contribution_pct": {valid[i]: _to_float(rc_pct[i]) for i in range(n)},
            "diversification_ratio": _to_float(div_ratio),
            "hhi": _to_float(hhi),
            "effective_n": _to_float(effective_n),
        }

    # ----- 3b. Sector / Factor Exposure -----------------------------------

    def get_exposures(
        self,
        tickers: list[str],
        weights: list[float],
    ) -> dict:
        """Sector, geographic, and concentration exposures.

        Uses yfinance ``info`` for sector and country data.

        Args:
            tickers: Stock symbols.
            weights: Portfolio weights.

        Returns:
            Dict with sector_allocation, geographic_allocation,
            top_concentrations.
        """
        if len(tickers) != len(weights):
            raise ValueError("tickers and weights must be the same length")

        w = np.array(weights, dtype=float)
        w = w / w.sum()

        sector_alloc: dict[str, float] = {}
        geo_alloc: dict[str, float] = {}
        holdings: list[dict] = []

        for i, t in enumerate(tickers):
            weight = float(w[i])
            sector = "Unknown"
            country = "Unknown"
            try:
                info = yf.Ticker(t).info
                sector = info.get("sector", "Unknown")
                country = info.get("country", "Unknown")
            except Exception:
                logger.warning("Could not fetch info for %s", t)

            sector_alloc[sector] = sector_alloc.get(sector, 0.0) + weight
            geo_alloc[country] = geo_alloc.get(country, 0.0) + weight
            holdings.append({"ticker": t, "weight": _to_float(weight)})

        # round allocations
        sector_alloc = {k: _to_float(v) for k, v in sector_alloc.items()}
        geo_alloc = {k: _to_float(v) for k, v in geo_alloc.items()}

        # top concentrations (top 5 by weight)
        holdings_sorted = sorted(holdings, key=lambda h: h["weight"], reverse=True)
        top5 = holdings_sorted[:5]

        return {
            "sector_allocation": sector_alloc,
            "geographic_allocation": geo_alloc,
            "top_concentrations": top5,
            "num_holdings": len(tickers),
        }

    # ----- 3c. Efficient Frontier -----------------------------------------

    def compute_efficient_frontier(
        self,
        tickers: list[str],
        n_points: int = 50,
        risk_free_rate: float = 0.04,
    ) -> dict:
        """Compute the efficient frontier from min-variance to max-return.

        Also identifies the tangency (max Sharpe) portfolio and the global
        minimum-variance portfolio.

        Args:
            tickers: Stock symbols.
            n_points: Number of points on the frontier.
            risk_free_rate: Annual risk-free rate.

        Returns:
            Dict with frontier (list of point dicts), tangency_portfolio,
            min_variance_portfolio.
        """
        returns_df = _fetch_returns(self.market, tickers, period=self.period)
        valid = list(returns_df.columns)
        n = len(valid)

        mu = returns_df.mean().values * _TRADING_DAYS
        cov = _regularize_cov(returns_df.cov().values * _TRADING_DAYS)

        bounds = tuple((0.0, 1.0) for _ in range(n))
        sum_to_one = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
        w0 = np.ones(n) / n

        def variance_obj(w: np.ndarray) -> float:
            return float(w @ cov @ w)

        # -- global minimum-variance portfolio -----------------------------
        mv_res = minimize(
            variance_obj, w0, method="SLSQP", bounds=bounds,
            constraints=[sum_to_one], options={"maxiter": 1000, "ftol": 1e-12},
        )
        mv_w = mv_res.x
        mv_ret = float(mv_w @ mu)
        mv_vol = float(np.sqrt(mv_w @ cov @ mv_w))

        # -- max-return anchor (highest single-asset return) ---------------
        max_ret = float(np.max(mu))

        # -- tangency portfolio (max Sharpe) --------------------------------
        def neg_sharpe(w: np.ndarray) -> float:
            ret = w @ mu
            vol = np.sqrt(w @ cov @ w)
            if vol < 1e-12:
                return 1e6
            return -(ret - risk_free_rate) / vol

        tan_res = minimize(
            neg_sharpe, w0, method="SLSQP", bounds=bounds,
            constraints=[sum_to_one], options={"maxiter": 1000, "ftol": 1e-12},
        )
        tan_w = tan_res.x
        tan_ret = float(tan_w @ mu)
        tan_vol = float(np.sqrt(tan_w @ cov @ tan_w))
        tan_sharpe = (tan_ret - risk_free_rate) / tan_vol if tan_vol > 0 else 0.0

        # -- trace the frontier from min-var return to max return ----------
        target_returns = np.linspace(mv_ret, max_ret, n_points)
        frontier: list[dict] = []

        for tr in target_returns:
            ret_con = {"type": "eq", "fun": lambda w, _tr=tr: w @ mu - _tr}
            res = minimize(
                variance_obj, w0, method="SLSQP", bounds=bounds,
                constraints=[sum_to_one, ret_con],
                options={"maxiter": 1000, "ftol": 1e-12},
            )
            if not res.success:
                continue
            fw = res.x
            f_ret = float(fw @ mu)
            f_vol = float(np.sqrt(fw @ cov @ fw))
            f_sharpe = (f_ret - risk_free_rate) / f_vol if f_vol > 0 else 0.0

            frontier.append({
                "expected_return": _to_float(f_ret),
                "expected_volatility": _to_float(f_vol),
                "sharpe_ratio": _to_float(f_sharpe),
                "weights": {valid[j]: _to_float(fw[j]) for j in range(n)},
            })

        tangency_portfolio = {
            "weights": {valid[j]: _to_float(tan_w[j]) for j in range(n)},
            "expected_return": _to_float(tan_ret),
            "expected_volatility": _to_float(tan_vol),
            "sharpe_ratio": _to_float(tan_sharpe),
        }

        min_variance_portfolio = {
            "weights": {valid[j]: _to_float(mv_w[j]) for j in range(n)},
            "expected_return": _to_float(mv_ret),
            "expected_volatility": _to_float(mv_vol),
            "sharpe_ratio": _to_float(
                (mv_ret - risk_free_rate) / mv_vol if mv_vol > 0 else 0.0
            ),
        }

        return {
            "tickers": valid,
            "risk_free_rate": risk_free_rate,
            "frontier": frontier,
            "tangency_portfolio": tangency_portfolio,
            "min_variance_portfolio": min_variance_portfolio,
            "n_points": len(frontier),
        }

    # ----- 3d. Rebalancing Analysis ---------------------------------------

    def rebalancing_analysis(
        self,
        tickers: list[str],
        weights: list[float],
        current_prices: dict[str, float],
        current_shares: dict[str, int],
        portfolio_value: float,
        transaction_cost_bps: float = 10.0,
    ) -> dict:
        """Determine trades needed to rebalance toward target weights.

        Args:
            tickers: Stock symbols.
            weights: Target portfolio weights.
            current_prices: ``{ticker: price}`` for each holding.
            current_shares: ``{ticker: num_shares}`` for each holding.
            portfolio_value: Total portfolio value (cash + holdings).
            transaction_cost_bps: Estimated round-trip cost in basis points
                (default 10 bps = 0.10 %).

        Returns:
            Dict with target vs current weights, shares to trade,
            estimated transaction costs, and tracking-error estimate.
        """
        if len(tickers) != len(weights):
            raise ValueError("tickers and weights must be the same length")

        w_target = np.array(weights, dtype=float)
        w_target = w_target / w_target.sum()
        n = len(tickers)

        # current weights
        current_values = np.array([
            current_prices.get(t, 0.0) * current_shares.get(t, 0)
            for t in tickers
        ], dtype=float)
        total_current = current_values.sum()
        w_current = current_values / total_current if total_current > 0 else np.zeros(n)

        trades: list[dict] = []
        total_trade_value = 0.0

        for i, t in enumerate(tickers):
            target_value = w_target[i] * portfolio_value
            current_value = current_values[i]
            price = current_prices.get(t, 0.0)

            delta_value = target_value - current_value
            delta_shares = int(delta_value / price) if price > 0 else 0
            trade_value = abs(delta_shares * price)
            total_trade_value += trade_value

            action = "BUY" if delta_shares > 0 else ("SELL" if delta_shares < 0 else "HOLD")

            trades.append({
                "ticker": t,
                "current_shares": current_shares.get(t, 0),
                "target_shares": current_shares.get(t, 0) + delta_shares,
                "shares_delta": delta_shares,
                "action": action,
                "current_weight": _to_float(w_current[i]),
                "target_weight": _to_float(w_target[i]),
                "weight_delta": _to_float(w_target[i] - w_current[i]),
                "current_value": _to_float(current_value),
                "target_value": _to_float(target_value),
                "trade_value": _to_float(trade_value),
            })

        cost_fraction = transaction_cost_bps / 10_000.0
        total_cost = total_trade_value * cost_fraction

        # tracking error estimate if not rebalanced
        # TE = sqrt( sum( (w_current - w_target)^2 ) ) as a simple proxy
        weight_diff = w_current - w_target
        tracking_error = float(np.sqrt(np.sum(weight_diff ** 2)))

        # Fetch covariance for a more precise TE if we have enough tickers
        precise_te: float | None = None
        if n > 1:
            try:
                returns_df = _fetch_returns(self.market, tickers, period=self.period)
                cov_ann = _regularize_cov(returns_df.cov().values * _TRADING_DAYS)
                # align weight diff to valid columns
                valid_cols = list(returns_df.columns)
                if set(valid_cols) == set(tickers):
                    idx_map = [tickers.index(c) for c in valid_cols]
                    wd = np.array([weight_diff[j] for j in idx_map])
                    precise_te = float(np.sqrt(wd @ cov_ann @ wd))
            except Exception:
                logger.debug("Could not compute precise tracking error")

        turnover = total_trade_value / portfolio_value if portfolio_value > 0 else 0.0

        return {
            "tickers": tickers,
            "trades": trades,
            "total_trade_value": _to_float(total_trade_value),
            "estimated_transaction_cost": _to_float(total_cost),
            "transaction_cost_bps": transaction_cost_bps,
            "turnover": _to_float(turnover),
            "tracking_error_simple": _to_float(tracking_error),
            "tracking_error_precise": _to_float(precise_te) if precise_te is not None else None,
            "portfolio_value": _to_float(portfolio_value),
        }

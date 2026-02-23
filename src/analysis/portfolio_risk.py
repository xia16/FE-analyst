"""Portfolio-level risk analysis - correlation, VaR, concentration, stress testing, factor exposure."""

from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf

from src.data_sources.market_data import MarketDataClient
from src.data_sources.macro_data import MacroDataClient
from src.utils.logger import setup_logger

logger = setup_logger("portfolio_risk")

DEFAULT_STRESS_SCENARIOS: dict[str, tuple[str, str]] = {
    "covid_crash": ("2020-02-19", "2020-03-23"),
    "2022_rate_hike": ("2022-01-03", "2022-06-16"),
    "china_tech_crackdown": ("2021-02-16", "2021-10-04"),
}

FACTOR_ETFS = {"market": "SPY", "size_long": "IWM", "size_short": "SPY",
               "value_long": "IVE", "value_short": "IVW",
               "momentum": "MTUM", "quality": "QUAL"}

COUNTRY_CURRENCY: dict[str, str] = {
    "United States": "USD", "Japan": "JPY", "Netherlands": "EUR",
    "Germany": "EUR", "France": "EUR", "United Kingdom": "GBP",
    "South Korea": "KRW", "Taiwan": "TWD", "China": "CNY",
    "Hong Kong": "HKD", "Canada": "CAD", "Switzerland": "CHF",
    "Australia": "AUD", "Israel": "ILS", "India": "INR",
    "Sweden": "SEK", "Denmark": "DKK", "Singapore": "SGD",
}


class PortfolioRiskAnalyzer:
    """Portfolio-level risk engine complementing the per-stock RiskAnalyzer."""

    def __init__(self):
        self.market = MarketDataClient()
        self._macro = MacroDataClient()

    # ------------------------------------------------------------------
    #  Main entry point
    # ------------------------------------------------------------------
    def analyze(self, holdings: list[dict]) -> dict:
        """Full portfolio risk analysis.  holdings: [{"ticker": str, "weight": float}, ...]"""
        tickers = [h["ticker"] for h in holdings]
        weights = self._normalise_weights([h["weight"] for h in holdings])
        result: dict = {}

        price_data = self._fetch_all_prices(tickers, period="2y")
        returns_df = self._build_returns_df(price_data, tickers)
        valid_tickers, valid_weights = self._align_weights(tickers, weights, returns_df)

        if returns_df.empty or len(valid_tickers) == 0:
            return {"error": "Insufficient price data for portfolio analysis"}

        port_returns = (returns_df[valid_tickers] * valid_weights).sum(axis=1)

        try:
            rf = self._macro.get_risk_free_rate()
        except Exception:
            rf = 0.04
            logger.warning("Risk-free rate unavailable, using %.2f fallback", rf)

        result["portfolio_metrics"] = self._portfolio_metrics(
            port_returns, returns_df, valid_tickers, valid_weights, rf)
        result["var"] = self._compute_var(port_returns)
        result["correlation"] = self._compute_correlation(returns_df, valid_tickers)

        for key, fn in [("concentration", lambda: self.concentration_analysis(holdings)),
                        ("stress_tests", lambda: self.stress_test(holdings)),
                        ("factor_exposure", lambda: self.factor_exposure(holdings))]:
            try:
                result[key] = fn()
            except Exception as exc:
                logger.error("%s failed: %s", key, exc)
                result[key] = {"error": str(exc)}
        return result

    # ------------------------------------------------------------------
    #  Correlation matrix
    # ------------------------------------------------------------------
    def correlation_matrix(self, tickers: list[str], period: str = "2y") -> dict:
        """Pairwise correlation matrix of daily returns."""
        price_data = self._fetch_all_prices(tickers, period=period)
        returns_df = self._build_returns_df(price_data, tickers)
        valid = [t for t in tickers if t in returns_df.columns]
        if len(valid) < 2:
            return {"tickers": valid, "matrix": [], "high_correlation_pairs": []}
        return self._compute_correlation(returns_df, valid)

    # ------------------------------------------------------------------
    #  Portfolio VaR
    # ------------------------------------------------------------------
    def portfolio_var(self, holdings: list[dict], confidence: float = 0.95,
                      period: str = "2y") -> dict:
        """Historical and parametric portfolio VaR at given confidence."""
        tickers = [h["ticker"] for h in holdings]
        weights = self._normalise_weights([h["weight"] for h in holdings])
        price_data = self._fetch_all_prices(tickers, period=period)
        returns_df = self._build_returns_df(price_data, tickers)
        valid_tickers, valid_weights = self._align_weights(tickers, weights, returns_df)
        port_returns = (returns_df[valid_tickers] * valid_weights).sum(axis=1)
        return self._compute_var(port_returns, confidence)

    # ------------------------------------------------------------------
    #  Concentration analysis
    # ------------------------------------------------------------------
    def concentration_analysis(self, holdings: list[dict],
                               profiles: dict | None = None) -> dict:
        """Position, sector, country and currency concentration."""
        weights = self._normalise_weights([h["weight"] for h in holdings])
        sorted_pairs = sorted(zip([h["ticker"] for h in holdings], weights),
                              key=lambda x: x[1], reverse=True)
        top5_weight = float(sum(w for _, w in sorted_pairs[:5]))
        hhi = float((weights ** 2).sum())

        sector_bk: dict[str, float] = {}
        country_bk: dict[str, float] = {}
        currency_bk: dict[str, float] = {}

        for ticker, weight in sorted_pairs:
            sector, country, currency = "Unknown", "Unknown", "USD"
            if profiles and ticker in profiles:
                sector = profiles[ticker].get("sector", "Unknown")
                country = profiles[ticker].get("country", "Unknown")
                currency = COUNTRY_CURRENCY.get(country, "USD")
            else:
                try:
                    info = yf.Ticker(ticker).info
                    sector = info.get("sector", "Unknown")
                    country = info.get("country", "Unknown")
                    currency = COUNTRY_CURRENCY.get(country, "USD")
                except Exception:
                    logger.warning("Could not fetch profile for %s", ticker)
            w = float(weight)
            sector_bk[sector] = sector_bk.get(sector, 0.0) + w
            country_bk[country] = country_bk.get(country, 0.0) + w
            currency_bk[currency] = currency_bk.get(currency, 0.0) + w

        return {
            "top5_weight": round(top5_weight, 4),
            "hhi": round(hhi, 4),
            "sector_breakdown": {k: round(v, 4) for k, v in sector_bk.items()},
            "country_breakdown": {k: round(v, 4) for k, v in country_bk.items()},
            "currency_exposure": {k: round(v, 4) for k, v in currency_bk.items()},
        }

    # ------------------------------------------------------------------
    #  Position sizing (fractional Kelly)
    # ------------------------------------------------------------------
    def position_sizing(self, ticker: str, portfolio_holdings: list[dict],
                        risk_budget: float = 0.02) -> dict:
        """Fractional Kelly + risk-budget position sizing."""
        try:
            df = self.market.get_price_history(ticker, period="2y")
            if df.empty or len(df) < 60:
                return {"error": f"Insufficient data for {ticker}"}
            returns = df["Close"].pct_change().dropna()
            wins = returns[returns > 0]
            losses = returns[returns < 0]

            win_rate = len(wins) / len(returns) if len(returns) > 0 else 0.5
            avg_win = float(wins.mean()) if len(wins) > 0 else 0.0
            avg_loss = float(abs(losses.mean())) if len(losses) > 0 else 1.0

            if avg_loss == 0:
                kelly_pct = 0.0
            else:
                wl = avg_win / avg_loss
                kelly_pct = max(0.0, (win_rate * wl - (1 - win_rate)) / wl)
            half_kelly = kelly_pct / 2.0

            annual_vol = float(returns.std() * np.sqrt(252))
            risk_max = risk_budget / annual_vol if annual_vol > 0 else 0.0
            rec_low = min(half_kelly, risk_max)
            rec_high = min(max(half_kelly, risk_max), 0.25)

            return {
                "ticker": ticker,
                "kelly_pct": round(kelly_pct, 4),
                "half_kelly": round(half_kelly, 4),
                "risk_budget_max": round(risk_max, 4),
                "annual_volatility": round(annual_vol, 4),
                "win_rate": round(win_rate, 4),
                "avg_win": round(avg_win, 6),
                "avg_loss": round(avg_loss, 6),
                "recommended_range": [round(rec_low, 4), round(rec_high, 4)],
            }
        except Exception as exc:
            logger.error("Position sizing failed for %s: %s", ticker, exc)
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    #  Stress testing
    # ------------------------------------------------------------------
    def stress_test(self, holdings: list[dict],
                    scenarios: dict[str, tuple[str, str]] | None = None,
                    period: str = "2y") -> dict:
        """Replay historical stress scenarios on the portfolio."""
        all_scenarios = dict(DEFAULT_STRESS_SCENARIOS)
        if scenarios:
            all_scenarios.update(scenarios)

        tickers = [h["ticker"] for h in holdings]
        weights = self._normalise_weights([h["weight"] for h in holdings])
        price_data = self._fetch_all_prices(tickers, period="max")
        results: dict = {}

        for name, (start_str, end_str) in all_scenarios.items():
            start_dt, end_dt = pd.Timestamp(start_str), pd.Timestamp(end_str)
            per_holding: dict[str, float | str] = {}
            portfolio_return = 0.0
            skipped: list[str] = []

            for ticker, weight in zip(tickers, weights):
                if ticker not in price_data or price_data[ticker].empty:
                    skipped.append(ticker); continue
                df = price_data[ticker]
                sdf = df.loc[(df.index >= start_dt) & (df.index <= end_dt)]
                if len(sdf) < 2:
                    skipped.append(ticker); continue

                ret = (float(sdf["Close"].iloc[-1]) - float(sdf["Close"].iloc[0])) / float(sdf["Close"].iloc[0])
                per_holding[ticker] = round(ret, 4)
                portfolio_return += ret * float(weight)

            worst_dd = self._scenario_drawdown(price_data, tickers, weights, start_dt, end_dt)
            entry: dict = {"portfolio_return": round(portfolio_return, 4),
                           "worst_drawdown": round(worst_dd, 4),
                           "per_holding": per_holding}
            if skipped:
                entry["skipped_tickers"] = skipped
            results[name] = entry
        return results

    # ------------------------------------------------------------------
    #  Factor exposure
    # ------------------------------------------------------------------
    def factor_exposure(self, holdings: list[dict], period: str = "2y") -> dict:
        """Factor decomposition (Market, Size, Value, Momentum, Quality) via OLS."""
        tickers = [h["ticker"] for h in holdings]
        weights = self._normalise_weights([h["weight"] for h in holdings])
        price_data = self._fetch_all_prices(tickers, period=period)
        returns_df = self._build_returns_df(price_data, tickers)
        valid_tickers, valid_weights = self._align_weights(tickers, weights, returns_df)

        if len(valid_tickers) == 0:
            return {"error": "No valid return data for factor analysis"}

        port_returns = (returns_df[valid_tickers] * valid_weights).sum(axis=1)

        # Fetch factor proxy ETFs
        factor_tickers = list(set(FACTOR_ETFS.values()))
        fret = self._build_returns_df(self._fetch_all_prices(factor_tickers, period=period),
                                      factor_tickers)
        if "SPY" not in fret.columns:
            return {"error": "Could not fetch SPY data for factor analysis"}

        factor_series: dict[str, pd.Series] = {"market": fret["SPY"]}
        if "IWM" in fret.columns:
            factor_series["size"] = fret["IWM"] - fret["SPY"]
        if "IVE" in fret.columns and "IVW" in fret.columns:
            factor_series["value"] = fret["IVE"] - fret["IVW"]
        if "MTUM" in fret.columns:
            factor_series["momentum"] = fret["MTUM"]
        if "QUAL" in fret.columns:
            factor_series["quality"] = fret["QUAL"]

        factor_names = list(factor_series.keys())
        combined = pd.concat([port_returns.rename("portfolio"),
                              pd.DataFrame(factor_series)],
                             axis=1, join="inner").dropna()
        if len(combined) < 30:
            return {"error": "Insufficient overlapping data for factor regression"}

        y = combined["portfolio"].values
        X = np.column_stack([np.ones(len(y)), combined[factor_names].values])

        try:
            coeffs, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
        except np.linalg.LinAlgError as exc:
            return {"error": f"Regression failed: {exc}"}

        y_pred = X @ coeffs
        ss_res = float(np.sum((y - y_pred) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        r_sq = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

        result = {n: round(float(b), 4) for n, b in zip(factor_names, coeffs[1:])}
        result["intercept"] = round(float(coeffs[0]), 6)
        result["r_squared"] = round(r_sq, 4)
        return result

    # ==================================================================
    #  Internal helpers
    # ==================================================================

    @staticmethod
    def _normalise_weights(raw: list[float]) -> np.ndarray:
        w = np.array(raw, dtype=float)
        s = w.sum()
        if s > 0 and not np.isclose(s, 1.0):
            logger.warning("Weights sum to %.4f, normalising to 1.0", s)
            w = w / s
        return w

    @staticmethod
    def _align_weights(tickers, weights, returns_df):
        valid = [t for t in tickers if t in returns_df.columns]
        vw = np.array([w for t, w in zip(tickers, weights) if t in returns_df.columns])
        if vw.sum() > 0:
            vw = vw / vw.sum()
        return valid, vw

    def _fetch_all_prices(self, tickers: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
        data: dict[str, pd.DataFrame] = {}
        for ticker in tickers:
            try:
                df = self.market.get_price_history(ticker, period=period)
                if df is not None and not df.empty:
                    data[ticker] = df
                else:
                    logger.warning("Empty price data for %s", ticker)
            except Exception as exc:
                logger.warning("Failed to fetch %s: %s", ticker, exc)
        return data

    @staticmethod
    def _build_returns_df(price_data: dict[str, pd.DataFrame], tickers: list[str]) -> pd.DataFrame:
        series = {}
        for t in tickers:
            if t in price_data and not price_data[t].empty:
                series[t] = price_data[t]["Close"].pct_change().dropna()
        if not series:
            return pd.DataFrame()
        df = pd.DataFrame(series)
        df.dropna(how="all", inplace=True)
        return df

    def _portfolio_metrics(self, port_returns, returns_df, valid_tickers, valid_weights, rf):
        port_vol = float(port_returns.std() * np.sqrt(252))

        rf_daily = rf / 252
        excess = port_returns - rf_daily
        port_sharpe = float(excess.mean() / excess.std() * np.sqrt(252)) if excess.std() > 0 else 0.0

        try:
            spy_df = self.market.get_price_history("SPY", period="2y")
            spy_ret = spy_df["Close"].pct_change().dropna()
            aligned = pd.concat([port_returns.rename("port"), spy_ret.rename("spy")],
                                axis=1, join="inner").dropna()
            var_spy = aligned["spy"].var()
            port_beta = float(aligned["port"].cov(aligned["spy"]) / var_spy) if var_spy > 0 else 1.0
        except Exception:
            port_beta = 1.0
            logger.warning("Could not compute portfolio beta, defaulting to 1.0")

        ind_vols = np.array([float(returns_df[t].std() * np.sqrt(252))
                             if t in returns_df.columns else 0.0 for t in valid_tickers])
        wav = float(np.dot(valid_weights, ind_vols))
        div_ratio = wav / port_vol if port_vol > 0 else 1.0

        return {"total_positions": len(valid_tickers),
                "portfolio_volatility": round(port_vol, 4),
                "portfolio_sharpe": round(port_sharpe, 4),
                "portfolio_beta": round(port_beta, 4),
                "diversification_ratio": round(div_ratio, 4)}

    @staticmethod
    def _compute_var(port_returns: pd.Series, confidence: float = 0.95) -> dict:
        alpha = 1 - confidence
        clean = port_returns.dropna()
        daily_var = float(np.percentile(clean, alpha * 100))
        annual_var = daily_var * np.sqrt(252)
        tail = clean[clean <= daily_var]
        daily_cvar = float(tail.mean()) if len(tail) > 0 else daily_var

        from scipy.stats import norm
        z = norm.ppf(alpha)
        mu, sigma = float(clean.mean()), float(clean.std())
        p_daily = mu + z * sigma
        p_annual = p_daily * np.sqrt(252)

        c = int(confidence * 100)
        return {f"daily_var_{c}": round(daily_var, 6),
                f"annual_var_{c}": round(float(annual_var), 4),
                f"daily_cvar_{c}": round(daily_cvar, 6),
                f"parametric_daily_var_{c}": round(p_daily, 6),
                f"parametric_annual_var_{c}": round(float(p_annual), 4)}

    @staticmethod
    def _compute_correlation(returns_df: pd.DataFrame, tickers: list[str]) -> dict:
        corr = returns_df[tickers].dropna().corr()
        matrix = [[round(float(corr.loc[t1, t2]), 4) for t2 in tickers] for t1 in tickers]

        high_pairs: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for i, t1 in enumerate(tickers):
            for j, t2 in enumerate(tickers):
                if i >= j:
                    continue
                c = float(corr.loc[t1, t2])
                if abs(c) > 0.7:
                    key = (min(t1, t2), max(t1, t2))
                    if key not in seen:
                        seen.add(key)
                        high_pairs.append({"pair": [t1, t2], "correlation": round(c, 4)})
        high_pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)

        return {"tickers": tickers, "matrix": matrix, "high_correlation_pairs": high_pairs}

    def _scenario_drawdown(self, price_data, tickers, weights, start_dt, end_dt) -> float:
        portfolio_values: pd.Series | None = None
        for ticker, weight in zip(tickers, weights):
            if ticker not in price_data or price_data[ticker].empty:
                continue
            prices = price_data[ticker].loc[
                (price_data[ticker].index >= start_dt) & (price_data[ticker].index <= end_dt), "Close"]
            if len(prices) < 2:
                continue
            normed = prices / prices.iloc[0] * float(weight)
            portfolio_values = normed if portfolio_values is None else portfolio_values.add(normed, fill_value=0.0)

        if portfolio_values is None or len(portfolio_values) < 2:
            return 0.0
        cummax = portfolio_values.cummax()
        return float(((portfolio_values - cummax) / cummax).min())

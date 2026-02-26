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

# OTC ADR tickers known to have wide spreads
OTC_ADR_TICKERS = {"HTHIY", "SHECY", "TOELY", "ATEYY", "HOCPY", "LSRCY", "DSCSY", "FANUY"}


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
            try:
                from src.analysis.risk import get_risk_free_rate
                rf = get_risk_free_rate()[0]
            except Exception:
                rf = 0.04
            logger.warning("Risk-free rate from macro unavailable, using %.4f", rf)

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

        # Circuit breaker — assess portfolio drawdown status
        try:
            result["circuit_breaker"] = self._drawdown_circuit_breaker(port_returns)
        except Exception as exc:
            logger.error("Circuit breaker failed: %s", exc)
            result["circuit_breaker"] = {"status": "ERROR", "error": str(exc)}

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

    # ------------------------------------------------------------------
    # Allocation constraints (P8)
    # ------------------------------------------------------------------

    DEFAULT_CONSTRAINTS = {
        "max_single_position": 0.20,
        "max_sector": 0.35,
        "max_country": 0.80,       # High for Japan-thesis portfolios
        "max_correlated_group": 0.40,
        "drawdown_review_threshold": -0.20,
    }

    def check_constraints(self, holdings: list[dict],
                          constraints: dict | None = None) -> dict:
        """Check portfolio against allocation constraints.

        Returns violations (hard limits), warnings (soft limits), and pass/fail.
        """
        c = dict(self.DEFAULT_CONSTRAINTS)
        if constraints:
            c.update(constraints)

        violations: list[dict] = []
        warnings: list[dict] = []

        tickers = [h["ticker"] for h in holdings]
        raw_weights = [h["weight"] for h in holdings]
        total = sum(raw_weights) or 1.0
        weights = [w / total for w in raw_weights]

        # 1. Single position check
        for ticker, w in zip(tickers, weights):
            if w > c["max_single_position"]:
                violations.append({
                    "type": "max_single_position",
                    "ticker": ticker,
                    "weight": round(w, 4),
                    "limit": c["max_single_position"],
                    "detail": f"{ticker} at {w*100:.1f}% exceeds {c['max_single_position']*100:.0f}% limit",
                })

        # 2. Sector / Country concentration
        try:
            conc = self.concentration_analysis(holdings)
            for sector, sw in conc.get("sector_breakdown", {}).items():
                if sw > c["max_sector"]:
                    violations.append({
                        "type": "max_sector",
                        "sector": sector,
                        "weight": round(sw, 4),
                        "limit": c["max_sector"],
                        "detail": f"Sector '{sector}' at {sw*100:.1f}% exceeds {c['max_sector']*100:.0f}% limit",
                    })
            for country, cw in conc.get("country_breakdown", {}).items():
                if cw > c["max_country"]:
                    warnings.append({
                        "type": "max_country",
                        "country": country,
                        "weight": round(cw, 4),
                        "limit": c["max_country"],
                        "detail": f"Country '{country}' at {cw*100:.1f}% exceeds {c['max_country']*100:.0f}% limit",
                    })
        except Exception as e:
            logger.warning("Concentration check failed: %s", e)

        # 3. Correlation-aware group limits
        try:
            corr = self.correlation_matrix(tickers)
            high_pairs = corr.get("high_correlation_pairs", [])
            groups = self._build_correlation_groups(tickers, high_pairs)
            for group in groups:
                group_weight = sum(weights[tickers.index(t)] for t in group if t in tickers)
                if group_weight > c["max_correlated_group"]:
                    warnings.append({
                        "type": "high_correlation_group",
                        "tickers": list(group),
                        "weight": round(group_weight, 4),
                        "limit": c["max_correlated_group"],
                        "detail": f"Correlated group {list(group)} totals {group_weight*100:.1f}%",
                    })
        except Exception as e:
            logger.warning("Correlation constraint check failed: %s", e)

        return {
            "violations": violations,
            "warnings": warnings,
            "violation_count": len(violations),
            "warning_count": len(warnings),
            "passed": len(violations) == 0,
            "constraints_used": c,
        }

    @staticmethod
    def _build_correlation_groups(tickers: list[str], high_pairs: list[dict],
                                   threshold: float = 0.7) -> list[set[str]]:
        """Build groups of tickers correlated above threshold (union-find)."""
        parent = {t: t for t in tickers}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for pair in high_pairs:
            t1, t2 = pair.get("pair", (None, None))
            if t1 and t2 and abs(pair.get("correlation", 0)) >= threshold:
                if t1 in parent and t2 in parent:
                    union(t1, t2)

        groups: dict[str, set[str]] = {}
        for t in tickers:
            root = find(t)
            groups.setdefault(root, set()).add(t)

        return [g for g in groups.values() if len(g) >= 2]

    def _drawdown_circuit_breaker(self, port_returns: pd.Series,
                                   yellow_threshold: float = -0.10,
                                   red_threshold: float = -0.20) -> dict:
        """2-tier circuit breaker with drawdown velocity tracking.

        Yellow (-10%): CAUTION — review positions, tighten stops.
        Red (-20%): REVIEW_REQUIRED — halt new buys, reassess thesis.
        Velocity: rate of drawdown change over last 5 trading days.
        """
        if port_returns.empty or len(port_returns) < 5:
            return {"status": "INSUFFICIENT_DATA"}

        cumulative = (1 + port_returns).cumprod()
        peak = cumulative.cummax()
        drawdown = (cumulative - peak) / peak
        current_dd = float(drawdown.iloc[-1])
        max_dd = float(drawdown.min())

        peak_date = str(peak.idxmax().date()) if hasattr(peak.idxmax(), "date") else str(peak.idxmax())
        trough_idx = drawdown.idxmin()
        trough_date = str(trough_idx.date()) if hasattr(trough_idx, "date") else str(trough_idx)

        # Drawdown velocity: how fast is the drawdown deepening?
        # Measured as change in drawdown over last 5 trading days (annualized).
        dd_velocity = None
        dd_velocity_signal = "STABLE"
        if len(drawdown) >= 6:
            dd_5d = float(drawdown.iloc[-1] - drawdown.iloc[-6])
            dd_velocity = round(dd_5d * 100, 2)  # pct change in 5 days
            if dd_5d < -0.05:  # >5% drawdown deepening in 5 days
                dd_velocity_signal = "RAPID_DETERIORATION"
            elif dd_5d < -0.02:
                dd_velocity_signal = "DETERIORATING"
            elif dd_5d > 0.02:
                dd_velocity_signal = "RECOVERING"

        result = {
            "current_drawdown_pct": round(current_dd * 100, 2),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "peak_date": peak_date,
            "trough_date": trough_date,
            "yellow_threshold_pct": round(yellow_threshold * 100, 2),
            "red_threshold_pct": round(red_threshold * 100, 2),
            "drawdown_velocity_5d_pct": dd_velocity,
            "velocity_signal": dd_velocity_signal,
        }

        if current_dd < red_threshold:
            result["status"] = "RED"
            result["tier"] = "REVIEW_REQUIRED"
            result["detail"] = (
                f"Current drawdown {current_dd*100:.1f}% exceeds red "
                f"threshold ({red_threshold*100:.0f}%). Halt new buys, reassess thesis."
            )
        elif current_dd < yellow_threshold:
            result["status"] = "YELLOW"
            result["tier"] = "CAUTION"
            result["detail"] = (
                f"Current drawdown {current_dd*100:.1f}% exceeds yellow "
                f"threshold ({yellow_threshold*100:.0f}%). Review positions, tighten stops."
            )
        else:
            result["status"] = "GREEN"
            result["tier"] = "OK"

        # Velocity override: rapid deterioration escalates severity
        if dd_velocity_signal == "RAPID_DETERIORATION" and result["status"] == "GREEN":
            result["status"] = "YELLOW"
            result["tier"] = "CAUTION"
            result["detail"] = (
                f"Drawdown velocity warning: {dd_velocity:.1f}% in 5 days. "
                "Portfolio deteriorating rapidly even though absolute level is OK."
            )

        return result

    # ------------------------------------------------------------------
    # Transaction cost model (P7)
    # ------------------------------------------------------------------

    @staticmethod
    def _corwin_schultz_spread(df: pd.DataFrame, window: int = 20) -> float:
        """Corwin-Schultz (2012) high-low spread estimator.

        Uses the 2-period range decomposition to separate spread from volatility:
            beta  = sum of single-day [ln(H/L)]^2 over consecutive pairs
            gamma = [ln(H_2day / L_2day)]^2
            alpha = [sqrt(2*beta) - sqrt(beta)] / k  -  sqrt(gamma / k)
                    where k = 3 - 2*sqrt(2) ≈ 0.1716
            S     = 2*(exp(alpha) - 1) / (1 + exp(alpha))

        Returns estimated percentage spread (e.g. 0.35 means 0.35%).
        """
        h = df["High"].values.astype(float)
        l = df["Low"].values.astype(float)

        # Guard against bad data
        valid = (h > 0) & (l > 0) & (h >= l)
        if valid.sum() < 5:
            return 0.0

        hl_log_sq = np.log(h / np.maximum(l, 1e-10)) ** 2

        # beta: sum of consecutive single-day range-squared
        beta = hl_log_sq[1:] + hl_log_sq[:-1]

        # gamma: 2-day high-low range squared
        h2 = np.maximum(h[1:], h[:-1])
        l2 = np.minimum(l[1:], l[:-1])
        gamma = np.log(h2 / np.maximum(l2, 1e-10)) ** 2

        k = 3.0 - 2.0 * np.sqrt(2.0)  # ≈ 0.1716

        alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / k - np.sqrt(gamma / k)
        alpha = np.maximum(alpha, 0.0)  # Negative alpha → zero spread

        spread = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))

        # Average over trailing window
        tail = spread[-window:] if len(spread) >= window else spread
        avg_spread = float(np.mean(tail)) if len(tail) > 0 else 0.0

        return avg_spread * 100  # Convert to percentage

    def transaction_cost_model(self, ticker: str, trade_value_usd: float = 100_000) -> dict:
        """Estimate transaction costs, especially for OTC ADRs.

        Uses the Corwin-Schultz (2012) 2-period spread estimator for spread,
        and Kyle's lambda sqrt model for market impact.
        """
        try:
            df = self.market.get_price_history(ticker, period="3mo")
            if df.empty:
                return {"error": f"No price data for {ticker}"}

            price = float(df["Close"].iloc[-1])

            # 1. Spread estimation — Corwin-Schultz (2012) 2-period formula
            if "High" in df.columns and "Low" in df.columns and len(df) >= 5:
                avg_spread_pct = self._corwin_schultz_spread(df)
            else:
                avg_spread_pct = 0.5 if ticker in OTC_ADR_TICKERS else 0.1

            # OTC floor: OTC ADRs have at least 0.30% effective spread
            if ticker in OTC_ADR_TICKERS:
                avg_spread_pct = max(avg_spread_pct, 0.30)

            spread_cost_usd = trade_value_usd * avg_spread_pct / 100 / 2  # half-spread

            # 2. Market impact (Kyle's lambda sqrt model)
            vol_20d = float(df["Volume"].tail(20).mean()) if "Volume" in df.columns else 0
            dollar_vol_20d = vol_20d * price

            returns = df["Close"].pct_change().dropna()
            daily_vol = float(returns.std()) if len(returns) > 10 else 0.02

            shares_to_trade = trade_value_usd / price if price > 0 else 0
            participation = shares_to_trade / vol_20d if vol_20d > 0 else 1.0

            import math
            market_impact_pct = daily_vol * math.sqrt(min(participation, 1.0)) * 100
            market_impact_usd = trade_value_usd * market_impact_pct / 100

            # 3. Participation rate limits
            max_participation = 0.10 if ticker in OTC_ADR_TICKERS else 0.25
            max_trade_value = dollar_vol_20d * max_participation

            total_cost_pct = avg_spread_pct / 2 + market_impact_pct

            return {
                "ticker": ticker,
                "is_otc_adr": ticker in OTC_ADR_TICKERS,
                "spread_estimator": "Corwin-Schultz (2012)",
                "estimated_spread_pct": round(avg_spread_pct, 3),
                "spread_cost_usd": round(spread_cost_usd, 2),
                "market_impact_pct": round(market_impact_pct, 3),
                "market_impact_usd": round(market_impact_usd, 2),
                "total_cost_pct": round(total_cost_pct, 3),
                "total_cost_usd": round(spread_cost_usd + market_impact_usd, 2),
                "avg_daily_dollar_volume": round(dollar_vol_20d, 0),
                "participation_rate": round(participation, 4),
                "max_recommended_trade_usd": round(max_trade_value, 0),
                "max_participation_pct": max_participation * 100,
                "warning": "EXCEEDS MAX PARTICIPATION" if trade_value_usd > max_trade_value else None,
            }
        except Exception as e:
            return {"error": str(e)}


# --- Plugin adapter for pipeline ---
from src.analysis.base import BaseAnalyzer as _BaseAnalyzer


class PortfolioRiskAnalyzerPlugin(_BaseAnalyzer):
    """Pipeline adapter for portfolio-level risk analysis.

    Since the plugin API is per-ticker but portfolio analysis is portfolio-level,
    we compute once per unique ticker set and cache the result.
    """
    name = "portfolio_risk"
    default_weight = 0.07

    def __init__(self):
        self._analyzer = PortfolioRiskAnalyzer()
        self._cached_result = None
        self._cached_key = None

    def analyze(self, ticker, ctx):
        tickers = ctx.tickers if ctx.tickers else [ticker]
        tickers_key = tuple(sorted(tickers))

        # Compute once, cache for the rest of the pipeline run
        if self._cached_key != tickers_key:
            n = len(tickers)
            holdings = [{"ticker": t, "weight": 1.0 / n} for t in tickers]
            try:
                self._cached_result = self._analyzer.analyze(holdings)
            except Exception as e:
                logger.warning("Portfolio risk analysis failed: %s", e)
                self._cached_result = {"error": str(e)}
            self._cached_key = tickers_key

        result = dict(self._cached_result)  # shallow copy

        # Compute score from portfolio metrics
        if "error" in result:
            result["score"] = None
            return result

        score = 70.0

        metrics = result.get("portfolio_metrics", {})
        port_vol = metrics.get("portfolio_volatility", 0.2)
        if port_vol > 0.3:
            score -= 20
        elif port_vol > 0.2:
            score -= 10

        div_ratio = metrics.get("diversification_ratio", 1.0)
        if div_ratio > 1.3:
            score += 10
        elif div_ratio < 1.1:
            score -= 10

        conc = result.get("concentration", {})
        hhi = conc.get("hhi", 0)
        if hhi > 0.2:
            score -= 15
        elif hhi > 0.1:
            score -= 5

        # Circuit breaker penalty
        cb = result.get("circuit_breaker", {})
        cb_status = cb.get("status", "OK")
        if cb_status == "RED":
            score -= 25
        elif cb_status == "YELLOW":
            score -= 10

        result["score"] = round(max(0, min(100, score)), 1)
        return result

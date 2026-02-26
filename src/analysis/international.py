"""International stock analysis — ADR premium/discount, FX sensitivity.

Critical for the Japan-heavy AI infrastructure portfolio where most
holdings are ADRs or foreign-listed with significant currency exposure.
"""

import numpy as np
import pandas as pd
import yfinance as yf

from src.data_sources.market_data import MarketDataClient
from src.utils.logger import setup_logger

logger = setup_logger("international")

# ADR → local ticker mapping for key holdings
ADR_LOCAL_MAP = {
    # Japan ADRs
    "TOELY": "6502.T",  # Tokyo Electron
    "8035.T": None,      # Already local
    "FANUY": "6954.T",  # FANUC
    "HTHIY": "6501.T",  # Hitachi
    "SHECY": "4063.T",  # Shin-Etsu Chemical (NOT 6723.T Renesas)
    "ATEYY": "6857.T",  # Advantest
    "HOCPY": "7741.T",  # Hoya
    "LSRCY": "6920.T",  # Lasertec
    "DSCSY": "6146.T",  # Disco
    "SSNLF": "005930.KS",  # Samsung (Korean)
    # European
    "ASML": "ASML.AS",  # ASML Amsterdam
    # Explicitly US-listed (no local pair)
    "NVDA": None,
    "AMD": None,
    "AVGO": None,
    "TSM": "2330.TW",   # TSMC
}

# Currency pairs for FX analysis
CURRENCY_BY_COUNTRY = {
    "Japan": ("JPYUSD=X", "JPY"),
    "Taiwan": ("TWDUSD=X", "TWD"),
    "South Korea": ("KRWUSD=X", "KRW"),
    "Netherlands": ("EURUSD=X", "EUR"),
    "France": ("EURUSD=X", "EUR"),
    "Germany": ("EURUSD=X", "EUR"),
    "China": ("CNYUSD=X", "CNY"),
    "Israel": ("ILSUSD=X", "ILS"),
    "United Kingdom": ("GBPUSD=X", "GBP"),
}


class InternationalAnalyzer:
    """Analyze ADR premium/discount and FX sensitivity."""

    def __init__(self):
        self.market = MarketDataClient()

    def analyze(self, ticker: str, country: str | None = None) -> dict:
        """Full international analysis for a ticker."""
        result = {"ticker": ticker}

        # Determine country if not provided
        if country is None:
            try:
                info = yf.Ticker(ticker).info
                country = info.get("country", "United States")
            except Exception:
                country = "United States"
        result["country"] = country

        # ADR premium/discount
        adr = self._adr_premium(ticker)
        if adr:
            result["adr_analysis"] = adr

        # FX sensitivity
        fx = self._fx_sensitivity(ticker, country)
        if fx:
            result["fx_sensitivity"] = fx

        # Currency info
        if country in CURRENCY_BY_COUNTRY:
            _, currency = CURRENCY_BY_COUNTRY[country]
            result["functional_currency"] = currency
        else:
            result["functional_currency"] = "USD"

        return result

    def _adr_premium(self, ticker: str) -> dict | None:
        """Compute ADR premium/discount vs local listing.

        ADR premium = (ADR price in USD) / (local price × FX rate) - 1
        A positive premium means ADR trades above local; negative = discount.
        """
        local_ticker = ADR_LOCAL_MAP.get(ticker)
        if local_ticker is None:
            return None

        try:
            # Get recent prices for both
            adr_df = self.market.get_price_history(ticker, period="3mo")
            local_df = self.market.get_price_history(local_ticker, period="3mo")

            if adr_df.empty or local_df.empty:
                return {"note": "Insufficient data for ADR comparison"}

            # Get currency info for local ticker
            local_info = yf.Ticker(local_ticker).info
            local_currency = local_info.get("currency", "USD")

            if local_currency == "USD":
                return {"note": "Both listed in USD, no ADR premium analysis needed"}

            # Get FX rate
            fx_pair = f"{local_currency}USD=X"
            try:
                fx_df = self.market.get_price_history(fx_pair, period="3mo")
                if fx_df.empty:
                    # Try inverse
                    fx_pair_inv = f"USD{local_currency}=X"
                    fx_df = self.market.get_price_history(fx_pair_inv, period="3mo")
                    if not fx_df.empty:
                        fx_df["Close"] = 1.0 / fx_df["Close"]
            except Exception:
                return {"note": f"Could not fetch FX rate for {local_currency}"}

            if fx_df.empty:
                return {"note": f"No FX data for {local_currency}/USD"}

            # Align dates
            aligned = pd.concat(
                [adr_df["Close"], local_df["Close"], fx_df["Close"]],
                axis=1, join="inner"
            )
            aligned.columns = ["adr_price", "local_price", "fx_rate"]

            if aligned.empty or len(aligned) < 5:
                return {"note": "Insufficient overlapping data"}

            # Compute ADR premium series
            # ADR ratio (how many local shares per ADR) — approximate from latest prices
            latest = aligned.iloc[-1]
            adr_ratio_approx = latest["adr_price"] / (latest["local_price"] * latest["fx_rate"])
            # Round to nearest common ratio (1, 2, 5, 10, etc.)
            common_ratios = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100]
            adr_ratio = min(common_ratios, key=lambda r: abs(r - adr_ratio_approx))

            # Premium = ADR / (local * FX * ratio) - 1
            aligned["premium"] = (
                aligned["adr_price"] / (aligned["local_price"] * aligned["fx_rate"] * adr_ratio) - 1
            ) * 100

            current_premium = float(aligned["premium"].iloc[-1])
            avg_premium = float(aligned["premium"].mean())
            std_premium = float(aligned["premium"].std())

            return {
                "local_ticker": local_ticker,
                "local_currency": local_currency,
                "adr_ratio": adr_ratio,
                "current_premium_pct": round(current_premium, 2),
                "avg_premium_pct": round(avg_premium, 2),
                "std_premium_pct": round(std_premium, 2),
                "premium_z_score": round(
                    (current_premium - avg_premium) / std_premium, 2
                ) if std_premium > 0 else 0,
                "assessment": (
                    "UNUSUALLY HIGH PREMIUM" if current_premium > avg_premium + 2 * std_premium
                    else "UNUSUALLY LOW (DISCOUNT)" if current_premium < avg_premium - 2 * std_premium
                    else "NORMAL RANGE"
                ),
            }
        except Exception as e:
            logger.warning("ADR premium calculation failed for %s: %s", ticker, e)
            return {"note": f"ADR analysis error: {e}"}

    def _fx_sensitivity(self, ticker: str, country: str) -> dict | None:
        """Estimate FX sensitivity — correlation of stock returns with currency moves."""
        if country not in CURRENCY_BY_COUNTRY:
            return None

        fx_pair, currency = CURRENCY_BY_COUNTRY[country]

        try:
            # Get stock and currency returns
            stock_df = self.market.get_price_history(ticker, period="2y")
            fx_df = self.market.get_price_history(fx_pair, period="2y")

            if stock_df.empty or fx_df.empty:
                return {"currency": currency, "note": "Insufficient data"}

            stock_ret = stock_df["Close"].pct_change().dropna()
            fx_ret = fx_df["Close"].pct_change().dropna()

            # Align
            aligned = pd.concat([stock_ret, fx_ret], axis=1, join="inner")
            aligned.columns = ["stock", "fx"]

            if len(aligned) < 30:
                return {"currency": currency, "note": "Insufficient overlapping data"}

            correlation = float(aligned["stock"].corr(aligned["fx"]))

            # Simple regression: stock_return = alpha + beta * fx_return
            fx_arr = aligned["fx"].values
            stock_arr = aligned["stock"].values
            A = np.column_stack([np.ones(len(fx_arr)), fx_arr])
            result_lstsq = np.linalg.lstsq(A, stock_arr, rcond=None)
            alpha, beta = result_lstsq[0]

            # FX volatility
            fx_vol = float(aligned["fx"].std() * np.sqrt(252))

            return {
                "currency": currency,
                "fx_pair": fx_pair,
                "correlation": round(correlation, 3),
                "fx_beta": round(float(beta), 3),
                "fx_annual_vol": round(fx_vol, 4),
                "assessment": (
                    "HIGH FX SENSITIVITY" if abs(correlation) > 0.4
                    else "MODERATE FX SENSITIVITY" if abs(correlation) > 0.2
                    else "LOW FX SENSITIVITY"
                ),
                "note": (
                    f"A 1% move in {currency}/USD historically corresponds to "
                    f"a {abs(beta):.2f}% move in {ticker}"
                ),
            }
        except Exception as e:
            logger.warning("FX sensitivity failed for %s: %s", ticker, e)
            return {"currency": currency, "note": f"FX analysis error: {e}"}

    # ------------------------------------------------------------------
    # Currency risk extensions
    # ------------------------------------------------------------------

    # Policy rates for hedge cost estimation.
    # Updated: 2026-02-01.  Attempted live refresh via _refresh_policy_rates().
    _POLICY_RATES = {
        "JPY": 0.005,
        "USD": 0.045,
        "EUR": 0.035,
        "TWD": 0.02,
        "KRW": 0.035,
        "CNY": 0.03,
        "GBP": 0.045,
        "ILS": 0.045,
    }
    _POLICY_RATES_UPDATED = "2026-02-01"
    _RATES_STALE_DAYS = 90

    @classmethod
    def _refresh_policy_rates(cls) -> None:
        """Attempt to fetch live short-term yield proxies from yfinance.

        Falls back silently to static rates if fetches fail.
        """
        from datetime import datetime, timedelta

        last = datetime.strptime(cls._POLICY_RATES_UPDATED, "%Y-%m-%d")
        if (datetime.now() - last).days < 30:
            return  # Refreshed recently enough

        # Only refresh USD — ^IRX is a reliable 13-week T-bill proxy.
        # No reliable yfinance proxies exist for JPY/EUR short rates;
        # those stay at manually-maintained static values.
        refreshed = False
        try:
            tk = yf.Ticker("^IRX")  # 13-week T-bill yield (% form)
            hist = tk.history(period="5d")
            if not hist.empty:
                rate_pct = float(hist["Close"].iloc[-1])
                if 0 < rate_pct < 20:
                    cls._POLICY_RATES["USD"] = rate_pct / 100
                    refreshed = True
                    logger.info("USD policy rate refreshed: %.4f from ^IRX", rate_pct / 100)
        except Exception:
            pass
        if refreshed:
            cls._POLICY_RATES_UPDATED = datetime.now().strftime("%Y-%m-%d")

    @classmethod
    def _rates_staleness_warning(cls) -> str | None:
        """Return a warning string if policy rates are stale."""
        from datetime import datetime
        last = datetime.strptime(cls._POLICY_RATES_UPDATED, "%Y-%m-%d")
        age_days = (datetime.now() - last).days
        if age_days > cls._RATES_STALE_DAYS:
            return (
                f"Policy rates last updated {cls._POLICY_RATES_UPDATED} "
                f"({age_days} days ago). Hedge cost estimates may be inaccurate."
            )
        return None

    @staticmethod
    def _fx_exposure(ticker: str, country: str) -> dict | None:
        """Report base currency and translation risk flag."""
        if country not in CURRENCY_BY_COUNTRY:
            return None
        _, base_currency = CURRENCY_BY_COUNTRY[country]
        return {
            "base_currency": base_currency,
            "primary_exposure": base_currency,
            "usd_denominated": country == "United States",
            "note": (
                f"Functional currency: {base_currency}. "
                "USD-denominated ADR adds translation risk."
                if base_currency != "USD"
                else "USD functional currency — no translation risk."
            ),
        }

    @classmethod
    def _hedge_cost_estimate(cls, country: str) -> dict | None:
        """Estimate FX hedge cost from interest rate differential.

        Hedge cost ~ USD_rate - foreign_rate (covered interest parity).
        Attempts live rate refresh; warns if rates are stale.
        """
        if country not in CURRENCY_BY_COUNTRY:
            return None

        # Attempt live refresh
        try:
            cls._refresh_policy_rates()
        except Exception:
            pass

        _, currency = CURRENCY_BY_COUNTRY[country]
        home_rate = cls._POLICY_RATES.get(currency, 0.03)
        usd_rate = cls._POLICY_RATES.get("USD", 0.045)
        hedge_cost = usd_rate - home_rate

        result = {
            "currency": currency,
            "estimated_annual_hedge_cost_pct": round(hedge_cost * 100, 2),
            "rates_as_of": cls._POLICY_RATES_UPDATED,
            "note": (
                f"Hedging {currency} exposure costs ~{hedge_cost * 100:.1f}% "
                "annually (rate differential proxy)"
            ),
        }

        staleness = cls._rates_staleness_warning()
        if staleness:
            result["staleness_warning"] = staleness

        return result

    @staticmethod
    def _boj_sensitivity(ticker: str, country: str) -> dict | None:
        """Flag JPY holdings with BOJ policy sensitivity."""
        if country != "Japan":
            return None
        return {
            "flag": True,
            "severity": "MEDIUM",
            "note": (
                "JPY-denominated. BOJ policy normalization risk: rate hikes "
                "strengthen JPY, compressing ADR returns for USD investors."
            ),
        }


# --- Plugin adapter for pipeline ---
from src.analysis.base import BaseAnalyzer as _BaseAnalyzer


class InternationalAnalyzerPlugin(_BaseAnalyzer):
    name = "international"
    default_weight = 0.08

    def __init__(self):
        self._analyzer = InternationalAnalyzer()

    def analyze(self, ticker, ctx):
        # Determine country
        try:
            info = yf.Ticker(ticker).info
            country = info.get("country") or "United States"
        except Exception:
            country = "United States"

        result = self._analyzer.analyze(ticker, country=country)

        # Enrich with currency risk extensions
        fx_exp = InternationalAnalyzer._fx_exposure(ticker, country)
        if fx_exp:
            result["fx_exposure"] = fx_exp
        hedge = InternationalAnalyzer._hedge_cost_estimate(country)
        if hedge:
            result["hedge_cost"] = hedge
        boj = InternationalAnalyzer._boj_sensitivity(ticker, country)
        if boj:
            result["boj_sensitivity"] = boj

        # Compute a 0-100 score from international risk factors
        score = 70.0  # Base score for any stock

        # ADR premium penalty
        adr = result.get("adr_analysis", {})
        premium_z = adr.get("premium_z_score", 0)
        if abs(premium_z) > 2:
            score -= 15
        elif abs(premium_z) > 1:
            score -= 5

        # FX sensitivity penalty
        fx = result.get("fx_sensitivity", {})
        correlation = abs(fx.get("correlation", 0))
        if correlation > 0.4:
            score -= 10
        elif correlation > 0.2:
            score -= 5

        # Hedge cost drag
        if hedge:
            hc = abs(hedge.get("estimated_annual_hedge_cost_pct", 0))
            if hc > 3:
                score -= 10
            elif hc > 1.5:
                score -= 5

        # US-listed stocks get minimal international risk
        if country == "United States":
            score = 80.0

        result["score"] = round(max(0, min(100, score)), 1)
        return result

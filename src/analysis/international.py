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
    "SHECY": "6723.T",  # Renesas
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

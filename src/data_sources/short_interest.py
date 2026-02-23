"""Short interest data client.

Track short interest metrics as a contrarian signal.
Primary source: yfinance info dict (no API key required).
"""

import yfinance as yf

from src.utils.cache import DataCache
from src.utils.logger import setup_logger

logger = setup_logger("short_interest")
cache = DataCache("short_interest")


class ShortInterestClient:
    """Track short interest data as a contrarian signal."""

    # Thresholds for signal classification
    HIGH_SHORT_PCT = 20.0
    ELEVATED_SHORT_PCT = 10.0
    SIGNIFICANT_CHANGE_PCT = 10.0

    def get_short_interest(self, ticker: str) -> dict:
        """Get short interest metrics for a ticker.

        Returns shares_short, short_ratio (days to cover), short_pct_of_float,
        short_change_pct (vs prior month), and signal classification.
        """
        cache_key = f"short_{ticker}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        logger.info("Fetching short interest: %s", ticker)
        result = {
            "ticker": ticker,
            "shares_short": None,
            "shares_short_prior_month": None,
            "short_ratio": None,
            "short_pct_of_float": None,
            "short_change_pct": None,
            "short_change_direction": "UNKNOWN",
            "signal": "UNAVAILABLE",
            "signal_details": [],
        }

        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            shares_short = info.get("sharesShort")
            shares_short_prior = info.get("sharesShortPriorMonth")
            short_ratio = info.get("shortRatio")
            short_pct = info.get("shortPercentOfFloat")

            result["shares_short"] = shares_short
            result["shares_short_prior_month"] = shares_short_prior
            result["short_ratio"] = _safe_round(short_ratio, 2)

            # Convert short_pct_of_float to percentage if it's a fraction
            if short_pct is not None:
                # yfinance sometimes returns as decimal (0.05) or percent (5.0)
                if short_pct < 1.0:
                    short_pct = short_pct * 100
                result["short_pct_of_float"] = round(short_pct, 2)

            # Calculate month-over-month change
            if shares_short is not None and shares_short_prior is not None and shares_short_prior > 0:
                change_pct = ((shares_short - shares_short_prior) / shares_short_prior) * 100
                result["short_change_pct"] = round(change_pct, 2)
                if change_pct > self.SIGNIFICANT_CHANGE_PCT:
                    result["short_change_direction"] = "INCREASING"
                elif change_pct < -self.SIGNIFICANT_CHANGE_PCT:
                    result["short_change_direction"] = "DECREASING"
                else:
                    result["short_change_direction"] = "STABLE"

            # Generate signal
            signals = []
            pct = result["short_pct_of_float"]

            if pct is not None:
                if pct >= self.HIGH_SHORT_PCT:
                    signals.append("HIGH SHORT INTEREST")
                elif pct >= self.ELEVATED_SHORT_PCT:
                    signals.append("ELEVATED")

                # Days-to-cover warning
                if result["short_ratio"] is not None and result["short_ratio"] > 5:
                    signals.append("HIGH DAYS TO COVER")

                # Change direction flag
                if result["short_change_direction"] == "INCREASING":
                    signals.append("SHORTS INCREASING")
                elif result["short_change_direction"] == "DECREASING":
                    signals.append("SHORTS DECREASING")

                # Squeeze candidate: high short interest + decreasing or high days to cover
                if pct >= self.ELEVATED_SHORT_PCT and (
                    result["short_change_direction"] == "DECREASING"
                    or (result["short_ratio"] is not None and result["short_ratio"] > 7)
                ):
                    signals.append("POTENTIAL SQUEEZE")

                result["signal_details"] = signals
                if "HIGH SHORT INTEREST" in signals:
                    result["signal"] = "HIGH SHORT INTEREST"
                elif "ELEVATED" in signals:
                    result["signal"] = "ELEVATED"
                else:
                    result["signal"] = "NORMAL"
            else:
                result["signal"] = "UNAVAILABLE"

        except Exception as e:
            logger.warning("Failed to fetch short interest for %s: %s", ticker, e)

        cache.set(cache_key, result)
        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_round(val, decimals: int = 2) -> float | None:
    """Safely round a value, returning None on failure."""
    if val is None:
        return None
    try:
        f = float(val)
        if f != f:  # NaN check
            return None
        return round(f, decimals)
    except (ValueError, TypeError):
        return None

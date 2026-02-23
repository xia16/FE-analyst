"""Earnings estimates and revision tracking.

Track earnings estimate revisions — a leading indicator of stock performance.
Primary source: yfinance (no API key required).
"""

from datetime import datetime

import yfinance as yf

from src.utils.cache import DataCache
from src.utils.logger import setup_logger

logger = setup_logger("earnings_estimates")
cache = DataCache("earnings_estimates")


class EarningsEstimatesClient:
    """Track earnings estimate revisions - a leading indicator of stock performance."""

    def get_earnings_calendar(self, ticker: str) -> dict:
        """Next earnings date + estimates.

        Returns dict with next_earnings_date, eps_estimate, previous_eps,
        surprise_pct (last quarter), and revenue_estimate.
        """
        cache_key = f"calendar_{ticker}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        logger.info("Fetching earnings calendar: %s", ticker)
        result = {
            "ticker": ticker,
            "next_earnings_date": None,
            "eps_estimate": None,
            "previous_eps": None,
            "surprise_pct": None,
            "revenue_estimate": None,
        }

        try:
            stock = yf.Ticker(ticker)

            # Next earnings date from calendar
            try:
                cal = stock.calendar
                if isinstance(cal, dict) and "Earnings Date" in cal:
                    dates = cal["Earnings Date"]
                    if isinstance(dates, list) and len(dates) > 0:
                        result["next_earnings_date"] = str(dates[0])
                    elif dates is not None:
                        result["next_earnings_date"] = str(dates)
            except Exception as e:
                logger.debug("Calendar unavailable for %s: %s", ticker, e)

            # Recent earnings surprises from earnings_dates
            try:
                ed = stock.earnings_dates
                if ed is not None and not ed.empty:
                    # earnings_dates is indexed by date, most recent first
                    # Columns: "EPS Estimate", "Reported EPS", "Surprise(%)"
                    # Find the most recent row that has reported EPS (past earnings)
                    reported = ed[ed["Reported EPS"].notna()]
                    if not reported.empty:
                        latest = reported.iloc[0]
                        result["previous_eps"] = _safe_float(latest.get("Reported EPS"))
                        result["surprise_pct"] = _safe_float(latest.get("Surprise(%)"))

                    # Find next upcoming (rows where Reported EPS is NaN = future)
                    upcoming = ed[ed["Reported EPS"].isna()]
                    if not upcoming.empty:
                        next_row = upcoming.iloc[-1]  # furthest future is last, closest is first after sort
                        # Actually earnings_dates is sorted descending, so closest future = first NaN row
                        next_row = upcoming.iloc[0]
                        result["eps_estimate"] = _safe_float(next_row.get("EPS Estimate"))
                        if result["next_earnings_date"] is None:
                            result["next_earnings_date"] = str(upcoming.index[0].date())
            except Exception as e:
                logger.debug("earnings_dates unavailable for %s: %s", ticker, e)

            # Current quarter EPS estimate from earnings_estimate
            try:
                ee = stock.earnings_estimate
                if ee is not None and not ee.empty:
                    if "avg" in ee.index:
                        cols = ee.columns.tolist()
                        if len(cols) > 0:
                            result["eps_estimate"] = result["eps_estimate"] or _safe_float(ee.loc["avg", cols[0]])
            except Exception as e:
                logger.debug("earnings_estimate unavailable for %s: %s", ticker, e)

            # Revenue estimate for current quarter
            try:
                re = stock.revenue_estimate
                if re is not None and not re.empty:
                    if "avg" in re.index:
                        cols = re.columns.tolist()
                        if len(cols) > 0:
                            result["revenue_estimate"] = _safe_float(re.loc["avg", cols[0]])
            except Exception as e:
                logger.debug("revenue_estimate unavailable for %s: %s", ticker, e)

        except Exception as e:
            logger.warning("Failed to fetch earnings calendar for %s: %s", ticker, e)

        cache.set(cache_key, result)
        return result

    def get_estimate_revisions(self, ticker: str) -> dict:
        """Track EPS estimate revisions and analyst price targets.

        Returns current_estimate, year_ago_eps, revision_direction,
        analyst_price_targets, and an overall revision_signal.
        """
        cache_key = f"revisions_{ticker}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        logger.info("Fetching estimate revisions: %s", ticker)
        result = {
            "ticker": ticker,
            "current_quarter_estimate": None,
            "next_quarter_estimate": None,
            "current_year_estimate": None,
            "next_year_estimate": None,
            "year_ago_eps": None,
            "revision_direction": "UNKNOWN",
            "analyst_targets": {},
            "revision_signal": "NEUTRAL",
        }

        try:
            stock = yf.Ticker(ticker)

            # EPS estimates by period
            try:
                ee = stock.earnings_estimate
                if ee is not None and not ee.empty:
                    cols = ee.columns.tolist()
                    # Typical columns: "Current Qtr", "Next Qtr", "Current Year", "Next Year"
                    for i, col in enumerate(cols):
                        col_lower = str(col).lower()
                        if "avg" in ee.index:
                            val = _safe_float(ee.loc["avg", col])
                            if i == 0:
                                result["current_quarter_estimate"] = val
                            elif i == 1:
                                result["next_quarter_estimate"] = val
                            elif i == 2:
                                result["current_year_estimate"] = val
                            elif i == 3:
                                result["next_year_estimate"] = val

                        if "yearAgoEps" in ee.index:
                            ya = _safe_float(ee.loc["yearAgoEps", col])
                            if i == 0 and ya is not None:
                                result["year_ago_eps"] = ya

                    # Determine revision direction: compare current estimate to year-ago EPS
                    cur = result["current_quarter_estimate"]
                    ya = result["year_ago_eps"]
                    if cur is not None and ya is not None and ya != 0:
                        growth = (cur - ya) / abs(ya)
                        if growth > 0.05:
                            result["revision_direction"] = "UP"
                        elif growth < -0.05:
                            result["revision_direction"] = "DOWN"
                        else:
                            result["revision_direction"] = "FLAT"
            except Exception as e:
                logger.debug("earnings_estimate unavailable for %s: %s", ticker, e)

            # Analyst price targets
            try:
                targets = stock.analyst_price_targets
                if targets and isinstance(targets, dict):
                    result["analyst_targets"] = {
                        "current": _safe_float(targets.get("current")),
                        "low": _safe_float(targets.get("low")),
                        "high": _safe_float(targets.get("high")),
                        "mean": _safe_float(targets.get("mean")),
                        "median": _safe_float(targets.get("median")),
                    }
                    # Upside/downside signal from target vs current price
                    current_price = _safe_float(targets.get("current"))
                    mean_target = _safe_float(targets.get("mean"))
                    if current_price and mean_target and current_price > 0:
                        upside = (mean_target - current_price) / current_price
                        result["analyst_targets"]["upside_pct"] = round(upside * 100, 1)
            except Exception as e:
                logger.debug("analyst_price_targets unavailable for %s: %s", ticker, e)

            # Composite revision signal
            direction = result["revision_direction"]
            upside = result["analyst_targets"].get("upside_pct")
            if direction == "UP" and upside is not None and upside > 10:
                result["revision_signal"] = "BULLISH"
            elif direction == "DOWN" and upside is not None and upside < -5:
                result["revision_signal"] = "BEARISH"
            elif direction == "UP" or (upside is not None and upside > 15):
                result["revision_signal"] = "SLIGHTLY_BULLISH"
            elif direction == "DOWN" or (upside is not None and upside < 0):
                result["revision_signal"] = "SLIGHTLY_BEARISH"
            else:
                result["revision_signal"] = "NEUTRAL"

        except Exception as e:
            logger.warning("Failed to fetch estimate revisions for %s: %s", ticker, e)

        cache.set(cache_key, result)
        return result

    def get_earnings_history(self, ticker: str, quarters: int = 8) -> list[dict]:
        """Get recent earnings surprises.

        Returns list of dicts with quarter, eps_estimate, eps_actual,
        surprise_pct, and beat (bool).
        """
        cache_key = f"history_{ticker}_{quarters}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        logger.info("Fetching earnings history: %s (%d quarters)", ticker, quarters)
        results = []

        try:
            stock = yf.Ticker(ticker)

            # Primary: earnings_history DataFrame
            try:
                eh = stock.earnings_history
                if eh is not None and not eh.empty:
                    for _, row in eh.head(quarters).iterrows():
                        eps_est = _safe_float(row.get("epsEstimate"))
                        eps_act = _safe_float(row.get("epsActual"))
                        surprise = _safe_float(row.get("surprisePercent"))
                        if surprise is None and eps_est and eps_est != 0 and eps_act is not None:
                            surprise = round(((eps_act - eps_est) / abs(eps_est)) * 100, 2)
                        results.append({
                            "quarter": str(row.get("quarter", "")),
                            "eps_estimate": eps_est,
                            "eps_actual": eps_act,
                            "eps_difference": _safe_float(row.get("epsDifference")),
                            "surprise_pct": surprise,
                            "beat": eps_act > eps_est if eps_act is not None and eps_est is not None else None,
                        })
                    if results:
                        cache.set(cache_key, results)
                        return results
            except Exception as e:
                logger.debug("earnings_history unavailable for %s: %s", ticker, e)

            # Fallback: earnings_dates (has both reported and estimated)
            try:
                ed = stock.earnings_dates
                if ed is not None and not ed.empty:
                    reported = ed[ed["Reported EPS"].notna()].head(quarters)
                    for date_idx, row in reported.iterrows():
                        eps_est = _safe_float(row.get("EPS Estimate"))
                        eps_act = _safe_float(row.get("Reported EPS"))
                        surprise = _safe_float(row.get("Surprise(%)"))
                        results.append({
                            "quarter": str(date_idx.date()) if hasattr(date_idx, "date") else str(date_idx),
                            "eps_estimate": eps_est,
                            "eps_actual": eps_act,
                            "eps_difference": round(eps_act - eps_est, 4) if eps_act is not None and eps_est is not None else None,
                            "surprise_pct": surprise,
                            "beat": eps_act > eps_est if eps_act is not None and eps_est is not None else None,
                        })
            except Exception as e:
                logger.debug("earnings_dates fallback failed for %s: %s", ticker, e)

        except Exception as e:
            logger.warning("Failed to fetch earnings history for %s: %s", ticker, e)

        cache.set(cache_key, results)
        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(val) -> float | None:
    """Convert a value to float, returning None on failure."""
    if val is None:
        return None
    try:
        f = float(val)
        # Catch NaN / Inf
        if f != f or f == float("inf") or f == float("-inf"):
            return None
        return round(f, 4)
    except (ValueError, TypeError):
        return None

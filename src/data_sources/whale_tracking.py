"""Institutional and insider ownership tracking.

Track 13F filings — institutional position changes and insider activity.
Primary source: yfinance (no API key required).
"""

from datetime import datetime

import pandas as pd
import yfinance as yf

from src.utils.cache import DataCache
from src.utils.logger import setup_logger

logger = setup_logger("whale_tracking")
cache = DataCache("whale_tracking")


class WhaleTrackingClient:
    """Track 13F filings - institutional position changes."""

    def get_institutional_holders(self, ticker: str) -> dict:
        """Get top institutional holders and ownership breakdown.

        Returns top_holders list, institutional_pct, insider_pct,
        total_institutions, and total_institutional_value.
        """
        cache_key = f"inst_{ticker}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        logger.info("Fetching institutional holders: %s", ticker)
        result = {
            "ticker": ticker,
            "institutional_pct": None,
            "insider_pct": None,
            "top_holders": [],
            "total_institutions": None,
            "total_institutional_value": None,
        }

        try:
            stock = yf.Ticker(ticker)

            # Major holders summary (% held by insiders, institutions, etc.)
            try:
                mh = stock.major_holders
                if mh is not None and not mh.empty:
                    # major_holders is a 2-column DataFrame: Value, description
                    for _, row in mh.iterrows():
                        desc = str(row.iloc[1]).lower() if len(row) > 1 else ""
                        val_str = str(row.iloc[0])
                        val = _parse_pct(val_str)
                        if "insider" in desc:
                            result["insider_pct"] = val
                        elif "institution" in desc and "float" not in desc:
                            result["institutional_pct"] = val
            except Exception as e:
                logger.debug("major_holders unavailable for %s: %s", ticker, e)

            # Top institutional holders
            try:
                ih = stock.institutional_holders
                if ih is not None and not ih.empty:
                    result["total_institutions"] = len(ih)
                    total_value = 0
                    holders = []
                    for _, row in ih.head(15).iterrows():
                        date_reported = row.get("Date Reported")
                        if isinstance(date_reported, pd.Timestamp):
                            date_reported = date_reported.strftime("%Y-%m-%d")
                        else:
                            date_reported = str(date_reported) if date_reported is not None else None

                        value = _safe_float(row.get("Value"))
                        shares = _safe_int(row.get("Shares"))
                        pct_out = _safe_float(row.get("% Out"))

                        holders.append({
                            "holder": row.get("Holder", "Unknown"),
                            "shares": shares,
                            "date_reported": date_reported,
                            "pct_out": round(pct_out * 100, 2) if pct_out is not None and pct_out < 1 else pct_out,
                            "value": value,
                        })
                        if value is not None:
                            total_value += value

                    result["top_holders"] = holders
                    result["total_institutional_value"] = total_value if total_value > 0 else None
            except Exception as e:
                logger.debug("institutional_holders unavailable for %s: %s", ticker, e)

        except Exception as e:
            logger.warning("Failed to fetch institutional holders for %s: %s", ticker, e)

        cache.set(cache_key, result)
        return result

    def get_insider_ownership(self, ticker: str) -> dict:
        """Get insider ownership percentage and key holders.

        Returns insider_ownership_pct, top_insiders list, and
        recent_transactions list.
        """
        cache_key = f"insider_{ticker}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        logger.info("Fetching insider ownership: %s", ticker)
        result = {
            "ticker": ticker,
            "insider_ownership_pct": None,
            "top_insiders": [],
            "recent_transactions": [],
            "net_insider_buys_90d": 0,
        }

        try:
            stock = yf.Ticker(ticker)

            # Insider ownership % from major_holders
            try:
                mh = stock.major_holders
                if mh is not None and not mh.empty:
                    for _, row in mh.iterrows():
                        desc = str(row.iloc[1]).lower() if len(row) > 1 else ""
                        if "insider" in desc:
                            result["insider_ownership_pct"] = _parse_pct(str(row.iloc[0]))
                            break
            except Exception as e:
                logger.debug("major_holders unavailable for %s: %s", ticker, e)

            # Insider roster (key insiders and their positions)
            try:
                roster = stock.insider_roster_holders
                if roster is not None and not roster.empty:
                    insiders = []
                    for _, row in roster.head(10).iterrows():
                        latest_date = row.get("Latest Transaction Date")
                        if isinstance(latest_date, pd.Timestamp):
                            latest_date = latest_date.strftime("%Y-%m-%d")
                        else:
                            latest_date = str(latest_date) if latest_date is not None else None

                        insiders.append({
                            "name": row.get("Name", "Unknown"),
                            "position": row.get("Position", ""),
                            "most_recent_transaction": row.get("Most Recent Transaction", ""),
                            "latest_transaction_date": latest_date,
                            "shares_owned": _safe_int(row.get("Shares Owned Directly")),
                        })
                    result["top_insiders"] = insiders
            except Exception as e:
                logger.debug("insider_roster_holders unavailable for %s: %s", ticker, e)

            # Recent insider transactions
            try:
                txns = stock.insider_transactions
                if txns is not None and not txns.empty:
                    transactions = []
                    net_buys = 0
                    cutoff_90d = datetime.now().timestamp() - (90 * 86400)

                    for _, row in txns.head(20).iterrows():
                        start_date = row.get("Start Date")
                        if isinstance(start_date, pd.Timestamp):
                            date_str = start_date.strftime("%Y-%m-%d")
                            ts = start_date.timestamp()
                        else:
                            date_str = str(start_date) if start_date is not None else None
                            ts = 0

                        shares = _safe_int(row.get("Shares"))
                        value = _safe_float(row.get("Value"))
                        text = str(row.get("Text", ""))

                        transactions.append({
                            "insider": row.get("Insider", "Unknown"),
                            "relation": row.get("Relationship", ""),
                            "date": date_str,
                            "transaction": text,
                            "shares": shares,
                            "value": value,
                        })

                        # Count net buys in last 90 days
                        if ts > cutoff_90d:
                            text_lower = text.lower()
                            if "purchase" in text_lower or "buy" in text_lower:
                                net_buys += 1
                            elif "sale" in text_lower or "sell" in text_lower:
                                net_buys -= 1

                    result["recent_transactions"] = transactions
                    result["net_insider_buys_90d"] = net_buys
            except Exception as e:
                logger.debug("insider_transactions unavailable for %s: %s", ticker, e)

        except Exception as e:
            logger.warning("Failed to fetch insider ownership for %s: %s", ticker, e)

        cache.set(cache_key, result)
        return result

    def get_fund_sentiment(self, ticker: str) -> dict:
        """Aggregate institutional sentiment from holder data.

        Analyzes holder positions and insider activity to determine
        if institutions are accumulating or distributing.
        Returns signal: ACCUMULATION, DISTRIBUTION, or NEUTRAL.
        """
        cache_key = f"sentiment_{ticker}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        logger.info("Computing fund sentiment: %s", ticker)
        result = {
            "ticker": ticker,
            "signal": "NEUTRAL",
            "institutional_pct": None,
            "insider_pct": None,
            "net_insider_buys_90d": 0,
            "holder_concentration": None,
            "details": [],
        }

        try:
            # Gather data from the other methods (they have their own caching)
            inst_data = self.get_institutional_holders(ticker)
            insider_data = self.get_insider_ownership(ticker)

            result["institutional_pct"] = inst_data.get("institutional_pct")
            result["insider_pct"] = inst_data.get("insider_pct")
            result["net_insider_buys_90d"] = insider_data.get("net_insider_buys_90d", 0)

            # Holder concentration: % held by top 5 institutions
            top_holders = inst_data.get("top_holders", [])
            if top_holders:
                top5_pct = sum(
                    h.get("pct_out", 0) or 0
                    for h in top_holders[:5]
                )
                result["holder_concentration"] = round(top5_pct, 2)

            # Determine signal based on multiple factors
            signals = []
            bullish_points = 0
            bearish_points = 0

            # Factor 1: Insider buying in last 90 days
            net_buys = result["net_insider_buys_90d"]
            if net_buys >= 2:
                bullish_points += 2
                signals.append(f"Strong insider buying ({net_buys} net buys in 90d)")
            elif net_buys == 1:
                bullish_points += 1
                signals.append("Insider buying detected (1 net buy in 90d)")
            elif net_buys <= -2:
                bearish_points += 2
                signals.append(f"Heavy insider selling ({abs(net_buys)} net sells in 90d)")
            elif net_buys == -1:
                bearish_points += 1
                signals.append("Insider selling detected (1 net sell in 90d)")

            # Factor 2: High institutional ownership (stability signal)
            inst_pct = result["institutional_pct"]
            if inst_pct is not None:
                if inst_pct > 80:
                    signals.append(f"Very high institutional ownership ({inst_pct}%)")
                    bullish_points += 1
                elif inst_pct < 20:
                    signals.append(f"Low institutional ownership ({inst_pct}%)")

            # Factor 3: Insider ownership alignment
            ins_pct = result["insider_pct"]
            if ins_pct is not None and ins_pct > 10:
                bullish_points += 1
                signals.append(f"Significant insider ownership ({ins_pct}%)")

            # Compute overall signal
            if bullish_points >= 2 and bullish_points > bearish_points:
                result["signal"] = "ACCUMULATION"
            elif bearish_points >= 2 and bearish_points > bullish_points:
                result["signal"] = "DISTRIBUTION"
            else:
                result["signal"] = "NEUTRAL"

            result["details"] = signals

        except Exception as e:
            logger.warning("Failed to compute fund sentiment for %s: %s", ticker, e)

        cache.set(cache_key, result)
        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(val) -> float | None:
    """Convert a value to float, returning None on failure."""
    if val is None:
        return None
    try:
        f = float(val)
        if f != f:  # NaN check
            return None
        return f
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> int | None:
    """Convert a value to int, returning None on failure."""
    if val is None:
        return None
    try:
        f = float(val)
        if f != f:  # NaN check
            return None
        return int(f)
    except (ValueError, TypeError):
        return None


def _parse_pct(val_str: str) -> float | None:
    """Parse a percentage string like '5.23%' or '0.0523' to a float percentage."""
    if not val_str:
        return None
    try:
        cleaned = val_str.strip().replace("%", "")
        f = float(cleaned)
        # If the original had a % sign, it's already in percent form
        if "%" in val_str:
            return round(f, 2)
        # If it looks like a fraction (< 1), convert to percent
        if f < 1.0:
            return round(f * 100, 2)
        return round(f, 2)
    except (ValueError, TypeError):
        return None

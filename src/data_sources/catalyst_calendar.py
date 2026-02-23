"""Catalyst calendar — aggregate upcoming events for a ticker or sector.

Combines earnings dates, dividend dates, FOMC meetings, and sector-specific
events into a unified catalyst timeline.
Primary source: yfinance + hardcoded macro calendar.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import yfinance as yf

from src.utils.cache import DataCache
from src.utils.logger import setup_logger

logger = setup_logger("catalyst_calendar")
cache = DataCache("catalyst_calendar")

# ---------------------------------------------------------------------------
# Hardcoded macro / sector calendars
# ---------------------------------------------------------------------------

FOMC_2026 = [
    "2026-01-28", "2026-03-18", "2026-05-06", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16",
]

# Approximate US earnings season windows (reporting period start dates)
EARNINGS_SEASONS_2026 = [
    {"start": "2026-01-12", "end": "2026-02-14", "label": "Q4 2025 Earnings Season"},
    {"start": "2026-04-13", "end": "2026-05-16", "label": "Q1 2026 Earnings Season"},
    {"start": "2026-07-13", "end": "2026-08-15", "label": "Q2 2026 Earnings Season"},
    {"start": "2026-10-12", "end": "2026-11-14", "label": "Q3 2026 Earnings Season"},
]

# Sector-specific recurring catalysts
SECTOR_CATALYSTS = {
    "technology": [
        {"month": 1, "description": "CES (Consumer Electronics Show)", "importance": "MEDIUM"},
        {"month": 3, "description": "GTC (NVIDIA GPU Technology Conference)", "importance": "HIGH"},
        {"month": 6, "description": "WWDC (Apple Worldwide Developers Conference)", "importance": "HIGH"},
        {"month": 6, "description": "Computex Taipei", "importance": "MEDIUM"},
        {"month": 9, "description": "Apple Fall Event (iPhone launch)", "importance": "HIGH"},
        {"month": 11, "description": "AWS re:Invent", "importance": "MEDIUM"},
    ],
    "semiconductors": [
        {"month": 1, "description": "TSMC Q4 Earnings (industry bellwether)", "importance": "HIGH"},
        {"month": 3, "description": "SEMI World Fab Forecast update", "importance": "MEDIUM"},
        {"month": 4, "description": "TSMC Q1 Earnings", "importance": "HIGH"},
        {"month": 6, "description": "SEMICON West", "importance": "MEDIUM"},
        {"month": 7, "description": "TSMC Q2 Earnings", "importance": "HIGH"},
        {"month": 9, "description": "SEMI Equipment Billings report", "importance": "MEDIUM"},
        {"month": 10, "description": "TSMC Q3 Earnings", "importance": "HIGH"},
        {"month": 12, "description": "SEMI Year-End Equipment Forecast", "importance": "MEDIUM"},
    ],
    "financials": [
        {"month": 1, "description": "Major bank earnings season begins", "importance": "HIGH"},
        {"month": 6, "description": "Fed Stress Test results", "importance": "HIGH"},
        {"month": 7, "description": "Major bank Q2 earnings", "importance": "HIGH"},
    ],
    "energy": [
        {"month": 3, "description": "OPEC+ production review", "importance": "HIGH"},
        {"month": 6, "description": "OPEC+ mid-year meeting", "importance": "HIGH"},
        {"month": 11, "description": "OPEC+ full ministerial meeting", "importance": "HIGH"},
    ],
    "healthcare": [
        {"month": 6, "description": "ASCO Annual Meeting (oncology)", "importance": "HIGH"},
        {"month": 11, "description": "RSNA Annual Meeting (radiology)", "importance": "MEDIUM"},
    ],
}


class CatalystCalendarClient:
    """Aggregate upcoming catalysts for a ticker."""

    def get_catalysts(self, ticker: str, days_ahead: int = 90) -> dict:
        """Get all upcoming catalysts for a ticker.

        Combines earnings dates, dividend dates, and FOMC meetings into
        a sorted timeline. Returns list of catalyst dicts sorted by date.
        """
        cache_key = f"catalysts_{ticker}_{days_ahead}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        logger.info("Fetching catalysts: %s (next %d days)", ticker, days_ahead)
        today = datetime.now().date()
        horizon = today + timedelta(days=days_ahead)
        catalysts = []

        try:
            stock = yf.Ticker(ticker)

            # 1. Earnings date
            try:
                cal = stock.calendar
                if isinstance(cal, dict) and "Earnings Date" in cal:
                    dates = cal["Earnings Date"]
                    if isinstance(dates, list):
                        for d in dates:
                            ed = _parse_date(d)
                            if ed and today <= ed <= horizon:
                                catalysts.append({
                                    "date": ed.isoformat(),
                                    "type": "EARNINGS",
                                    "description": f"{ticker} earnings report",
                                    "importance": "HIGH",
                                })
                    elif dates is not None:
                        ed = _parse_date(dates)
                        if ed and today <= ed <= horizon:
                            catalysts.append({
                                "date": ed.isoformat(),
                                "type": "EARNINGS",
                                "description": f"{ticker} earnings report",
                                "importance": "HIGH",
                            })
            except Exception as e:
                logger.debug("Calendar unavailable for %s: %s", ticker, e)

            # 2. Dividend dates
            try:
                info = stock.info
                ex_div = info.get("exDividendDate")
                if ex_div is not None:
                    ed = _parse_date(ex_div)
                    if ed and today <= ed <= horizon:
                        div_yield = info.get("dividendYield")
                        yield_str = f" (yield: {div_yield:.1%})" if div_yield else ""
                        catalysts.append({
                            "date": ed.isoformat(),
                            "type": "DIVIDEND",
                            "description": f"{ticker} ex-dividend date{yield_str}",
                            "importance": "MEDIUM",
                        })

                div_date = info.get("dividendDate")
                if div_date is not None:
                    dd = _parse_date(div_date)
                    if dd and today <= dd <= horizon and dd != ed:
                        catalysts.append({
                            "date": dd.isoformat(),
                            "type": "DIVIDEND_PAY",
                            "description": f"{ticker} dividend payment date",
                            "importance": "LOW",
                        })
            except Exception as e:
                logger.debug("Dividend info unavailable for %s: %s", ticker, e)

            # 3. FOMC dates (always relevant for equities)
            for fomc_str in FOMC_2026:
                fomc_date = datetime.strptime(fomc_str, "%Y-%m-%d").date()
                if today <= fomc_date <= horizon:
                    catalysts.append({
                        "date": fomc_str,
                        "type": "MACRO",
                        "description": "FOMC interest rate decision",
                        "importance": "HIGH",
                    })

            # 4. Earnings season windows
            for season in EARNINGS_SEASONS_2026:
                s_start = datetime.strptime(season["start"], "%Y-%m-%d").date()
                if today <= s_start <= horizon:
                    catalysts.append({
                        "date": season["start"],
                        "type": "EARNINGS_SEASON",
                        "description": season["label"],
                        "importance": "MEDIUM",
                    })

        except Exception as e:
            logger.warning("Failed to fetch catalysts for %s: %s", ticker, e)

        # Deduplicate by (date, type)
        seen = set()
        unique = []
        for c in catalysts:
            key = (c["date"], c["type"])
            if key not in seen:
                seen.add(key)
                unique.append(c)

        # Sort by date ascending
        unique.sort(key=lambda x: x["date"])

        result = {
            "ticker": ticker,
            "days_ahead": days_ahead,
            "catalyst_count": len(unique),
            "catalysts": unique,
        }
        cache.set(cache_key, result)
        return result

    def get_sector_catalysts(self, sector: str, days_ahead: int = 90) -> list[dict]:
        """Get sector-level catalysts for the given sector.

        Includes hardcoded sector-specific events plus FOMC dates.
        Sector names are case-insensitive and partially matched.
        """
        cache_key = f"sector_{sector.lower()}_{days_ahead}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        logger.info("Fetching sector catalysts: %s (next %d days)", sector, days_ahead)
        today = datetime.now().date()
        horizon = today + timedelta(days=days_ahead)
        catalysts = []

        # Match sector to our catalog (partial, case-insensitive)
        sector_lower = sector.lower()
        matched_sectors = []
        for key in SECTOR_CATALYSTS:
            if key in sector_lower or sector_lower in key:
                matched_sectors.append(key)

        # If no match, still return FOMC dates
        for sector_key in matched_sectors:
            for event in SECTOR_CATALYSTS[sector_key]:
                # Generate date for 2026 using the event month
                event_date = datetime(2026, event["month"], 15).date()
                if today <= event_date <= horizon:
                    catalysts.append({
                        "date": event_date.isoformat(),
                        "type": "SECTOR_EVENT",
                        "description": event["description"],
                        "importance": event["importance"],
                        "sector": sector_key,
                    })

        # Always include FOMC dates
        for fomc_str in FOMC_2026:
            fomc_date = datetime.strptime(fomc_str, "%Y-%m-%d").date()
            if today <= fomc_date <= horizon:
                catalysts.append({
                    "date": fomc_str,
                    "type": "MACRO",
                    "description": "FOMC interest rate decision",
                    "importance": "HIGH",
                    "sector": "macro",
                })

        # Sort by date ascending
        catalysts.sort(key=lambda x: x["date"])

        cache.set(cache_key, catalysts)
        return catalysts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(val) -> datetime.date | None:
    """Parse various date formats into a date object."""
    if val is None:
        return None
    try:
        # Already a date/datetime
        if hasattr(val, "date"):
            return val.date() if callable(getattr(val, "date")) else val
        if hasattr(val, "isoformat") and not hasattr(val, "hour"):
            return val  # already a date

        # Unix timestamp (yfinance sometimes returns epoch seconds)
        if isinstance(val, (int, float)):
            if val > 1e9:  # looks like epoch seconds
                return datetime.fromtimestamp(val).date()
            return None

        # String parsing
        s = str(val).strip()
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%B %d, %Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None
    except Exception:
        return None

"""SEC EDGAR filings client.

Uses edgartools for parsing 10-K, 10-Q, 8-K filings.
No API key required (just a user-agent string).
"""

import pandas as pd

from src.config import Keys
from src.utils.cache import DataCache
from src.utils.logger import setup_logger

logger = setup_logger("sec_filings")
cache = DataCache("sec_filings")


class SECFilingsClient:
    """Access SEC EDGAR filings and XBRL data."""

    def __init__(self):
        if Keys.SEC_USER_AGENT:
            import edgar
            edgar.set_identity(Keys.SEC_USER_AGENT)

    def get_recent_filings(self, ticker: str, form_type: str = "10-K", count: int = 5) -> list[dict]:
        """Get recent filings of a specific type."""
        from edgar import Company

        logger.info("Fetching %s filings for %s", form_type, ticker)
        company = Company(ticker)
        filings = company.get_filings(form=form_type).latest(count)

        results = []
        for filing in filings:
            results.append({
                "form": filing.form,
                "date": str(filing.filing_date),
                "accession_number": filing.accession_no,
                "description": getattr(filing, "description", ""),
            })
        return results

    def get_financials_xbrl(self, ticker: str) -> dict:
        """Extract structured financial data from XBRL filings."""
        from edgar import Company

        logger.info("Extracting XBRL financials for %s", ticker)
        company = Company(ticker)
        filings = company.get_filings(form="10-K").latest(1)

        if not filings:
            return {}

        filing = filings[0]
        xbrl = filing.xbrl()
        if xbrl is None:
            return {}

        return {"filing_date": str(filing.filing_date), "data": str(xbrl)}

    def search_filings(self, query: str, form_type: str = "", date_from: str = "") -> list[dict]:
        """Full-text search across SEC filings."""
        import requests

        params = {"q": query, "dateRange": "custom", "startdt": date_from}
        if form_type:
            params["forms"] = form_type

        url = "https://efts.sec.gov/LATEST/search-index"
        headers = {"User-Agent": Keys.SEC_USER_AGENT or "FE-Analyst research@example.com"}
        resp = requests.get(url, params=params, headers=headers, timeout=30)

        if resp.status_code != 200:
            logger.error("EFTS search failed: %s", resp.status_code)
            return []

        data = resp.json()
        return data.get("hits", {}).get("hits", [])

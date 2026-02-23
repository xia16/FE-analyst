"""SEC EDGAR filings client.

Uses edgartools for parsing 10-K, 10-Q, 8-K filings when available,
plus direct EDGAR EFTS API for 8-K monitoring and risk factor extraction.
No API key required (just a user-agent string).
"""

import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

import pandas as pd

from src.config import Keys
from src.utils.cache import DataCache
from src.utils.logger import setup_logger

logger = setup_logger("sec_filings")
cache = DataCache("sec_filings")

# SEC EDGAR base URLs (no API key needed, just user-agent)
EDGAR_FULL_TEXT_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_FILING_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{filename}"

# 8-K item codes and their meanings
ITEM_8K_CODES = {
    "1.01": "Entry into a Material Definitive Agreement",
    "1.02": "Termination of a Material Definitive Agreement",
    "1.03": "Bankruptcy or Receivership",
    "2.01": "Completion of Acquisition or Disposition of Assets",
    "2.02": "Results of Operations and Financial Condition",
    "2.03": "Creation of a Direct Financial Obligation",
    "2.04": "Triggering Events That Accelerate or Increase a Direct Financial Obligation",
    "2.05": "Costs Associated with Exit or Disposal Activities",
    "2.06": "Material Impairments",
    "3.01": "Notice of Delisting or Failure to Satisfy a Continued Listing Rule",
    "3.02": "Unregistered Sales of Equity Securities",
    "3.03": "Material Modification to Rights of Security Holders",
    "4.01": "Changes in Registrant's Certifying Accountant",
    "4.02": "Non-Reliance on Previously Issued Financial Statements",
    "5.01": "Changes in Control of Registrant",
    "5.02": "Departure/Election of Directors or Principal Officers",
    "5.03": "Amendments to Articles of Incorporation or Bylaws",
    "5.07": "Submission of Matters to a Vote of Security Holders",
    "7.01": "Regulation FD Disclosure",
    "8.01": "Other Events",
    "9.01": "Financial Statements and Exhibits",
}

# High-impact 8-K items (material events investors care about most)
HIGH_IMPACT_ITEMS = {
    "1.01", "1.02", "1.03", "2.01", "2.02", "2.05", "2.06",
    "3.01", "4.01", "4.02", "5.01", "5.02",
}

USER_AGENT = Keys.SEC_USER_AGENT or "FE-Analyst research@example.com"


def _sec_request(url: str, params: dict | None = None) -> dict | str | None:
    """Make a request to SEC EDGAR with proper headers."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read().decode("utf-8")
            if "json" in content_type:
                return json.loads(raw)
            return raw
    except Exception as e:
        logger.warning("SEC request failed for %s: %s", url, e)
        return None


def _get_cik(ticker: str) -> str | None:
    """Resolve ticker to CIK number via SEC tickers.json."""
    cache_key = f"cik_{ticker}"
    cached = cache.get(cache_key)
    if cached:
        return cached.get("cik")

    url = "https://www.sec.gov/files/company_tickers.json"
    data = _sec_request(url)
    if not isinstance(data, dict):
        return None

    for entry in data.values():
        if entry.get("ticker", "").upper() == ticker.upper():
            cik = str(entry["cik_str"]).zfill(10)
            cache.set(cache_key, {"cik": cik})
            return cik
    return None


class SECFilingsClient:
    """Access SEC EDGAR filings and XBRL data."""

    def __init__(self):
        if Keys.SEC_USER_AGENT:
            try:
                import edgar
                edgar.set_identity(Keys.SEC_USER_AGENT)
            except ImportError:
                pass

    def get_recent_filings(self, ticker: str, form_type: str = "10-K", count: int = 5) -> list[dict]:
        """Get recent filings of a specific type."""
        # Try edgartools first, fall back to direct API
        try:
            from edgar import Company
            logger.info("Fetching %s filings for %s via edgartools", form_type, ticker)
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
        except Exception:
            pass

        # Direct EDGAR API fallback
        return self._get_filings_direct(ticker, form_type, count)

    def _get_filings_direct(self, ticker: str, form_type: str, count: int) -> list[dict]:
        """Fetch filings directly from SEC EDGAR submissions API."""
        cik = _get_cik(ticker)
        if not cik:
            return []

        url = EDGAR_SUBMISSIONS_URL.format(cik=cik)
        data = _sec_request(url)
        if not isinstance(data, dict):
            return []

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        descriptions = recent.get("primaryDocDescription", [])

        results = []
        for i, form in enumerate(forms):
            if form_type and form != form_type:
                continue
            results.append({
                "form": form,
                "date": dates[i] if i < len(dates) else "",
                "accession_number": accessions[i] if i < len(accessions) else "",
                "description": descriptions[i] if i < len(descriptions) else "",
            })
            if len(results) >= count:
                break
        return results

    def get_financials_xbrl(self, ticker: str) -> dict:
        """Extract structured financial data from XBRL filings."""
        try:
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
        except Exception as e:
            logger.warning("XBRL extraction failed for %s: %s", ticker, e)
            return {}

    def search_filings(self, query: str, form_type: str = "", date_from: str = "") -> list[dict]:
        """Full-text search across SEC filings."""
        params = {"q": query, "dateRange": "custom", "startdt": date_from}
        if form_type:
            params["forms"] = form_type

        data = _sec_request(EDGAR_FULL_TEXT_URL, params)
        if not isinstance(data, dict):
            return []

        return data.get("hits", {}).get("hits", [])

    # -------------------------------------------------------------------
    # Phase 2B: 8-K Material Event Monitoring
    # -------------------------------------------------------------------

    def get_recent_8k(self, ticker: str, months: int = 6) -> dict:
        """Get recent 8-K filings with classified material events.

        Returns a summary of recent 8-K filings with:
        - Filing date and items reported
        - Impact classification (HIGH/MEDIUM/LOW)
        - Overall signal (material events in last 3 months)
        """
        cache_key = f"8k_{ticker}_{months}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        filings = self._get_filings_direct(ticker, "8-K", 20)
        if not filings:
            return {"ticker": ticker, "filings_8k": [], "signal": "NO DATA"}

        cutoff = datetime.now() - timedelta(days=months * 30)
        recent_cutoff = datetime.now() - timedelta(days=90)

        processed = []
        high_impact_recent = 0
        total_recent = 0

        for f in filings:
            try:
                filing_date = datetime.strptime(f["date"], "%Y-%m-%d")
            except (ValueError, KeyError):
                continue

            if filing_date < cutoff:
                continue

            is_recent = filing_date >= recent_cutoff
            if is_recent:
                total_recent += 1

            # Parse 8-K items from description
            items_found = self._classify_8k_items(f.get("description", ""))

            impact = "LOW"
            if any(item["code"] in HIGH_IMPACT_ITEMS for item in items_found):
                impact = "HIGH"
                if is_recent:
                    high_impact_recent += 1
            elif items_found:
                impact = "MEDIUM"

            processed.append({
                "date": f["date"],
                "accession": f.get("accession_number", ""),
                "description": f.get("description", ""),
                "items": items_found,
                "impact": impact,
            })

        # Overall signal
        if high_impact_recent >= 3:
            signal = "HIGH ACTIVITY — Multiple material events recently"
        elif high_impact_recent >= 1:
            signal = "MODERATE ACTIVITY"
        elif total_recent == 0:
            signal = "QUIET — No 8-K filings in last 90 days"
        else:
            signal = "NORMAL"

        result = {
            "ticker": ticker,
            "filings_8k": processed[:10],  # Last 10
            "total_count": len(processed),
            "high_impact_count": sum(1 for f in processed if f["impact"] == "HIGH"),
            "recent_count_90d": total_recent,
            "signal": signal,
        }

        cache.set(cache_key, result)
        return result

    def _classify_8k_items(self, description: str) -> list[dict]:
        """Extract and classify 8-K item numbers from filing description."""
        items = []
        # Match patterns like "Item 2.02" or "Items 5.02 and 9.01"
        pattern = r"(?:Item\s+)?(\d\.\d{2})"
        matches = re.findall(pattern, description, re.IGNORECASE)

        for code in matches:
            items.append({
                "code": code,
                "description": ITEM_8K_CODES.get(code, "Unknown"),
                "high_impact": code in HIGH_IMPACT_ITEMS,
            })

        # If no items found, try to infer from description text
        if not items and description:
            desc_lower = description.lower()
            if any(kw in desc_lower for kw in ["earnings", "results of operations"]):
                items.append({"code": "2.02", "description": ITEM_8K_CODES["2.02"], "high_impact": True})
            elif any(kw in desc_lower for kw in ["acquisition", "disposition", "merger"]):
                items.append({"code": "2.01", "description": ITEM_8K_CODES["2.01"], "high_impact": True})
            elif any(kw in desc_lower for kw in ["officer", "director", "departure", "appointment"]):
                items.append({"code": "5.02", "description": ITEM_8K_CODES["5.02"], "high_impact": True})
            elif any(kw in desc_lower for kw in ["agreement", "contract"]):
                items.append({"code": "1.01", "description": ITEM_8K_CODES["1.01"], "high_impact": True})

        return items

    # -------------------------------------------------------------------
    # Phase 2B + 3A: 10-K Risk Factor Extraction & Year-over-Year Diff
    # -------------------------------------------------------------------

    def get_risk_factors(self, ticker: str) -> dict:
        """Extract risk factors from the most recent 10-K filing.

        Uses the EDGAR full-text search to find Item 1A (Risk Factors)
        from the most recent annual report.
        """
        cache_key = f"risk_factors_{ticker}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        cik = _get_cik(ticker)
        if not cik:
            return {"ticker": ticker, "risk_factors": [], "note": "CIK not found"}

        # Get latest 10-K filing
        filings = self._get_filings_direct(ticker, "10-K", 2)
        if not filings:
            return {"ticker": ticker, "risk_factors": [], "note": "No 10-K filings found"}

        latest = filings[0]
        risk_text = self._fetch_risk_factor_text(cik, latest.get("accession_number", ""))

        if not risk_text:
            return {
                "ticker": ticker,
                "filing_date": latest.get("date"),
                "risk_factors": [],
                "note": "Could not extract risk factors from filing",
            }

        # Parse individual risk headings
        risks = self._parse_risk_headings(risk_text)

        result = {
            "ticker": ticker,
            "filing_date": latest.get("date"),
            "risk_factors": risks[:20],  # Top 20 risk headings
            "total_risk_count": len(risks),
            "risk_text_length": len(risk_text),
        }

        cache.set(cache_key, result)
        return result

    def get_risk_factor_changes(self, ticker: str) -> dict:
        """Compare risk factors between the two most recent 10-K filings.

        Phase 3A: Identifies NEW risks, REMOVED risks, and MODIFIED risks
        year-over-year — a key signal for emerging threats.
        """
        cache_key = f"risk_changes_{ticker}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        cik = _get_cik(ticker)
        if not cik:
            return {"ticker": ticker, "changes": [], "note": "CIK not found"}

        filings = self._get_filings_direct(ticker, "10-K", 2)
        if len(filings) < 2:
            return {"ticker": ticker, "changes": [], "note": "Need at least 2 annual filings"}

        # Extract risk headings from both years
        current = filings[0]
        previous = filings[1]

        current_text = self._fetch_risk_factor_text(cik, current.get("accession_number", ""))
        previous_text = self._fetch_risk_factor_text(cik, previous.get("accession_number", ""))

        if not current_text or not previous_text:
            return {
                "ticker": ticker,
                "changes": [],
                "note": "Could not extract risk factors from one or both filings",
            }

        current_risks = set(self._parse_risk_headings(current_text))
        previous_risks = set(self._parse_risk_headings(previous_text))

        # Fuzzy matching — normalize headings for comparison
        current_normalized = {self._normalize_heading(r): r for r in current_risks}
        previous_normalized = {self._normalize_heading(r): r for r in previous_risks}

        current_keys = set(current_normalized.keys())
        previous_keys = set(previous_normalized.keys())

        new_risks = [current_normalized[k] for k in current_keys - previous_keys]
        removed_risks = [previous_normalized[k] for k in previous_keys - current_keys]
        unchanged = current_keys & previous_keys

        # Signal assessment
        if len(new_risks) >= 5:
            signal = "SIGNIFICANT NEW RISKS — Company facing materially new threats"
        elif len(new_risks) >= 2:
            signal = "MODERATE CHANGES — Some new risks identified"
        elif len(removed_risks) > len(new_risks):
            signal = "IMPROVING — More risks removed than added"
        else:
            signal = "STABLE — Risk profile largely unchanged"

        result = {
            "ticker": ticker,
            "current_filing": current.get("date"),
            "previous_filing": previous.get("date"),
            "new_risks": new_risks[:10],
            "removed_risks": removed_risks[:10],
            "unchanged_count": len(unchanged),
            "new_count": len(new_risks),
            "removed_count": len(removed_risks),
            "total_current": len(current_risks),
            "total_previous": len(previous_risks),
            "signal": signal,
        }

        cache.set(cache_key, result)
        return result

    def _fetch_risk_factor_text(self, cik: str, accession: str) -> str:
        """Fetch the risk factors section (Item 1A) from a 10-K filing."""
        if not accession:
            return ""

        # Get the filing index to find the main document
        acc_clean = accession.replace("-", "")
        index_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{acc_clean}/index.json"
        index_data = _sec_request(index_url)

        if not isinstance(index_data, dict):
            return ""

        # Find the main document (usually the .htm file)
        main_doc = None
        for item in index_data.get("directory", {}).get("item", []):
            name = item.get("name", "")
            if name.endswith((".htm", ".html")) and not name.startswith("R"):
                main_doc = name
                break

        if not main_doc:
            return ""

        doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{acc_clean}/{main_doc}"
        raw_html = _sec_request(doc_url)
        if not isinstance(raw_html, str):
            return ""

        # Extract Item 1A section
        return self._extract_item_1a(raw_html)

    def _extract_item_1a(self, html: str) -> str:
        """Extract Item 1A (Risk Factors) section from 10-K HTML."""
        # Remove HTML tags but preserve some structure
        text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
        text = re.sub(r"</?p[^>]*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&#\d+;", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Find Item 1A section
        # Pattern: "Item 1A" followed by risk factors content until "Item 1B" or "Item 2"
        patterns = [
            r"(?:Item\s+1A\.?\s*[\.\-—]?\s*Risk\s+Factors)(.*?)(?:Item\s+1B|Item\s+2\.?\s)",
            r"(?:ITEM\s+1A\.?\s*[\.\-—]?\s*RISK\s+FACTORS)(.*?)(?:ITEM\s+1B|ITEM\s+2\.?\s)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                section = match.group(1).strip()
                # Limit to reasonable size (risk factors can be very long)
                if len(section) > 50000:
                    section = section[:50000]
                return section

        return ""

    def _parse_risk_headings(self, risk_text: str) -> list[str]:
        """Extract risk factor headings from the risk factors section.

        Risk headings are typically bold or in larger text, and serve as
        titles for individual risk discussions.
        """
        headings = []
        lines = risk_text.split("\n")

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Heuristic: headings tend to be shorter lines that start with
            # uppercase and end without a period (or end with a period but
            # are short enough to be a title)
            if 15 < len(stripped) < 200:
                # Check if it looks like a heading
                words = stripped.split()
                if len(words) >= 3:
                    # Many risk headings are in title case or all caps
                    upper_ratio = sum(1 for w in words if w[0].isupper()) / len(words)
                    if upper_ratio >= 0.5 and not stripped.endswith(","):
                        # Filter out lines that are clearly paragraph text
                        if not any(phrase in stripped.lower() for phrase in [
                            "we believe", "we expect", "we may", "our business",
                            "in addition", "for example", "as a result",
                            "the following", "we have", "we are",
                        ]):
                            headings.append(stripped.rstrip("."))

        return headings

    @staticmethod
    def _normalize_heading(heading: str) -> str:
        """Normalize a risk heading for comparison."""
        # Lowercase, remove punctuation, collapse whitespace
        normalized = heading.lower()
        normalized = re.sub(r"[^\w\s]", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    # -------------------------------------------------------------------
    # Convenience: Combined SEC analysis for a ticker
    # -------------------------------------------------------------------

    def analyze(self, ticker: str) -> dict:
        """Run all SEC-based analyses for a ticker.

        Returns combined results from:
        - Recent 8-K events (material event monitoring)
        - 10-K risk factors (current risks)
        - Risk factor changes (year-over-year)
        """
        result = {"ticker": ticker}

        try:
            result["events_8k"] = self.get_recent_8k(ticker)
        except Exception as e:
            logger.warning("8-K analysis failed for %s: %s", ticker, e)
            result["events_8k"] = {"signal": "ERROR", "note": str(e)}

        try:
            result["risk_factors"] = self.get_risk_factors(ticker)
        except Exception as e:
            logger.warning("Risk factor extraction failed for %s: %s", ticker, e)
            result["risk_factors"] = {"note": str(e)}

        try:
            result["risk_changes"] = self.get_risk_factor_changes(ticker)
        except Exception as e:
            logger.warning("Risk factor change detection failed for %s: %s", ticker, e)
            result["risk_changes"] = {"note": str(e)}

        return result

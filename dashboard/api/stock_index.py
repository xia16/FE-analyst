"""Comprehensive stock index for search autocomplete.

Downloads all US-listed securities from NASDAQ FTP (NYSE, NASDAQ, AMEX, ARCA)
and merges with portfolio holdings + universe YAML for enriched search.
Refreshed weekly via APScheduler.

Data sources:
    nasdaqlisted.txt  — NASDAQ-listed securities (~3,800)
    otherlisted.txt   — NYSE / AMEX / ARCA-listed securities (~3,000)
    portfolio.db      — User's portfolio holdings (sector, country)
    universe YAML     — Tracked companies (category, moat data)
"""

import json
import logging
import sqlite3
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import yaml

logger = logging.getLogger("stock_index")

DB_PATH = Path(__file__).parent / "portfolio.db"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# In-memory cache
_stock_cache: list[dict] = []
_cache_updated: str = ""


def _fetch_text(url: str) -> str:
    """Download a text file from URL."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


def _parse_nasdaq_listed(text: str) -> list[dict]:
    """Parse nasdaqlisted.txt (pipe-delimited).

    Columns: Symbol|Security Name|Market Category|Test Issue|Financial Status|
             Round Lot Size|ETF|NextShares
    """
    rows = []
    for line in text.strip().split("\n")[1:]:  # skip header
        if line.startswith("File Creation Time"):
            continue
        parts = line.split("|")
        if len(parts) < 2:
            continue
        ticker = parts[0].strip()
        name = parts[1].strip()
        is_test = parts[3].strip() == "Y" if len(parts) > 3 else False
        is_etf = parts[6].strip() == "Y" if len(parts) > 6 else False
        if is_test or not ticker or ticker == "Symbol":
            continue
        rows.append({
            "ticker": ticker,
            "name": name,
            "exchange": "NASDAQ",
            "market": "US",
            "type": "ETF" if is_etf else "Stock",
        })
    return rows


def _parse_other_listed(text: str) -> list[dict]:
    """Parse otherlisted.txt (pipe-delimited).

    Columns: ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|
             Round Lot Size|Test Issue|NASDAQ Symbol
    """
    exchange_map = {"A": "AMEX", "N": "NYSE", "P": "ARCA", "Z": "BATS", "V": "IEX"}
    rows = []
    for line in text.strip().split("\n")[1:]:
        if line.startswith("File Creation Time"):
            continue
        parts = line.split("|")
        if len(parts) < 3:
            continue
        ticker = parts[0].strip()
        name = parts[1].strip()
        exch_code = parts[2].strip()
        is_etf = parts[4].strip() == "Y" if len(parts) > 4 else False
        is_test = parts[6].strip() == "Y" if len(parts) > 6 else False
        if is_test or not ticker or ticker == "ACT Symbol":
            continue
        rows.append({
            "ticker": ticker,
            "name": name,
            "exchange": exchange_map.get(exch_code, exch_code),
            "market": "US",
            "type": "ETF" if is_etf else "Stock",
        })
    return rows


def _load_portfolio_holdings() -> dict[str, dict]:
    """Load holdings from portfolio.db for enrichment."""
    holdings = {}
    if not DB_PATH.exists():
        return holdings
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT ticker, name, sector, country FROM holdings").fetchall()
        for r in rows:
            holdings[r["ticker"]] = {
                "name": r["name"] or "",
                "sector": r["sector"] or "",
                "country": r["country"] or "",
                "source": "holding",
            }
        conn.close()
    except Exception as e:
        logger.warning("Could not load portfolio holdings: %s", e)
    return holdings


def _load_universe_stocks() -> dict[str, dict]:
    """Load tracked companies from all domain YAML configs."""
    universe = {}
    domains_path = PROJECT_ROOT / "configs" / "domains.yaml"
    if not domains_path.exists():
        return universe
    try:
        with open(domains_path) as f:
            domains_data = yaml.safe_load(f) or {}
        for entry in domains_data.get("domains", []):
            file_path = PROJECT_ROOT / "configs" / entry["file"]
            if not file_path.exists():
                continue
            with open(file_path) as f:
                domain_data = yaml.safe_load(f) or {}
            categories = domain_data.get("categories", {})
            for cat_key, cat_val in categories.items():
                for company in cat_val.get("companies", []):
                    ticker = company.get("adr") or company.get("ticker", "")
                    if ticker:
                        universe[ticker] = {
                            "name": company.get("name", ""),
                            "sector": cat_val.get("label", cat_key),
                            "country": company.get("country", ""),
                            "source": "universe",
                        }
                    # Also add local ticker if different
                    local = company.get("ticker", "")
                    if local and local != ticker:
                        universe[local] = {
                            "name": company.get("name", ""),
                            "sector": cat_val.get("label", cat_key),
                            "country": company.get("country", ""),
                            "source": "universe",
                        }
    except Exception as e:
        logger.warning("Could not load universe: %s", e)
    return universe


def build_index() -> int:
    """Build the comprehensive stock index.

    Downloads NASDAQ FTP files, merges with portfolio + universe data.
    Returns total number of stocks indexed.
    """
    global _stock_cache, _cache_updated

    all_stocks: dict[str, dict] = {}  # keyed by ticker for dedup

    # --- Tier 1: NASDAQ FTP data (US-listed securities) ---
    try:
        nasdaq_text = _fetch_text(NASDAQ_LISTED_URL)
        nasdaq_stocks = _parse_nasdaq_listed(nasdaq_text)
        for s in nasdaq_stocks:
            all_stocks[s["ticker"]] = s
        logger.info("Loaded %d NASDAQ-listed stocks", len(nasdaq_stocks))
    except Exception as e:
        logger.error("Failed to fetch nasdaqlisted.txt: %s", e)

    try:
        other_text = _fetch_text(OTHER_LISTED_URL)
        other_stocks = _parse_other_listed(other_text)
        for s in other_stocks:
            if s["ticker"] not in all_stocks:
                all_stocks[s["ticker"]] = s
        logger.info("Loaded %d other-listed stocks (NYSE/AMEX/ARCA)", len(other_stocks))
    except Exception as e:
        logger.error("Failed to fetch otherlisted.txt: %s", e)

    # --- Tier 2: Enrich with portfolio holdings ---
    holdings = _load_portfolio_holdings()
    for ticker, info in holdings.items():
        if ticker in all_stocks:
            # Enrich existing entry with portfolio data
            all_stocks[ticker]["sector"] = info["sector"]
            all_stocks[ticker]["country"] = info["country"]
            all_stocks[ticker]["source"] = "holding"
            if info["name"]:
                all_stocks[ticker]["name"] = info["name"]
        else:
            # Add portfolio-only stock (international, OTC, etc.)
            all_stocks[ticker] = {
                "ticker": ticker,
                "name": info["name"],
                "exchange": "",
                "market": info["country"] or "",
                "type": "Stock",
                "sector": info["sector"],
                "country": info["country"],
                "source": "holding",
            }

    # --- Tier 3: Enrich with universe data ---
    universe = _load_universe_stocks()
    for ticker, info in universe.items():
        if ticker in all_stocks:
            if not all_stocks[ticker].get("sector"):
                all_stocks[ticker]["sector"] = info["sector"]
            if not all_stocks[ticker].get("country"):
                all_stocks[ticker]["country"] = info["country"]
            # Mark as universe if not already a holding
            if all_stocks[ticker].get("source") != "holding":
                all_stocks[ticker]["source"] = "universe"
            if info["name"] and not all_stocks[ticker].get("name"):
                all_stocks[ticker]["name"] = info["name"]
        else:
            all_stocks[ticker] = {
                "ticker": ticker,
                "name": info["name"],
                "exchange": "",
                "market": info["country"] or "",
                "type": "Stock",
                "sector": info["sector"],
                "country": info["country"],
                "source": "universe",
            }

    # Build final list
    _stock_cache = sorted(all_stocks.values(), key=lambda s: s["ticker"])
    _cache_updated = datetime.utcnow().isoformat()

    logger.info("Built stock index: %d stocks (cache updated %s)", len(_stock_cache), _cache_updated)
    return len(_stock_cache)


def get_all_stocks() -> tuple[list[dict], str]:
    """Return the cached stock index and last-updated timestamp."""
    if not _stock_cache:
        build_index()
    return _stock_cache, _cache_updated


def schedule_refresh(scheduler):
    """Register weekly index refresh with APScheduler (Monday 02:00 UTC)."""
    scheduler.add_job(
        build_index,
        "cron",
        day_of_week="mon",
        hour=2,
        minute=0,
        id="stock_index_refresh",
        replace_existing=True,
    )
    logger.info("Scheduled weekly stock index refresh (Monday 02:00 UTC)")

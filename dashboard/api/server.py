"""
FE-Analyst Dashboard API Server
Multi-domain investment analysis dashboard.
"""

import os
import re
import sys
import json
import yaml
import math
import time
import uuid
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import yfinance as yf
import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.background import BackgroundScheduler

from telegram_bot import (
    parse_trade_message, record_trade, get_holdings, get_trades,
    get_portfolio_summary, init_db,
)

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

app = FastAPI(title="FE-Analyst Dashboard API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Multi-domain config loaders
# ---------------------------------------------------------------------------

def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_domains_registry() -> list[dict]:
    """Load the domains registry from configs/domains.yaml."""
    path = PROJECT_ROOT / "configs" / "domains.yaml"
    if not path.exists():
        return []
    data = load_yaml(path)
    return data.get("domains", [])


def load_domain_file(domain_id: str) -> dict:
    """Load a specific domain's YAML file by its registry ID."""
    registry = load_domains_registry()
    for entry in registry:
        if entry["id"] == domain_id:
            path = PROJECT_ROOT / "configs" / entry["file"]
            if path.exists():
                return load_yaml(path)
            raise HTTPException(status_code=404, detail=f"Domain file not found: {entry['file']}")
    raise HTTPException(status_code=404, detail=f"Unknown domain: {domain_id}")


def _domain_meta(domain_id: str) -> dict:
    """Extract domain metadata block from a domain file."""
    full = load_domain_file(domain_id)
    return full.get("domain", {})


def _domain_portfolio(domain_id: str) -> dict:
    """Get portfolio recommendations for a domain."""
    return _domain_meta(domain_id).get("portfolio", {})


def _format_domain_meta(domain_id: str, meta: dict, registry_entry: dict) -> dict:
    """Format domain metadata for the API response."""
    return {
        "id": domain_id,
        "name": meta.get("name", domain_id.replace("_", " ").title()),
        "description": meta.get("description", ""),
        "color": registry_entry.get("color", "#3b82f6"),
        "tabLabel": meta.get("tab_label", "Universe"),
        "heatmapLabel": meta.get("heatmap_label", "Heatmap"),
        "tiers": {
            k: {"label": v.get("label", k), "color": v.get("color", "#3b82f6"), "description": v.get("description", "")}
            for k, v in meta.get("tiers", {}).items()
        },
        "dimensions": {
            k: {"label": v.get("label", k), "description": v.get("description", "")}
            for k, v in meta.get("dimensions", {}).items()
        },
        "extraMetrics": {
            k: {"label": v.get("label", k), "suffix": v.get("suffix", ""), "color": v.get("color", "#8b8d97")}
            for k, v in meta.get("extra_metrics", {}).items()
        },
        "hasPortfolio": bool(meta.get("portfolio")),
    }


def _build_universe_response(domain_id: str) -> dict:
    """Build the universe response for a domain."""
    full = load_domain_file(domain_id)
    domain = full.get("domain", {})
    dim_keys = list(domain.get("dimensions", {}).keys())
    extra_keys = list(domain.get("extra_metrics", {}).keys())
    portfolio_recs = domain.get("portfolio", {})

    result = {}
    for cat_key, cat_data in full.get("categories", {}).items():
        companies = []
        for c in cat_data.get("companies", []):
            dim_values = [c.get(dk, 0) for dk in dim_keys]
            moat_score = sum(dim_values) / len(dim_values) if dim_values else 0
            breakdown = {dk: c.get(dk) for dk in dim_keys}
            extras = {ek: c.get(ek) for ek in extra_keys}
            companies.append({
                "ticker": c["ticker"],
                "name": c["name"],
                "adr": c.get("adr"),
                "country": c.get("country"),
                "tier": c.get("choke_point_tier"),
                "moat": c.get("moat"),
                "moatScore": round(moat_score, 1),
                "breakdown": breakdown,
                "extras": extras,
                "recommendation": portfolio_recs.get(c.get("adr") or c["ticker"], {}),
            })
        result[cat_key] = {
            "label": cat_data.get("label", cat_key.replace("_", " ").title()),
            "color": cat_data.get("color", "#3b82f6"),
            "description": cat_data.get("description"),
            "theme": cat_data.get("choke_point_theme"),
            "companies": companies,
        }
    return result


def _build_heatmap_response(domain_id: str) -> list:
    """Build the heatmap response for a domain."""
    full = load_domain_file(domain_id)
    domain = full.get("domain", {})
    dim_keys = list(domain.get("dimensions", {}).keys())

    data = []
    for cat_key, cat_data in full.get("categories", {}).items():
        cat_label = cat_data.get("label", cat_key.replace("_", " ").title())
        cat_color = cat_data.get("color", "#3b82f6")
        for c in cat_data.get("companies", []):
            entry = {
                "ticker": c.get("adr") or c["ticker"],
                "name": c["name"],
                "category": cat_key,
                "categoryLabel": cat_label,
                "categoryColor": cat_color,
                "tier": c.get("choke_point_tier"),
            }
            dim_values = []
            for dk in dim_keys:
                val = c.get(dk, 0)
                entry[dk] = val
                dim_values.append(val)
            entry["composite"] = round(sum(dim_values) / len(dim_values), 1) if dim_values else 0
            data.append(entry)
    data.sort(key=lambda x: x["composite"], reverse=True)
    return data


# ---------------------------------------------------------------------------
# In-memory alert store
# ---------------------------------------------------------------------------
alerts_store: list[dict] = []

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_val(v):
    """Convert numpy/pandas values to JSON-safe Python types."""
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        if math.isnan(v) or math.isinf(v):
            return None
        return round(float(v), 4)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return v


# In-memory cache for quotes
_quote_cache: dict[str, tuple[datetime, dict]] = {}
QUOTE_CACHE_TTL = timedelta(minutes=5)

# Twelve Data API key (fallback provider)
TWELVEDATA_API_KEY = os.environ.get("TWELVEDATA_API_KEY", "")

# Company name lookup from ALL domains
_name_lookup: dict[str, str] = {}


def _build_name_lookup():
    """Build ticker -> name mapping from all domains."""
    global _name_lookup
    if _name_lookup:
        return
    try:
        for entry in load_domains_registry():
            path = PROJECT_ROOT / "configs" / entry["file"]
            if not path.exists():
                continue
            data = load_yaml(path)
            for cat in data.get("categories", {}).values():
                for c in cat.get("companies", []):
                    _name_lookup[c["ticker"]] = c["name"]
                    if c.get("adr"):
                        _name_lookup[c["adr"]] = c["name"]
    except Exception:
        pass


def _fetch_twelvedata_bulk_quotes(tickers: list[str]) -> dict[str, dict]:
    """Fetch quotes for multiple tickers via Twelve Data API.

    Free tier: 8 API credits/min (each symbol = 1 credit).
    Sends all symbols in one request — Twelve Data returns what it can.
    """
    if not tickers or not TWELVEDATA_API_KEY:
        return {}
    _build_name_lookup()
    quotes = {}
    symbols = ",".join(tickers)
    try:
        params = urllib.parse.urlencode({"symbol": symbols, "apikey": TWELVEDATA_API_KEY})
        url = f"https://api.twelvedata.com/quote?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "FE-Analyst/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        # Rate limit error returns {"code": 429, ...}
        if isinstance(data, dict) and data.get("code") == 429:
            return {}
        # Single symbol: direct dict; multiple: dict keyed by symbol
        items = {}
        if len(tickers) == 1:
            if "symbol" in data:
                items[tickers[0]] = data
        else:
            for sym in tickers:
                entry = data.get(sym)
                if isinstance(entry, dict) and "symbol" in entry:
                    items[sym] = entry
        for sym, q in items.items():
            close = _safe_float(q.get("close"))
            prev = _safe_float(q.get("previous_close"))
            change = _safe_float(q.get("change"))
            change_pct = _safe_float(q.get("percent_change"))
            w52 = q.get("fifty_two_week", {})
            quote = {
                "ticker": sym,
                "name": q.get("name") or _name_lookup.get(sym, sym),
                "price": close,
                "previousClose": prev,
                "change": change,
                "changePct": change_pct,
                "currency": q.get("currency", "USD"),
                "marketCap": None,
                "volume": _safe_float(q.get("volume")),
                "fiftyTwoWeekHigh": _safe_float(w52.get("high")),
                "fiftyTwoWeekLow": _safe_float(w52.get("low")),
                "trailingPE": None,
                "forwardPE": None,
                "dividendYield": None,
                "beta": None,
                "averageVolume": _safe_float(q.get("average_volume")),
                "timestamp": datetime.utcnow().isoformat(),
            }
            quotes[sym] = quote
            _quote_cache[sym] = (datetime.utcnow(), quote)
    except Exception:
        pass
    return quotes


def _safe_float(v) -> float | None:
    """Convert string/number to float, returning None on failure."""
    if v is None:
        return None
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 4)
    except (ValueError, TypeError):
        return None


def _fetch_quotes_parallel(tickers: list[str]) -> dict[str, dict]:
    """Fetch quotes in parallel using ThreadPoolExecutor as fallback."""
    results = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(get_quote, t): t for t in tickers}
        for future in as_completed(futures, timeout=10):
            ticker = futures[future]
            try:
                results[ticker] = future.result()
            except Exception:
                results[ticker] = {"ticker": ticker, "error": "Failed to fetch"}
    # Mark any tickers that didn't complete in time
    for future, ticker in futures.items():
        if ticker not in results:
            results[ticker] = {"ticker": ticker, "name": _name_lookup.get(ticker, ticker), "error": "Timeout"}
            future.cancel()
    return results


def _get_bulk_quotes(tickers: list[str]) -> dict[str, dict]:
    """Get quotes for multiple tickers: cache -> Twelve Data bulk -> parallel Yahoo fallback."""
    _build_name_lookup()
    uncached = []
    cached = {}
    for t in tickers:
        if t in _quote_cache:
            cached_time, cached_data = _quote_cache[t]
            if datetime.utcnow() - cached_time < QUOTE_CACHE_TTL:
                cached[t] = cached_data
                continue
        uncached.append(t)

    if not uncached:
        return cached

    # Try Twelve Data bulk endpoint first
    bulk = _fetch_twelvedata_bulk_quotes(uncached)
    still_missing = [t for t in uncached if t not in bulk]

    # Parallel Yahoo v8 chart fallback for any tickers Twelve Data missed
    parallel = _fetch_quotes_parallel(still_missing) if still_missing else {}

    return {**cached, **bulk, **parallel}


def _fetch_yahoo_chart(ticker: str, range_: str = "1mo", interval: str = "1d") -> dict | None:
    """Fetch from Yahoo v8 chart API directly (avoids yfinance rate limits)."""
    urls = [
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
        f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}",
    ]
    qs = urllib.parse.urlencode({"range": range_, "interval": interval, "includePrePost": "false"})
    ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    for base_url in urls:
        try:
            req = urllib.request.Request(f"{base_url}?{qs}", headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            result = data.get("chart", {}).get("result", [])
            if result:
                return result[0]
        except Exception:
            continue
    return None


def get_quote(ticker: str) -> dict:
    """Fetch live quote via Yahoo v8 chart API with caching."""
    _build_name_lookup()
    if ticker in _quote_cache:
        cached_time, cached_data = _quote_cache[ticker]
        if datetime.utcnow() - cached_time < QUOTE_CACHE_TTL:
            return cached_data

    chart = _fetch_yahoo_chart(ticker, range_="1mo", interval="1d")
    if not chart:
        return {"ticker": ticker, "name": _name_lookup.get(ticker, ticker), "error": "No data (rate limited or invalid ticker)"}

    meta = chart.get("meta", {})
    indicators = chart.get("indicators", {}).get("quote", [{}])[0]
    closes = [c for c in indicators.get("close", []) if c is not None]
    volumes = [v for v in indicators.get("volume", []) if v is not None]

    if not closes:
        return {"ticker": ticker, "name": _name_lookup.get(ticker, ticker), "error": "No price data"}

    price = safe_val(closes[-1])
    # Use second-to-last daily close as previous close (yesterday's close).
    # chartPreviousClose is the close at the START of the chart range (1mo ago), not yesterday.
    prev_close = safe_val(closes[-2]) if len(closes) >= 2 else None

    change = round(price - prev_close, 4) if price and prev_close else None
    change_pct = round((change / prev_close) * 100, 2) if change and prev_close else None

    result = {
        "ticker": ticker,
        "name": meta.get("shortName") or _name_lookup.get(ticker, ticker),
        "price": price,
        "previousClose": prev_close,
        "change": change,
        "changePct": change_pct,
        "currency": meta.get("currency", "USD"),
        "marketCap": None,
        "volume": safe_val(volumes[-1]) if volumes else None,
        "fiftyTwoWeekHigh": safe_val(meta.get("fiftyTwoWeekHigh") or max(closes)),
        "fiftyTwoWeekLow": safe_val(meta.get("fiftyTwoWeekLow") or min(closes)),
        "trailingPE": None,
        "forwardPE": None,
        "dividendYield": None,
        "beta": None,
        "timestamp": datetime.utcnow().isoformat(),
    }
    _quote_cache[ticker] = (datetime.utcnow(), result)
    return result


def _chart_to_dataframe(chart: dict) -> pd.DataFrame:
    """Convert Yahoo v8 chart response to a pandas DataFrame."""
    timestamps = chart.get("timestamp", [])
    indicators = chart.get("indicators", {}).get("quote", [{}])[0]
    if not timestamps:
        return pd.DataFrame()
    df = pd.DataFrame({
        "Open": indicators.get("open", []),
        "High": indicators.get("high", []),
        "Low": indicators.get("low", []),
        "Close": indicators.get("close", []),
        "Volume": indicators.get("volume", []),
    }, index=pd.to_datetime(timestamps, unit="s", utc=True))
    df.index.name = "Date"
    return df.dropna(subset=["Close"])


def _get_history_df(ticker: str, period: str = "6mo") -> pd.DataFrame:
    """Get history DataFrame, trying direct API first then yfinance."""
    chart = _fetch_yahoo_chart(ticker, range_=period, interval="1d")
    if chart:
        df = _chart_to_dataframe(chart)
        if not df.empty:
            return df
    try:
        return yf.Ticker(ticker).history(period=period)
    except Exception:
        return pd.DataFrame()


def compute_technicals(ticker: str, period: str = "6mo") -> dict:
    """Compute key technical indicators."""
    try:
        hist = _get_history_df(ticker, period)
        if hist.empty:
            return {"ticker": ticker, "error": "No data"}

        close = hist["Close"]
        volume = hist["Volume"]

        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9).mean()
        macd_hist = macd_line - signal_line

        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        bb_upper = sma20 + 2 * std20
        bb_lower = sma20 - 2 * std20

        sma50 = close.rolling(50).mean()
        sma200 = close.rolling(200).mean()

        current = close.iloc[-1]
        high_52w = close.rolling(252).max().iloc[-1] if len(close) >= 252 else close.max()
        low_52w = close.rolling(252).min().iloc[-1] if len(close) >= 252 else close.min()
        dist_from_high = ((current - high_52w) / high_52w * 100) if high_52w else None
        dist_from_low = ((current - low_52w) / low_52w * 100) if low_52w else None

        rsi_val = rsi.iloc[-1]
        macd_val = macd_hist.iloc[-1]
        bb_position = (current - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1]) if (bb_upper.iloc[-1] - bb_lower.iloc[-1]) != 0 else 0.5

        signals = []
        if rsi_val < 30:
            signals.append({"type": "RSI_OVERSOLD", "message": f"RSI at {rsi_val:.1f} — oversold", "bullish": True})
        elif rsi_val > 70:
            signals.append({"type": "RSI_OVERBOUGHT", "message": f"RSI at {rsi_val:.1f} — overbought", "bullish": False})
        if macd_val > 0 and macd_hist.iloc[-2] <= 0:
            signals.append({"type": "MACD_CROSS_UP", "message": "MACD bullish crossover", "bullish": True})
        elif macd_val < 0 and macd_hist.iloc[-2] >= 0:
            signals.append({"type": "MACD_CROSS_DOWN", "message": "MACD bearish crossover", "bullish": False})
        if bb_position < 0.05:
            signals.append({"type": "BB_LOWER", "message": "Price near lower Bollinger Band", "bullish": True})
        elif bb_position > 0.95:
            signals.append({"type": "BB_UPPER", "message": "Price near upper Bollinger Band", "bullish": False})
        if len(sma50.dropna()) > 0 and len(sma200.dropna()) > 0:
            if current > sma50.iloc[-1] > sma200.iloc[-1]:
                signals.append({"type": "TREND_UP", "message": "Price above SMA50 > SMA200 — uptrend", "bullish": True})
            elif current < sma50.iloc[-1] < sma200.iloc[-1]:
                signals.append({"type": "TREND_DOWN", "message": "Price below SMA50 < SMA200 — downtrend", "bullish": False})

        return {
            "ticker": ticker,
            "rsi": safe_val(rsi_val),
            "macd": safe_val(macd_val),
            "macdLine": safe_val(macd_line.iloc[-1]),
            "signalLine": safe_val(signal_line.iloc[-1]),
            "sma50": safe_val(sma50.iloc[-1]),
            "sma200": safe_val(sma200.iloc[-1]) if len(sma200.dropna()) > 0 else None,
            "bbUpper": safe_val(bb_upper.iloc[-1]),
            "bbLower": safe_val(bb_lower.iloc[-1]),
            "bbPosition": safe_val(bb_position),
            "distFromHigh": safe_val(dist_from_high),
            "distFromLow": safe_val(dist_from_low),
            "signals": signals,
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


def check_buy_opportunities():
    """Scan ALL domains for buy signals. Called daily by scheduler."""
    global alerts_store
    new_alerts = []

    for reg in load_domains_registry():
        domain_id = reg["id"]
        try:
            full = load_yaml(PROJECT_ROOT / "configs" / reg["file"])
        except Exception:
            continue
        domain_meta = full.get("domain", {})
        domain_name = domain_meta.get("name", domain_id)
        portfolio_recs = domain_meta.get("portfolio", {})

        all_tickers = set()
        for cat in full.get("categories", {}).values():
            for company in cat.get("companies", []):
                adr = company.get("adr")
                ticker = adr if adr else company["ticker"]
                all_tickers.add((ticker, company["name"], company.get("choke_point_tier", "")))

        for ticker, name, tier in all_tickers:
            try:
                tech = compute_technicals(ticker)
                if "error" in tech:
                    continue

                bullish_signals = [s for s in tech.get("signals", []) if s.get("bullish")]
                rsi = tech.get("rsi")
                dist_from_high = tech.get("distFromHigh")

                is_opportunity = False
                reasons = []

                if rsi and rsi < 35:
                    is_opportunity = True
                    reasons.append(f"RSI oversold at {rsi:.1f}")
                if dist_from_high and dist_from_high < -25:
                    is_opportunity = True
                    reasons.append(f"{dist_from_high:.1f}% from 52-week high")
                if len(bullish_signals) >= 2:
                    is_opportunity = True
                    reasons.append(f"{len(bullish_signals)} bullish technical signals")
                if tech.get("bbPosition") and tech["bbPosition"] < 0.1:
                    is_opportunity = True
                    reasons.append("Near lower Bollinger Band")

                if is_opportunity:
                    new_alerts.append({
                        "id": f"{ticker}-{datetime.utcnow().strftime('%Y%m%d')}",
                        "ticker": ticker,
                        "name": name,
                        "tier": tier,
                        "domainId": domain_id,
                        "domainName": domain_name,
                        "timestamp": datetime.utcnow().isoformat(),
                        "reasons": reasons,
                        "rsi": safe_val(rsi),
                        "distFromHigh": safe_val(dist_from_high),
                        "signals": bullish_signals,
                        "recommendation": portfolio_recs.get(ticker, {}),
                    })
            except Exception:
                continue

    if new_alerts:
        alerts_store = new_alerts + alerts_store
        alerts_store = alerts_store[:200]

    return new_alerts


# ---------------------------------------------------------------------------
# Scheduler — runs buy opportunity scan daily at 09:00 UTC
# ---------------------------------------------------------------------------
scheduler = BackgroundScheduler()
scheduler.add_job(check_buy_opportunities, "cron", hour=9, minute=0)
scheduler.start()

# ---------------------------------------------------------------------------
# API Routes — Domain registry
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "FE-Analyst Dashboard API", "version": "2.0.0"}


@app.get("/api/domains")
def list_domains():
    """List all registered domains."""
    registry = load_domains_registry()
    result = []
    for entry in registry:
        try:
            path = PROJECT_ROOT / "configs" / entry["file"]
            data = load_yaml(path)
            meta = data.get("domain", {})
            result.append({
                "id": entry["id"],
                "name": meta.get("name", entry["id"].replace("_", " ").title()),
                "description": meta.get("description", ""),
                "color": entry.get("color", "#3b82f6"),
                "hasPortfolio": bool(meta.get("portfolio")),
            })
        except Exception:
            continue
    return {"domains": result}


# ---------------------------------------------------------------------------
# API Routes — Domain-scoped
# ---------------------------------------------------------------------------

@app.get("/api/domains/{domain_id}")
def get_domain_meta(domain_id: str):
    """Return full metadata for a specific domain."""
    registry = load_domains_registry()
    reg = next((r for r in registry if r["id"] == domain_id), None)
    if not reg:
        raise HTTPException(status_code=404, detail=f"Unknown domain: {domain_id}")
    meta = _domain_meta(domain_id)
    return _format_domain_meta(domain_id, meta, reg)


@app.get("/api/domains/{domain_id}/universe")
def get_domain_universe(domain_id: str):
    """Return the universe for a specific domain."""
    return _build_universe_response(domain_id)


@app.get("/api/domains/{domain_id}/heatmap")
def get_domain_heatmap(domain_id: str):
    """Return the heatmap for a specific domain."""
    return _build_heatmap_response(domain_id)


@app.get("/api/domains/{domain_id}/portfolio")
def get_domain_portfolio(domain_id: str):
    """Return portfolio with live quotes for a specific domain."""
    portfolio_recs = _domain_portfolio(domain_id)
    if not portfolio_recs:
        return {"portfolio": [], "timestamp": datetime.utcnow().isoformat()}
    tickers = list(portfolio_recs.keys())
    all_quotes = _get_bulk_quotes(tickers)
    results = []
    for ticker, rec in portfolio_recs.items():
        quote = all_quotes.get(ticker, {"ticker": ticker, "name": _name_lookup.get(ticker, ticker), "error": "No data"})
        quote["recommendation"] = rec
        if not quote.get("forwardPE"):
            quote["forwardPE"] = rec.get("fwd_pe")
        results.append(quote)
    return {"portfolio": results, "timestamp": datetime.utcnow().isoformat()}


# ---------------------------------------------------------------------------
# API Routes — Global (cross-domain)
# ---------------------------------------------------------------------------

@app.get("/api/quote/{ticker}")
def get_single_quote(ticker: str):
    """Get live quote for a single ticker."""
    return get_quote(ticker)


@app.get("/api/quotes")
def get_bulk_quotes(tickers: str):
    """Get live quotes for comma-separated tickers."""
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    all_quotes = _get_bulk_quotes(ticker_list)
    return {"quotes": [all_quotes.get(t, {"ticker": t, "error": "No data"}) for t in ticker_list]}


@app.get("/api/technicals/{ticker}")
def get_technicals(ticker: str, period: str = "6mo"):
    """Get technical indicators for a ticker."""
    return compute_technicals(ticker, period)


@app.get("/api/history/{ticker}")
def get_history(ticker: str, period: str = "1y", interval: str = "1d"):
    """Get OHLCV price history."""
    try:
        hist = _get_history_df(ticker, period)
        if hist.empty:
            raise HTTPException(status_code=404, detail="No data found")
        records = []
        for idx, row in hist.iterrows():
            records.append({
                "date": idx.isoformat(),
                "open": safe_val(row["Open"]),
                "high": safe_val(row["High"]),
                "low": safe_val(row["Low"]),
                "close": safe_val(row["Close"]),
                "volume": safe_val(row["Volume"]),
            })
        return {"ticker": ticker, "period": period, "interval": interval, "data": records}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/alerts")
def get_alerts():
    """Get recent buy-opportunity alerts (cross-domain)."""
    return {"alerts": alerts_store, "count": len(alerts_store)}


@app.post("/api/alerts/scan")
def trigger_scan():
    """Manually trigger a buy-opportunity scan across all domains."""
    new_alerts = check_buy_opportunities()
    return {"newAlerts": len(new_alerts), "totalAlerts": len(alerts_store), "alerts": new_alerts}


# ---------------------------------------------------------------------------
# Telegram Bot Webhook & Portfolio endpoints
# ---------------------------------------------------------------------------

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8461444330:AAHmtc2ZehwiCFtBe8t-cx4W2XM34ntSK5M")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "8387613359")


def _send_telegram(text: str):
    """Send a message back to the Telegram chat."""
    try:
        params = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"})
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "FE-Analyst/1.0"})
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        logger_tg = __import__("logging").getLogger("telegram")
        logger_tg.warning(f"Failed to send Telegram message: {e}")


@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    """Receive Telegram bot updates (webhook mode)."""
    body = await request.json()
    message = body.get("message", {})
    text = message.get("text", "")

    if not text:
        return {"ok": True}

    # Try to parse as a trade message
    trade = parse_trade_message(text)
    if trade:
        result = record_trade(trade)
        if result["status"] == "duplicate":
            return {"ok": True, "status": "duplicate"}

        # Send confirmation back to Telegram
        t = result["trade"]
        h = result["holding"]
        emoji = "🟢" if t["action"] == "BUY" else "🔴"
        msg = (
            f"{emoji} *{t['action']}* {t['quantity']} x {t['ticker']}\n"
            f"Price: ${t['price']:.2f} | Total: ${t['total_value']:.2f}\n"
        )
        if h.get("quantity", 0) > 0:
            msg += f"Holdings: {h['quantity']} shares @ ${h.get('avg_cost', 0):.2f} avg"
        else:
            msg += "Position closed"
        _send_telegram(msg)
        return {"ok": True, "result": result}

    # Handle commands
    if text.strip().lower() in ("/holdings", "/portfolio", "holdings", "portfolio"):
        holdings = get_holdings()
        if not holdings:
            _send_telegram("📊 No holdings currently.")
        else:
            lines = ["📊 *Current Holdings*\n"]
            total = 0
            for h in holdings:
                val = h["quantity"] * h["avg_cost"]
                total += val
                lines.append(f"`{h['ticker']:6s}` {h['quantity']:>6d} @ ${h['avg_cost']:.2f} = ${val:,.0f}")
            lines.append(f"\n*Total Invested:* ${total:,.0f}")
            _send_telegram("\n".join(lines))
        return {"ok": True}

    if text.strip().lower() in ("/trades", "trades"):
        trades = get_trades(10)
        if not trades:
            _send_telegram("📋 No trades recorded yet.")
        else:
            lines = ["📋 *Recent Trades*\n"]
            for t in trades:
                emoji = "🟢" if t["action"] == "BUY" else "🔴"
                lines.append(f"{emoji} {t['action']} {t['quantity']}x {t['ticker']} @ ${t['price']:.2f} — {t['timestamp'][:10]}")
            _send_telegram("\n".join(lines))
        return {"ok": True}

    return {"ok": True}


@app.post("/api/telegram/process")
async def process_trade_message(request: Request):
    """Process a raw trade SMS message (for MacroDroid HTTP forwarding)."""
    body = await request.json()
    text = body.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")

    trade = parse_trade_message(text)
    if not trade:
        return {"status": "not_a_trade", "text": text}

    result = record_trade(trade)
    return result


def _get_eur_usd_rate() -> float:
    """Fetch EUR/USD exchange rate from yfinance. Falls back to 1.05."""
    try:
        tk = yf.Ticker("EURUSD=X")
        return tk.fast_info.last_price or 1.05
    except Exception:
        return 1.05


@app.get("/api/holdings")
def api_get_holdings():
    """Get current portfolio holdings with live quotes."""
    holdings = get_holdings()
    tickers = [h["ticker"] for h in holdings]

    # Fetch live quotes for all holdings
    live_quotes = _get_bulk_quotes(tickers) if tickers else {}

    # Fetch EUR/USD rate if any holdings are EUR-denominated
    has_eur = any(h.get("currency", "USD") == "EUR" for h in holdings)
    eur_usd = _get_eur_usd_rate() if has_eur else None

    enriched = []
    for h in holdings:
        quote = live_quotes.get(h["ticker"], {})
        current_price = quote.get("price")
        currency = h.get("currency", "USD")

        # For EUR holdings: price from yfinance is in EUR, cost basis is in EUR
        # Convert both to USD for portfolio totals
        if currency == "EUR" and eur_usd and current_price:
            price_usd = current_price * eur_usd
            avg_cost_usd = h["avg_cost"] * eur_usd
            market_value = price_usd * h["quantity"]
            cost_basis = avg_cost_usd * h["quantity"]
        else:
            price_usd = current_price
            avg_cost_usd = h["avg_cost"]
            market_value = current_price * h["quantity"] if current_price else None
            cost_basis = h["total_invested"]

        unrealized_pnl = (market_value - cost_basis) if market_value else None
        unrealized_pct = (unrealized_pnl / cost_basis * 100) if unrealized_pnl and cost_basis else None

        enriched.append({
            **h,
            "sector": h.get("sector", ""),
            "country": h.get("country", ""),
            "currency": currency,
            "current_price": current_price,
            "current_price_usd": round(price_usd, 2) if price_usd else None,
            "avg_cost_usd": round(avg_cost_usd, 2),
            "market_value": round(market_value, 2) if market_value else None,
            "unrealized_pnl": round(unrealized_pnl, 2) if unrealized_pnl else None,
            "unrealized_pct": round(unrealized_pct, 2) if unrealized_pct else None,
            "change_pct": quote.get("changePct"),
            "quote_name": quote.get("name"),
        })

    total_invested = sum(h["avg_cost_usd"] * h["quantity"] for h in enriched)
    total_market_value = sum(h["market_value"] for h in enriched if h["market_value"])
    total_pnl = total_market_value - total_invested if total_market_value else None

    # Detect portfolio name(s) from holdings
    portfolio_names = list(set(h.get("portfolio_name", "") for h in holdings if h.get("portfolio_name")))

    return {
        "holdings": enriched,
        "summary": {
            "count": len(holdings),
            "total_invested": round(total_invested, 2),
            "total_market_value": round(total_market_value, 2) if total_market_value else None,
            "total_pnl": round(total_pnl, 2) if total_pnl else None,
            "total_pnl_pct": round(total_pnl / total_invested * 100, 2) if total_pnl and total_invested else None,
            "portfolio_name": portfolio_names[0] if len(portfolio_names) == 1 else ", ".join(portfolio_names) if portfolio_names else None,
            "eur_usd_rate": eur_usd,
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/trades")
def api_get_trades(limit: int = 50):
    """Get trade history."""
    return {"trades": get_trades(limit)}


# ---------------------------------------------------------------------------
# Manual position adjustment endpoints
# ---------------------------------------------------------------------------

from pydantic import BaseModel

class PositionUpdate(BaseModel):
    ticker: str
    name: Optional[str] = None
    quantity: int
    avg_cost: float
    sector: Optional[str] = ""
    country: Optional[str] = ""
    currency: Optional[str] = "USD"
    portfolio_name: Optional[str] = "SG Brokerage"


@app.post("/api/holdings/adjust")
def adjust_position(pos: PositionUpdate):
    """Add or update a position manually."""
    import sqlite3 as _sql
    db_path = Path(__file__).parent / "portfolio.db"
    conn = _sql.connect(db_path)

    # Ensure extra columns exist
    for col in ("sector", "country", "portfolio_name", "currency"):
        try:
            conn.execute(f"ALTER TABLE holdings ADD COLUMN {col} TEXT DEFAULT ''")
        except _sql.OperationalError:
            pass

    total_invested = pos.quantity * pos.avg_cost
    conn.execute(
        """INSERT OR REPLACE INTO holdings
           (ticker, name, exchange, quantity, avg_cost, total_invested, sector, country, portfolio_name, currency)
           VALUES (?, ?, '', ?, ?, ?, ?, ?, ?, ?)""",
        (pos.ticker.upper(), pos.name or pos.ticker.upper(), pos.quantity,
         pos.avg_cost, total_invested, pos.sector, pos.country, pos.portfolio_name, pos.currency),
    )
    conn.commit()
    conn.close()
    return {"status": "ok", "ticker": pos.ticker.upper(), "quantity": pos.quantity, "avg_cost": pos.avg_cost}


@app.delete("/api/holdings/{ticker}")
def remove_position(ticker: str):
    """Remove a position entirely."""
    import sqlite3 as _sql
    db_path = Path(__file__).parent / "portfolio.db"
    conn = _sql.connect(db_path)
    conn.execute("DELETE FROM holdings WHERE ticker = ?", (ticker.upper(),))
    conn.commit()
    conn.close()
    return {"status": "ok", "removed": ticker.upper()}


# ---------------------------------------------------------------------------
# Holdings analytics endpoints
# ---------------------------------------------------------------------------

@app.get("/api/holdings/allocation")
def holdings_allocation():
    """Get portfolio allocation by sector and country."""
    holdings = get_holdings()
    if not holdings:
        return {"sectors": [], "countries": [], "total_invested": 0}

    tickers = [h["ticker"] for h in holdings]
    quotes = _get_bulk_quotes(tickers) if tickers else {}

    sector_map = {}
    country_map = {}
    total_value = 0

    for h in holdings:
        quote = quotes.get(h["ticker"], {})
        price = quote.get("price")
        value = price * h["quantity"] if price else h["total_invested"]
        total_value += value

        sector = h.get("sector", "Other") or "Other"
        country = h.get("country", "US") or "US"

        sector_map[sector] = sector_map.get(sector, 0) + value
        country_map[country] = country_map.get(country, 0) + value

    sectors = [{"name": k, "value": round(v, 2), "pct": round(v/total_value*100, 1) if total_value else 0}
               for k, v in sorted(sector_map.items(), key=lambda x: -x[1])]
    countries = [{"name": k, "value": round(v, 2), "pct": round(v/total_value*100, 1) if total_value else 0}
                 for k, v in sorted(country_map.items(), key=lambda x: -x[1])]

    return {"sectors": sectors, "countries": countries, "total_value": round(total_value, 2)}


@app.get("/api/holdings/performance")
def holdings_performance(period: str = "3mo"):
    """Calculate portfolio value over time based on holdings and historical prices."""
    holdings = get_holdings()
    if not holdings:
        return {"data": [], "period": period}

    # Get historical data for all tickers
    all_histories = {}
    for h in holdings:
        try:
            hist = _get_history_df(h["ticker"], period)
            if not hist.empty:
                all_histories[h["ticker"]] = {
                    "quantity": h["quantity"],
                    "avg_cost": h["avg_cost"],
                    "closes": {idx.strftime("%Y-%m-%d"): safe_val(row["Close"])
                              for idx, row in hist.iterrows()},
                }
        except Exception:
            continue

    if not all_histories:
        return {"data": [], "period": period}

    # Get all unique dates across all tickers
    all_dates = sorted(set(d for h in all_histories.values() for d in h["closes"].keys()))

    # Calculate portfolio value for each date
    data = []
    prev_values = {}  # Track last known price per ticker
    for date in all_dates:
        total_value = 0
        total_cost = 0
        for ticker, info in all_histories.items():
            price = info["closes"].get(date)
            if price is None:
                price = prev_values.get(ticker)
            if price is None:
                continue
            prev_values[ticker] = price
            total_value += price * info["quantity"]
            total_cost += info["avg_cost"] * info["quantity"]

        if total_value > 0:
            pnl = total_value - total_cost
            pnl_pct = (pnl / total_cost * 100) if total_cost > 0 else 0
            data.append({
                "date": date,
                "value": round(total_value, 2),
                "cost": round(total_cost, 2),
                "pnl": round(pnl, 2),
                "pnlPct": round(pnl_pct, 2),
            })

    return {"data": data, "period": period}


@app.get("/api/holdings/benchmark")
def holdings_benchmark(period: str = "3mo", benchmark: str = "SPY"):
    """Compare portfolio performance against a benchmark index."""
    holdings = get_holdings()
    if not holdings:
        return {"portfolio": [], "benchmark": [], "period": period}

    # Get benchmark history
    bench_hist = _get_history_df(benchmark, period)
    if bench_hist.empty:
        return {"portfolio": [], "benchmark": [], "period": period}

    bench_start = bench_hist["Close"].iloc[0]
    bench_data = []
    for idx, row in bench_hist.iterrows():
        bench_data.append({
            "date": idx.strftime("%Y-%m-%d"),
            "value": round((row["Close"] / bench_start - 1) * 100, 2),
        })

    # Get portfolio performance (reuse logic)
    all_histories = {}
    for h in holdings:
        try:
            hist = _get_history_df(h["ticker"], period)
            if not hist.empty:
                all_histories[h["ticker"]] = {
                    "quantity": h["quantity"],
                    "closes": {idx.strftime("%Y-%m-%d"): safe_val(row["Close"])
                              for idx, row in hist.iterrows()},
                }
        except Exception:
            continue

    all_dates = sorted(set(d for h in all_histories.values() for d in h["closes"].keys()))

    if not all_dates:
        return {"portfolio": [], "benchmark": bench_data, "period": period}

    # Calculate portfolio % return from first date
    portfolio_data = []
    prev_values = {}
    first_value = None
    for date in all_dates:
        total_value = 0
        for ticker, info in all_histories.items():
            price = info["closes"].get(date)
            if price is None:
                price = prev_values.get(ticker)
            if price is None:
                continue
            prev_values[ticker] = price
            total_value += price * info["quantity"]

        if total_value > 0:
            if first_value is None:
                first_value = total_value
            pct = (total_value / first_value - 1) * 100 if first_value else 0
            portfolio_data.append({
                "date": date,
                "value": round(pct, 2),
            })

    return {
        "portfolio": portfolio_data,
        "benchmark": bench_data,
        "benchmarkTicker": benchmark,
        "period": period,
    }


@app.get("/api/holdings/movers")
def holdings_movers():
    """Get top gainers and losers from holdings today."""
    holdings = get_holdings()
    if not holdings:
        return {"gainers": [], "losers": []}

    tickers = [h["ticker"] for h in holdings]
    quotes = _get_bulk_quotes(tickers) if tickers else {}

    movers = []
    for h in holdings:
        quote = quotes.get(h["ticker"], {})
        if quote.get("changePct") is not None:
            movers.append({
                "ticker": h["ticker"],
                "name": quote.get("name") or h.get("name", h["ticker"]),
                "price": quote.get("price"),
                "changePct": quote["changePct"],
                "change": quote.get("change"),
                "quantity": h["quantity"],
                "marketValue": round(quote["price"] * h["quantity"], 2) if quote.get("price") else None,
            })

    movers.sort(key=lambda x: x["changePct"] or 0, reverse=True)

    gainers = [m for m in movers if (m["changePct"] or 0) > 0][:5]
    all_losers = [m for m in movers if (m["changePct"] or 0) < 0]
    losers = all_losers[-5:]  # 5 worst (most negative at end since sorted desc)

    return {"gainers": gainers, "losers": losers}


# ---------------------------------------------------------------------------
# Report & Generation endpoints (global)
# ---------------------------------------------------------------------------

REPORTS_DIR = PROJECT_ROOT / "reports" / "output"
ARCHIVE_DIR = REPORTS_DIR / "_archive"
PIPELINE_PYTHON = PROJECT_ROOT / "venv" / "bin" / "python"
PIPELINE_MAIN = PROJECT_ROOT / "main.py"

_jobs: dict[str, dict] = {}

# Ticker pattern: 1-5 uppercase letters, or digits+dot+letter (e.g. 8035.T)
_TICKER_RE = re.compile(r"[A-Z]{1,5}|\d{4}\.[A-Z]")
_TIMESTAMP_RE = re.compile(r"_\d{8}_\d{6}")


def _classify_report(md: Path) -> dict:
    """Classify a report by parsing its filename and content."""
    name = md.stem  # filename without .md
    rel = md.relative_to(REPORTS_DIR)
    size = md.stat().st_size
    is_nested = len(rel.parts) > 1  # inside a subdirectory

    report_type = "analysis"
    tickers = []
    title = name.replace("_", " ").title()

    # Pipeline-generated: quick_TICKER_DATE_TIME
    if name.startswith("quick_"):
        report_type = "quick"
        parts = name.split("_")
        if len(parts) >= 2:
            tickers = [parts[1]]
            title = f"{parts[1]} Quick Analysis"

    # Pipeline-generated: comparison_TICKERS_DATE_TIME or comparison_NAME_DATE_TIME
    elif name.startswith("comparison_"):
        report_type = "comparison"
        stripped = _TIMESTAMP_RE.sub("", name[len("comparison_"):])
        found = _TICKER_RE.findall(stripped)
        if found:
            tickers = found
            title = " vs ".join(found) + " Comparison"
        else:
            title = stripped.replace("_", " ").title() + " Comparison"

    # Pipeline-generated: screening_TICKERS_DATE_TIME
    elif name.startswith("screening_"):
        report_type = "screening"
        stripped = _TIMESTAMP_RE.sub("", name[len("screening_"):])
        found = _TICKER_RE.findall(stripped)
        tickers = found
        title = f"Screening: {', '.join(found[:3])}" + (f" +{len(found)-3}" if len(found) > 3 else "")

    # Nested in a project folder or large file = research
    elif is_nested or size > 10000:
        report_type = "research"
        try:
            with open(md, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
        except Exception:
            pass

    return {
        "filename": md.name,
        "path": str(rel),
        "size": size,
        "modified": datetime.fromtimestamp(md.stat().st_mtime).isoformat(),
        "type": report_type,
        "tickers": tickers,
        "title": title,
    }


@app.get("/api/reports")
def list_reports():
    """List all markdown reports in reports/output/, classified by type."""
    if not REPORTS_DIR.exists():
        return {"reports": []}
    files = []
    for md in sorted(REPORTS_DIR.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        # Skip archived reports
        try:
            md.relative_to(ARCHIVE_DIR)
            continue
        except ValueError:
            pass
        files.append(_classify_report(md))
        if len(files) >= 100:
            break
    return {"reports": files}


@app.get("/api/reports/{report_path:path}")
def read_report(report_path: str):
    """Read a specific report's markdown content."""
    safe = Path(report_path)
    if ".." in safe.parts:
        raise HTTPException(status_code=400, detail="Invalid path")
    full_path = REPORTS_DIR / safe
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    if not str(full_path.resolve()).startswith(str(REPORTS_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    return {"path": report_path, "content": full_path.read_text(encoding="utf-8")}


@app.post("/api/reports/archive")
def archive_report(path: str):
    """Move a report to _archive/ folder."""
    safe = Path(path)
    if ".." in safe.parts:
        raise HTTPException(status_code=400, detail="Invalid path")
    full_path = REPORTS_DIR / safe
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    if not str(full_path.resolve()).startswith(str(REPORTS_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    ARCHIVE_DIR.mkdir(exist_ok=True)
    dest = ARCHIVE_DIR / full_path.name
    full_path.rename(dest)
    return {"archived": path, "destination": str(dest.relative_to(REPORTS_DIR))}


@app.get("/api/profiles")
def get_profiles():
    """Return available analysis profiles."""
    path = PROJECT_ROOT / "configs" / "profiles.yaml"
    if not path.exists():
        return {"profiles": {}}
    profiles = load_yaml(path)
    return {"profiles": profiles}


def _run_pipeline(job_id: str, ticker: str, profile: str):
    """Execute the analysis pipeline in a subprocess."""
    _jobs[job_id]["status"] = "running"
    try:
        result = subprocess.run(
            [str(PIPELINE_PYTHON), str(PIPELINE_MAIN), "analyze", ticker, "--profile", profile],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(PROJECT_ROOT),
        )
        stdout = result.stdout
        stderr = result.stderr
        match = re.search(r"Report saved:\s*(.+\.md)", stdout)
        if result.returncode == 0 and match:
            report_path = match.group(1).strip()
            try:
                rel = str(Path(report_path).relative_to(REPORTS_DIR))
            except ValueError:
                rel = report_path
            _jobs[job_id]["status"] = "completed"
            _jobs[job_id]["report_path"] = rel
        else:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = stderr or stdout or "Pipeline returned no report path"
    except subprocess.TimeoutExpired:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = "Pipeline timed out after 300s"
    except Exception as e:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)


@app.post("/api/reports/generate")
def generate_report(ticker: str, profile: str = "full", background_tasks: BackgroundTasks = None):
    """Trigger analysis pipeline for a ticker. Returns job ID for polling."""
    profiles_path = PROJECT_ROOT / "configs" / "profiles.yaml"
    if profiles_path.exists():
        profiles = load_yaml(profiles_path)
        if profile not in profiles:
            raise HTTPException(status_code=400, detail=f"Unknown profile: {profile}")
    if not PIPELINE_PYTHON.exists():
        raise HTTPException(status_code=500, detail="Pipeline venv not found")

    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {
        "id": job_id,
        "ticker": ticker.upper(),
        "profile": profile,
        "status": "queued",
        "created": datetime.utcnow().isoformat(),
        "report_path": None,
        "error": None,
    }
    background_tasks.add_task(_run_pipeline, job_id, ticker.upper(), profile)
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/reports/job/{job_id}")
def get_job_status(job_id: str):
    """Poll job status."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ---------------------------------------------------------------------------
# Static file serving (production: serve React build from /static)
# ---------------------------------------------------------------------------
STATIC_DIR = Path(__file__).resolve().parent / "static"

if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    # Serve hashed assets (JS, CSS, images) from /assets
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="static-assets")

    # Catch-all: serve index.html for React SPA routing
    # This MUST be after all /api/* routes so they take priority
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = STATIC_DIR / full_path
        if file_path.is_file() and not full_path.startswith("api"):
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8050))
    uvicorn.run(app, host="0.0.0.0", port=port)

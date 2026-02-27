"""Shared yfinance session with rate limiting and request deduplication.

Fixes Yahoo Finance 429 (Too Many Requests) errors that cause
"INSUFFICIENT DATA" recommendations by dramatically reducing request count:

1. Shared YfData instance — crumb/cookie fetched once, reused by all
   Ticker instances (eliminates 20+ redundant auth requests per analysis)
2. In-process caching of ticker.info to eliminate redundant API calls
   (a single stock analysis calls .info 12+ times across engines → 1)
3. Pre-request rate limiting (min 0.5s between Yahoo requests)
4. Connection pooling via shared requests.Session

Net effect: ~50 Yahoo requests per analysis → ~8, spread over ~4s.

NOTE: We intentionally do NOT retry on 429 at the urllib3 level. Retrying
on persistent rate limits interacts badly with yfinance's internal strategy
switching (basic → csrf), causing cascading retry storms (60s+ per request).
Instead, we prevent 429s by reducing total requests + rate limiting.

Usage:
    from src.utils.yf_session import patch_yfinance
    patch_yfinance()  # Call once at startup

After patching, all `yf.Ticker()` calls throughout the codebase
automatically use the rate-limited session with shared auth.
"""

import time
import threading
import functools
import logging

import requests
from requests.adapters import HTTPAdapter

import yfinance as yf

logger = logging.getLogger("yf_session")

_session = None
_session_lock = threading.Lock()

# Shared YfData instance — stores crumb + cookies, reused across Ticker instances
_shared_yf_data = None
_yf_data_lock = threading.Lock()

# Rate limiter state
_rate_lock = threading.Lock()
_last_request_time = 0.0
_MIN_REQUEST_INTERVAL = 0.5  # 500ms between Yahoo requests (2 req/s)

# In-process cache: ticker → (timestamp, info_dict)
_info_cache: dict[str, tuple[float, dict]] = {}
_info_lock = threading.Lock()
_INFO_TTL = 300  # 5 minutes

_patched = False


class _RateLimitedSession(requests.Session):
    """Session that enforces minimum interval between requests to Yahoo."""

    def send(self, request, **kwargs):
        """Override send to add rate limiting for Yahoo Finance requests."""
        global _last_request_time

        url = getattr(request, "url", "") or ""
        is_yahoo = "yahoo.com" in url or "finance.yahoo" in url

        if is_yahoo:
            with _rate_lock:
                now = time.time()
                elapsed = now - _last_request_time
                if elapsed < _MIN_REQUEST_INTERVAL:
                    sleep_time = _MIN_REQUEST_INTERVAL - elapsed
                    time.sleep(sleep_time)
                _last_request_time = time.time()

        return super().send(request, **kwargs)


def get_session() -> requests.Session:
    """Get or create the shared rate-limited Session with connection pooling."""
    global _session
    if _session is not None:
        return _session

    with _session_lock:
        if _session is not None:
            return _session

        session = _RateLimitedSession()

        # Connection pooling only — no urllib3 retries.
        # yfinance handles 429 internally via strategy switching (basic ↔ csrf).
        # Adding urllib3 retries on 429 causes cascading retry storms.
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        _session = session
        logger.info(
            "Created shared yfinance session: rate_limit=%.1f req/s, pooled connections",
            1.0 / _MIN_REQUEST_INTERVAL,
        )
        return _session


def _get_cached_info(original_fget, self):
    """Cached wrapper for yf.Ticker.info property."""
    ticker = getattr(self, "ticker", None)
    if ticker is None:
        return original_fget(self)

    now = time.time()
    with _info_lock:
        if ticker in _info_cache:
            cached_time, cached_data = _info_cache[ticker]
            if now - cached_time < _INFO_TTL:
                return cached_data

    # Fetch fresh (outside lock to avoid blocking)
    result = original_fget(self)

    with _info_lock:
        _info_cache[ticker] = (time.time(), result)

    return result


def patch_yfinance():
    """Monkey-patch yf.Ticker to use shared rate-limited session with caching.

    Key optimizations (biggest impact first):
    1. Shared YfData: crumb/cookie fetched ONCE, reused by all Ticker instances
       (eliminates 20+ redundant /v1/test/getcrumb requests per analysis)
    2. Info cache: ticker.info fetched ONCE per ticker, cached 5min
       (eliminates 12+ redundant quoteSummary requests per analysis)
    3. Rate limiting: 0.5s between Yahoo requests (prevents triggering 429)
    4. Connection pooling: shared TCP connections reduce overhead

    Safe to call multiple times — only patches once.
    """
    global _patched, _shared_yf_data
    if _patched:
        return

    # 1. Patch __init__ to inject shared session AND shared YfData
    original_init = yf.Ticker.__init__

    @functools.wraps(original_init)
    def patched_init(self, ticker, session=None, proxy=None):
        global _shared_yf_data
        if session is None:
            session = get_session()
        original_init(self, ticker, session=session, proxy=proxy)

        # Share YfData across all Ticker instances so crumb/cookie
        # are fetched once and reused (biggest source of 429 errors)
        with _yf_data_lock:
            if _shared_yf_data is None:
                _shared_yf_data = self._data
            else:
                self._data = _shared_yf_data

    yf.Ticker.__init__ = patched_init

    # 2. Patch .info property to use process-level cache
    original_info_fget = yf.Ticker.info.fget

    @property
    def cached_info(self):
        return _get_cached_info(original_info_fget, self)

    yf.Ticker.info = cached_info

    _patched = True
    logger.info("Patched yfinance: shared YfData + rate limiting + info cache")


def clear_info_cache(ticker: str = None):
    """Clear the info cache (all or for a specific ticker)."""
    with _info_lock:
        if ticker:
            _info_cache.pop(ticker, None)
        else:
            _info_cache.clear()

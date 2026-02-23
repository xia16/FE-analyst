"""Data source modules — lazy imports to avoid breaking on missing optional dependencies."""

# Core modules (always available)
from .market_data import MarketDataClient
from .fundamentals import FundamentalsClient
from .macro_data import MacroDataClient

# Optional modules — import individually to avoid cascade failures
try:
    from .sec_filings import SECFilingsClient
except ImportError:
    pass

try:
    from .news_sentiment import NewsSentimentClient
except ImportError:
    pass

try:
    from .alternative_data import AlternativeDataClient
except ImportError:
    pass

try:
    from .screener import StockScreener
except ImportError:
    pass

try:
    from .insider_congress import InsiderCongressClient
except ImportError:
    pass

try:
    from .earnings_estimates import EarningsEstimatesClient
except ImportError:
    pass

try:
    from .short_interest import ShortInterestClient
except ImportError:
    pass

try:
    from .whale_tracking import WhaleTrackingClient
except ImportError:
    pass

try:
    from .catalyst_calendar import CatalystCalendarClient
except ImportError:
    pass

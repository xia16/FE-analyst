# Free Data Sources, APIs & Python Tools for Stock Investment Analysis Platform

> Compiled: 2026-02-09 | Focus: 100% Free Tools (no paid subscriptions)

---

## 1. MARKET DATA APIs (Free Tier)

### 1.1 yfinance (Yahoo Finance)
- **Provides**: Real-time & historical prices, dividends, splits, options chains, fundamentals, ETFs, mutual funds, crypto, forex
- **Python Package**: `yfinance`
- **Install**: `pip install yfinance`
- **Rate Limits**: ~2,000 API calls/day; unofficial/undocumented limits; Yahoo may temporarily block IPs with aggressive usage; 15-min delayed quotes
- **Restrictions**: Scrapes Yahoo Finance (not an official API); may break if Yahoo changes site structure; NOT suitable for live trading
- **Quality**: ★★★★☆ — Excellent breadth of data; most popular free library; occasional breakage
- **Notes**: Best for batch downloads; use `Ticker.history()` for bulk rather than many small requests

### 1.2 Alpha Vantage
- **Provides**: Real-time & historical stock prices (intraday, daily, weekly, monthly), forex, crypto, 50+ technical indicators, fundamental data (income statement, balance sheet, cash flow, earnings)
- **Python Package**: `alpha_vantage`
- **Install**: `pip install alpha-vantage`
- **API Key**: Free (register at alphavantage.co)
- **Rate Limits**: **5 requests/minute, 25 requests/day** (free tier — significantly reduced from previous 500/day)
- **Quality**: ★★★☆☆ — High quality data but very restrictive free tier limits make it impractical for large-scale analysis
- **Notes**: Good for supplementary data; pair with yfinance for volume

### 1.3 Finnhub
- **Provides**: Real-time US stock prices, company fundamentals, financials, SEC filings, earnings, IPO calendar, forex, crypto, economic data, news sentiment, insider transactions, congressional trading
- **Python Package**: `finnhub-python`
- **Install**: `pip install finnhub-python`
- **API Key**: Free (register at finnhub.io)
- **Rate Limits**: **60 calls/minute** (30 calls/second internal cap)
- **Quality**: ★★★★★ — Most generous free tier; broad data coverage; reliable; WebSocket support for real-time data
- **Notes**: Best all-around free API; covers market data + fundamentals + alternative data

### 1.4 Twelve Data
- **Provides**: Real-time & historical stock/forex/crypto prices, 100+ technical indicators, fundamentals, ETFs
- **Python Package**: `twelvedata`
- **Install**: `pip install twelvedata`
- **API Key**: Free (register at twelvedata.com)
- **Rate Limits**: **8 calls/minute, 800 calls/day**; WebSocket: 1 connection, 8 symbols max
- **Quality**: ★★★★☆ — Clean API design; good documentation; reasonable free tier

### 1.5 Alpaca Markets
- **Provides**: Real-time & historical US stock data (1-min to daily bars), trade & quote data, news, account/trading API
- **Python Package**: `alpaca-py`
- **Install**: `pip install alpaca-py`
- **API Key**: Free (register at alpaca.markets; paper trading account)
- **Rate Limits**: 200 requests/minute for data API
- **Quality**: ★★★★☆ — Excellent real-time data; designed for algo trading; IEX real-time feed is free
- **Notes**: Requires brokerage account signup (paper trading OK); primarily US equities

### 1.6 Marketstack
- **Provides**: End-of-day stock data for 170,000+ tickers from 70+ global exchanges
- **Python Package**: None (REST API, use `requests`)
- **API Key**: Free (register at marketstack.com)
- **Rate Limits**: 100 requests/month (free tier)
- **Quality**: ★★☆☆☆ — Good global coverage but extremely limited free tier

---

## 2. FUNDAMENTAL DATA

### 2.1 Financial Modeling Prep (FMP)
- **Provides**: Financial statements (income, balance sheet, cash flow), ratios, key metrics, DCF valuations, stock screener, ETF data, earnings transcripts
- **Python Package**: `fmpsdk` or use `requests`
- **Install**: `pip install fmpsdk`
- **API Key**: Free (register at financialmodelingprep.com)
- **Rate Limits**: 250 requests/day; 30-day trailing bandwidth limit of 500MB
- **Quality**: ★★★★☆ — Very comprehensive fundamental data; clean JSON format; well-documented

### 2.2 SimFin
- **Provides**: Quarterly & annual financial statements (balance sheet, P&L, cash flow) for ~5,000 US stocks; share prices; industry data
- **Python Package**: `simfin`
- **Install**: `pip install simfin`
- **API Key**: Free (register at simfin.com)
- **Rate Limits**: 2 calls/second; data older than 5 years requires paid plan
- **Quality**: ★★★★☆ — High-quality fundamental data; downloads to local disk for offline use; Pandas-native
- **Notes**: Bulk download approach — very efficient; great for fundamental screening

### 2.3 yfinance (Fundamentals)
- **Provides**: Income statement, balance sheet, cash flow (quarterly & annual), key statistics, analyst recommendations, institutional holders
- **Python Package**: `yfinance` (same as Section 1.1)
- **Quality**: ★★★☆☆ — Convenient but data can be incomplete or inconsistent for some tickers

### 2.4 Finnhub (Fundamentals)
- **Provides**: Basic financials, reported financials (as-reported from SEC), financial ratios, revenue breakdown by segment/geography
- **Python Package**: `finnhub-python` (same as Section 1.3)
- **Quality**: ★★★★☆ — Sourced from SEC filings; reliable for US companies

### 2.5 OpenBB Platform
- **Provides**: Aggregated access to ~100 data sources; equities, options, crypto, forex, macro, fixed income, alternative data; acts as a unified interface
- **Python Package**: `openbb`
- **Install**: `pip install openbb`
- **Rate Limits**: Depends on underlying data providers (you supply your own API keys)
- **Quality**: ★★★★★ — Open-source Bloomberg alternative; modular architecture; AGPLv3 license; latest version 4.6.0 (Jan 2026)
- **Notes**: Best as an orchestration layer; configure it with free API keys from the providers listed here

---

## 3. SEC FILINGS

### 3.1 SEC EDGAR Official APIs (data.sec.gov)
- **Provides**: Submissions history, XBRL financial data from 10-Q/10-K/8-K/20-F/40-F/6-K, company facts, CIK lookup
- **Python Package**: Use `requests` directly or wrapper libraries below
- **API Key**: **None required** (completely free, no registration)
- **Rate Limits**: 10 requests/second; must include User-Agent header with name and email
- **Endpoints**:
  - `data.sec.gov/submissions/CIK{cik}.json` — Filing history
  - `data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json` — All XBRL facts
  - `data.sec.gov/api/xbrl/companyconcept/` — Specific financial concepts
- **Quality**: ★★★★★ — Authoritative source; sub-minute update latency; free forever

### 3.2 edgartools
- **Provides**: Python library to download/analyze SEC filings; parse 10-K, 10-Q, 8-K; extract XBRL financial statements; insider trading (Form 4); full-text search
- **Python Package**: `edgartools`
- **Install**: `pip install edgartools`
- **Rate Limits**: Subject to SEC EDGAR rate limits (10 req/sec)
- **Quality**: ★★★★★ — Best open-source SEC library; actively maintained; rich parsing capabilities

### 3.3 sec-edgar-downloader
- **Provides**: Download any SEC filing type by ticker or CIK; supports 10-K, 10-Q, 8-K, 13-F, S-1, and all other form types
- **Python Package**: `sec-edgar-downloader`
- **Install**: `pip install sec-edgar-downloader`
- **Rate Limits**: Subject to SEC EDGAR rate limits
- **Quality**: ★★★★☆ — Simple, focused tool for bulk downloading filings to disk

### 3.4 sec-edgar-api
- **Provides**: Lightweight wrapper around the official SEC EDGAR REST API
- **Python Package**: `sec-edgar-api`
- **Install**: `pip install sec-edgar-api`
- **Quality**: ★★★☆☆ — Thin wrapper; good for quick access to submissions and XBRL data

### 3.5 SEC EDGAR Full-Text Search (EFTS)
- **Provides**: Full-text search across all SEC filings since 2004
- **Endpoint**: `efts.sec.gov/LATEST/search-index?q=...`
- **API Key**: None required
- **Quality**: ★★★★☆ — Official SEC search; useful for finding specific disclosures across companies

---

## 4. NEWS & SENTIMENT

### 4.1 Finnhub News & Sentiment
- **Provides**: Company news, market news, press releases, news sentiment scores (bullish/bearish/neutral with relevance scoring)
- **Python Package**: `finnhub-python`
- **Rate Limits**: Included in 60 calls/min free tier
- **Quality**: ★★★★☆ — Built-in sentiment scoring; good coverage

### 4.2 Marketaux
- **Provides**: Global financial news with entity recognition, sentiment analysis, ticker tagging
- **Python Package**: None (REST API, use `requests`)
- **API Key**: Free (register at marketaux.com)
- **Rate Limits**: **100 requests/day** (free tier); 3 articles per request
- **Quality**: ★★★☆☆ — Good sentiment metadata; limited free volume

### 4.3 Alpaca News API
- **Provides**: Real-time and historical news for stocks; includes sentiment data
- **Python Package**: `alpaca-py`
- **Rate Limits**: Included in Alpaca free tier
- **Quality**: ★★★★☆ — High quality; real-time; requires Alpaca account

### 4.4 FinBERT (Sentiment Model)
- **Provides**: Pre-trained BERT model fine-tuned on financial text for sentiment classification (positive/negative/neutral)
- **Python Package**: `transformers` (Hugging Face)
- **Install**: `pip install transformers torch`
- **Model**: `ProsusAI/finbert` on Hugging Face
- **Rate Limits**: Runs locally — no API limits
- **Quality**: ★★★★★ — State-of-the-art financial sentiment; significantly more accurate than lexicon-based approaches
- **Notes**: Requires GPU for fast inference; can run on CPU for smaller batches

### 4.5 FinVADER
- **Provides**: VADER sentiment classifier enhanced with financial-domain lexicons
- **Python Package**: `finvader`
- **Install**: `pip install finvader`
- **Rate Limits**: Runs locally — no API limits
- **Quality**: ★★★☆☆ — Fast and lightweight; less accurate than FinBERT but much faster; good for high-volume processing

### 4.6 NLTK VADER
- **Provides**: General-purpose lexicon-based sentiment analysis; works on social media text
- **Python Package**: `nltk`
- **Install**: `pip install nltk` then `nltk.download('vader_lexicon')`
- **Rate Limits**: Runs locally
- **Quality**: ★★☆☆☆ — General purpose; not optimized for financial text; use FinVADER or FinBERT instead

### 4.7 GNews / Google News (via gnews)
- **Provides**: Google News articles by topic, keyword, or location
- **Python Package**: `gnews`
- **Install**: `pip install gnews`
- **Rate Limits**: Unofficial scraping; be cautious with volume
- **Quality**: ★★★☆☆ — Broad coverage; no sentiment built-in; pair with FinBERT

---

## 5. TECHNICAL ANALYSIS LIBRARIES

### 5.1 pandas-ta
- **Provides**: 150+ technical indicators and 60+ candlestick patterns; Pandas extension
- **Python Package**: `pandas_ta`
- **Install**: `pip install pandas-ta`
- **Indicators Include**: SMA, EMA, MACD, RSI, Bollinger Bands, Stochastic, ATR, OBV, Ichimoku, VWAP, ADX, Aroon, Squeeze, and 130+ more
- **Quality**: ★★★★★ — Most comprehensive pure-Python TA library; Pandas-native; actively maintained
- **Notes**: Can optionally use TA-Lib C backend for speed

### 5.2 TA-Lib
- **Provides**: 200+ technical indicators; C/C++ core with Python bindings
- **Python Package**: `TA-Lib`
- **Install**: Requires C library first: `brew install ta-lib` (macOS) then `pip install TA-Lib`
- **Quality**: ★★★★★ — Industry standard; fastest execution; BSD license
- **Notes**: Installation can be tricky due to C dependency; once installed, extremely fast

### 5.3 ta (Technical Analysis Library)
- **Provides**: Technical indicators built on Pandas and NumPy; volume, volatility, trend, momentum, and other indicators
- **Python Package**: `ta`
- **Install**: `pip install ta`
- **Quality**: ★★★★☆ — Clean API; easy to use; good for feature engineering in ML pipelines
- **Notes**: Lighter alternative to pandas-ta; fewer indicators but simpler interface

### 5.4 mplfinance
- **Provides**: Matplotlib-based financial charting; candlestick charts, OHLC charts, volume overlays
- **Python Package**: `mplfinance`
- **Install**: `pip install mplfinance`
- **Quality**: ★★★★☆ — Best free library for financial chart visualization in Python

### 5.5 Backtrader
- **Provides**: Backtesting framework with built-in technical indicators; supports live trading
- **Python Package**: `backtrader`
- **Install**: `pip install backtrader`
- **Quality**: ★★★★☆ — Full backtesting engine; includes its own TA indicators; event-driven

---

## 6. SCREENING & FILTERING

### 6.1 finvizfinance
- **Provides**: Stock screener with 90+ filters (P/E, market cap, sector, technical signals, etc.); charts, news, insider data, analyst targets
- **Python Package**: `finvizfinance`
- **Install**: `pip install finvizfinance`
- **Rate Limits**: Scrapes FinViz; be respectful with request frequency; 15-20 min delayed data
- **Quality**: ★★★★★ — Most powerful free screener; returns Pandas DataFrames; very comprehensive filters

### 6.2 finviz (Unofficial API)
- **Provides**: Similar to finvizfinance; stock screening, news, insider trading, analyst targets
- **Python Package**: `finviz`
- **Install**: `pip install finviz`
- **Rate Limits**: Same as above (scraping-based)
- **Quality**: ★★★★☆ — Export to CSV/SQLite/DataFrames; good alternative to finvizfinance

### 6.3 Yahoo Finance Screener (via yfinance)
- **Provides**: Basic screening via `yfinance.Screener` or manual filtering of downloaded data
- **Python Package**: `yfinance`
- **Quality**: ★★★☆☆ — Limited built-in screening; better to download data and filter with Pandas

### 6.4 FMP Stock Screener
- **Provides**: Screen by market cap, price, volume, beta, sector, exchange, and financial ratios
- **Python Package**: `fmpsdk` or `requests`
- **Rate Limits**: Included in 250 requests/day free tier
- **Quality**: ★★★★☆ — Good API-based screener; clean JSON output

### 6.5 Custom Screening Pipeline (Recommended Approach)
```python
# Best practice: combine multiple sources
# 1. Use finvizfinance for initial universe filtering
# 2. Pull detailed fundamentals from FMP or SimFin
# 3. Get price data from yfinance
# 4. Apply custom technical filters with pandas-ta
# 5. Score with your own model
```

---

## 7. ECONOMIC / MACRO DATA

### 7.1 FRED (Federal Reserve Economic Data)
- **Provides**: 816,000+ economic time series: GDP, CPI, unemployment, interest rates, money supply, housing, manufacturing, trade, and much more
- **Python Package**: `fredapi`
- **Install**: `pip install fredapi`
- **API Key**: Free (register at fred.stlouisfed.org)
- **Rate Limits**: 120 requests/minute
- **Quality**: ★★★★★ — Gold standard for US economic data; updated frequently; unmatched breadth
- **Alternative Package**: `fedfred` (pip install fedfred) — newer, with built-in caching and rate limiter

### 7.2 Bureau of Labor Statistics (BLS)
- **Provides**: Employment, unemployment, CPI, PPI, wages, productivity, import/export prices
- **Python Package**: `bls` or use `requests`
- **Install**: `pip install bls`
- **API Key**: Optional for v1.0 (25 queries/day); free registration for v2.0 (500 queries/day)
- **Rate Limits**: v1: 25/day, v2: 500/day
- **Quality**: ★★★★★ — Authoritative US labor data; JSON and XLSX output

### 7.3 World Bank API
- **Provides**: Global economic indicators: GDP, population, trade, education, health for 200+ countries
- **Python Package**: `wbdata`
- **Install**: `pip install wbdata`
- **API Key**: None required
- **Rate Limits**: Generous; no strict published limits
- **Quality**: ★★★★☆ — Best for international/comparative macro analysis

### 7.4 pandas-datareader
- **Provides**: Unified interface to pull data from FRED, World Bank, OECD, Eurostat, Stooq, and more
- **Python Package**: `pandas_datareader`
- **Install**: `pip install pandas-datareader`
- **Quality**: ★★★☆☆ — Convenient but some data sources are deprecated (e.g., Quandl WIKI); FRED reader still works well

### 7.5 Nasdaq Data Link (formerly Quandl)
- **Provides**: Economic and financial datasets from hundreds of publishers
- **Python Package**: `nasdaq-data-link`
- **Install**: `pip install nasdaq-data-link`
- **API Key**: Free (register at data.nasdaq.com)
- **Rate Limits**: Varies by dataset; many free datasets available
- **Quality**: ★★★☆☆ — Some excellent free datasets; many premium ones require payment; WIKI stock database discontinued (2018)

### 7.6 Treasury Direct / US Treasury API
- **Provides**: Treasury yields, bill/bond auction results, debt data
- **Endpoint**: `api.fiscaldata.treasury.gov`
- **API Key**: None required
- **Quality**: ★★★★☆ — Official US Treasury data; useful for yield curve analysis

---

## 8. ALTERNATIVE DATA

### 8.1 Reddit Sentiment (via PRAW)
- **Provides**: Access Reddit posts/comments from r/wallstreetbets, r/stocks, r/investing, r/options, etc.
- **Python Package**: `praw`
- **Install**: `pip install praw`
- **API Key**: Free (create Reddit app at reddit.com/prefs/apps)
- **Rate Limits**: 60 requests/minute (OAuth); 10 requests/minute (no OAuth)
- **Quality**: ★★★★☆ — Direct access to retail sentiment; pair with FinBERT for analysis
- **Notes**: Must create Reddit "script" app; combine with NLP for signal extraction

### 8.2 Finnhub Alternative Data
- **Provides**: Insider transactions, congressional trading, social sentiment, supply chain data, lobbying data, USPTO patents
- **Python Package**: `finnhub-python`
- **Rate Limits**: Included in 60 calls/min free tier
- **Quality**: ★★★★☆ — Excellent free alternative data; insider trading data is particularly valuable

### 8.3 SEC Insider Trading (Form 4)
- **Provides**: Insider buy/sell transactions from SEC Form 4 filings
- **Python Package**: `edgartools` or direct SEC EDGAR API
- **Rate Limits**: SEC standard (10 req/sec)
- **Quality**: ★★★★★ — Authoritative source; no delay; free

### 8.4 OpenInsider (via scraping)
- **Provides**: Aggregated insider trading data with filtering
- **Website**: openinsider.com
- **Python Package**: Use `requests` + `beautifulsoup4` to scrape
- **Quality**: ★★★☆☆ — Convenient aggregation; scraping may be fragile

### 8.5 ApeWisdom API
- **Provides**: Aggregated stock mention counts and trends from Reddit (WSB, stocks, etc.)
- **Endpoint**: `apewisdom.io/api/v1.0/filter/all-stocks`
- **API Key**: None required
- **Rate Limits**: Not strictly documented; be respectful
- **Quality**: ★★★☆☆ — Quick Reddit sentiment proxy; limited depth

### 8.6 Quiver Quantitative (Free Tier)
- **Provides**: Congressional trading, government contracts, lobbying, Wikipedia page views, patent data, insider trading
- **Website**: quiverquant.com
- **Python Package**: Use `requests` with their API
- **API Key**: Free tier available
- **Quality**: ★★★★☆ — Unique alternative datasets; some endpoints free

### 8.7 Wikipedia Page Views
- **Provides**: Daily page view counts for any Wikipedia article (proxy for public interest)
- **Endpoint**: `wikimedia.org/api/rest_v1/metrics/pageviews`
- **API Key**: None required
- **Quality**: ★★★☆☆ — Interesting alternative signal; correlates with retail attention

---

## RECOMMENDED CONFIGURATION FOR YOUR PLATFORM

### Core Stack (Install All)
```bash
pip install yfinance finnhub-python pandas-ta edgartools finvizfinance fredapi simfin transformers torch
```

### Tier 1 — Essential (Use These First)
| Category | Primary Source | Backup Source |
|---|---|---|
| Price Data | `yfinance` | `finnhub-python` |
| Fundamentals | `finnhub` + `simfin` | FMP API |
| SEC Filings | `edgartools` | SEC EDGAR direct |
| News | Finnhub News API | Alpaca News |
| Sentiment | FinBERT (local) | FinVADER (fast) |
| Technical | `pandas-ta` | `ta` |
| Screening | `finvizfinance` | Custom Pandas |
| Macro Data | `fredapi` | `wbdata` |
| Alt Data | Finnhub (insider/congress) | PRAW (Reddit) |

### Tier 2 — Supplementary
| Category | Source | Use Case |
|---|---|---|
| Price Data | Twelve Data, Alpha Vantage | Fill gaps in yfinance |
| Fundamentals | FMP, OpenBB | Cross-validation |
| SEC | sec-edgar-downloader | Bulk filing downloads |
| News | Marketaux, GNews | Broader news coverage |
| Macro | BLS, Nasdaq Data Link | Labor/specialized data |
| Alt Data | ApeWisdom, Wikipedia views | Retail attention signals |

### API Keys to Register (All Free)
1. **Finnhub** — finnhub.io (most important; best free tier)
2. **FRED** — fred.stlouisfed.org
3. **Alpha Vantage** — alphavantage.co
4. **FMP** — financialmodelingprep.com
5. **Twelve Data** — twelvedata.com
6. **SimFin** — simfin.com
7. **Alpaca** — alpaca.markets
8. **Reddit** — reddit.com/prefs/apps (for PRAW)
9. **Marketaux** — marketaux.com
10. **BLS** — registrationrequired for v2 API

### Rate Limit Summary
| Source | Free Limit | Effective Capacity |
|---|---|---|
| yfinance | ~2,000/day | High (batch friendly) |
| Finnhub | 60/min | **Best** — 86,400/day |
| Alpha Vantage | 25/day | Very Low |
| Twelve Data | 800/day | Moderate |
| FMP | 250/day | Moderate |
| SEC EDGAR | 10/sec | **Very High** |
| FRED | 120/min | **Very High** |
| Marketaux | 100/day | Low |
| BLS v2 | 500/day | Moderate |

### Data Quality Tiers
- **Authoritative** (use as ground truth): SEC EDGAR, FRED, BLS, US Treasury
- **High Quality** (reliable for analysis): Finnhub, SimFin, FMP, yfinance
- **Good** (supplementary): Alpha Vantage, Twelve Data, Alpaca, World Bank
- **Variable** (verify before relying on): FinViz scrapers, Reddit data, ApeWisdom

---

## SAMPLE INTEGRATION CODE

```python
"""
Minimal example: Multi-source stock analysis pipeline
"""
import yfinance as yf
import finnhub
import pandas_ta as ta
from fredapi import Fred
from edgartools import Company

# --- 1. Price Data ---
ticker = yf.Ticker("AAPL")
hist = ticker.history(period="2y")

# --- 2. Technical Indicators ---
hist.ta.macd(append=True)
hist.ta.rsi(append=True)
hist.ta.bbands(append=True)

# --- 3. Fundamentals (Finnhub) ---
fc = finnhub.Client(api_key="YOUR_FINNHUB_KEY")
basics = fc.company_basic_financials("AAPL", "all")
metrics = basics.get("metric", {})

# --- 4. SEC Filings ---
company = Company("AAPL")
filings_10k = company.get_filings(form="10-K")
latest_10k = filings_10k[0]

# --- 5. Macro Data ---
fred = Fred(api_key="YOUR_FRED_KEY")
fed_rate = fred.get_series("FEDFUNDS")
cpi = fred.get_series("CPIAUCSL")

# --- 6. News Sentiment (Finnhub) ---
news = fc.company_news("AAPL", _from="2026-01-01", to="2026-02-09")

# --- 7. Insider Trading (Finnhub) ---
insiders = fc.stock_insider_transactions("AAPL")

# --- 8. Screening (FinViz) ---
from finvizfinance.screener.overview import Overview
screener = Overview()
filters_dict = {
    "Market Cap.": "Mid ($2bln to $10bln)",
    "P/E": "Under 15",
    "ROE": "Over 15%"
}
screener.set_filter(filters_dict=filters_dict)
results_df = screener.screener_view()
```

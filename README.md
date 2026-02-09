# FE-Analyst

Stock & company analysis platform for investment decision-making. Built entirely on **free** data sources and open-source tools.

## What It Does

- **Full stock analysis** with composite scoring (0-100) and buy/sell/hold recommendations
- **Fundamental analysis** - financial health, growth profile, key ratios from SEC filings
- **Technical analysis** - 15+ indicators (RSI, MACD, Bollinger Bands, moving averages, etc.)
- **Valuation models** - DCF, comparable company analysis
- **Sentiment analysis** - financial news (FinBERT), Reddit/social, analyst consensus
- **Risk metrics** - volatility, beta, Sharpe ratio, VaR, max drawdown
- **Stock screening** - pre-built screens (value, growth, momentum, dividend) + custom filters
- **Macro dashboard** - FRED economic data, Treasury yields, key indicators
- **Report generation** - markdown and JSON reports with full breakdown

## Quick Start

```bash
# 1. Clone and setup
git clone <your-repo-url>
cd FE-analyst
chmod +x setup.sh && ./setup.sh

# 2. Activate environment
source venv/bin/activate

# 3. Add your API keys
# Edit .env (copied from .env.example during setup)

# 4. Run
python main.py analyze AAPL
python main.py compare AAPL MSFT GOOGL
python main.py screen value
python main.py quote TSLA
python main.py fundamentals NVDA
python main.py risk AMZN
python main.py macro
```

## CLI Commands

| Command | Description | Example |
|---------|-------------|---------|
| `analyze` | Full report with composite score | `python main.py analyze AAPL` |
| `compare` | Side-by-side comparison | `python main.py compare AAPL MSFT GOOGL` |
| `screen` | Stock screener (value/growth/momentum/dividend) | `python main.py screen value` |
| `quote` | Real-time price quote | `python main.py quote TSLA` |
| `fundamentals` | Key financial ratios | `python main.py fundamentals NVDA` |
| `risk` | Risk analysis | `python main.py risk AMZN` |
| `macro` | Economic indicators snapshot | `python main.py macro` |

## Project Structure

```
FE-analyst/
├── main.py                     # CLI entry point
├── setup.sh                    # One-command environment setup
├── requirements.txt            # Python dependencies
├── .env.example                # API key template
├── configs/
│   └── settings.yaml           # App configuration
├── src/
│   ├── config.py               # Central config loader
│   ├── data_sources/           # Data fetching clients
│   │   ├── market_data.py      # Price/OHLCV (yfinance, finnhub)
│   │   ├── fundamentals.py     # Financials, ratios (yfinance, simfin)
│   │   ├── sec_filings.py      # SEC EDGAR (edgartools)
│   │   ├── news_sentiment.py   # News + FinBERT sentiment
│   │   ├── macro_data.py       # FRED, Treasury, World Bank
│   │   ├── alternative_data.py # Reddit, insider trades, analysts
│   │   └── screener.py         # Finviz stock screener
│   ├── analysis/               # Analysis engines
│   │   ├── technical.py        # Technical indicators & signals
│   │   ├── fundamental.py      # Financial health scoring
│   │   ├── valuation.py        # DCF, comparables
│   │   ├── sentiment.py        # Multi-source sentiment aggregation
│   │   ├── risk.py             # Volatility, VaR, beta, drawdown
│   │   └── scoring.py          # Composite scorer (0-100)
│   ├── reports/
│   │   └── generator.py        # Markdown/JSON report output
│   └── utils/
│       ├── cache.py            # File-based response caching
│       ├── rate_limiter.py     # API rate limit management
│       └── logger.py           # Logging setup
├── data/
│   ├── raw/                    # Raw downloaded data
│   ├── cache/                  # Cached API responses
│   └── processed/              # Processed datasets
├── notebooks/
│   └── 01_quick_start.ipynb    # Interactive exploration
├── reports/output/             # Generated reports
├── models/                     # ML model artifacts (FinBERT cache)
├── tests/                      # Test suite
└── configs/
    └── settings.yaml           # Configuration
```

## Data Sources (All Free)

| Source | Data | Python Package |
|--------|------|---------------|
| yfinance | Prices, financials, holders | `yfinance` |
| Finnhub | Quotes, news, peers, insider trades | `finnhub-python` |
| SEC EDGAR | 10-K, 10-Q, 8-K filings, XBRL | `edgartools` |
| FRED | 800K+ economic series | `fredapi` |
| SimFin | Bulk fundamental data | `simfin` |
| Finviz | Stock screening (90+ filters) | `finvizfinance` |
| FinBERT | Financial sentiment NLP | `transformers` |
| Reddit (PRAW) | Social sentiment | `praw` |
| World Bank | Global macro indicators | `wbdata` |
| pandas-ta | 150+ technical indicators | `pandas_ta` |

## API Keys (Free Registration)

Edit `.env` after running setup. All keys are free tier:

1. **Finnhub** (most important) - https://finnhub.io/
2. **FRED** - https://fred.stlouisfed.org/docs/api/api_key.html
3. **SimFin** - https://simfin.com/
4. **FMP** - https://financialmodelingprep.com/
5. **Reddit** - https://www.reddit.com/prefs/apps
6. **SEC EDGAR** - No key needed, just set your email as user-agent

The platform works with partial keys - it gracefully degrades if a source is unavailable.

## Scoring System

The composite score (0-100) weights five dimensions:

| Dimension | Weight | What It Measures |
|-----------|--------|-----------------|
| Fundamental | 30% | Financial health, ROE, debt, margins |
| Valuation | 25% | DCF intrinsic value vs. current price |
| Technical | 20% | RSI, MACD, moving average signals |
| Risk | 15% | Volatility, beta, drawdown |
| Sentiment | 10% | News, social media, analyst consensus |

**Recommendation thresholds:** 75+ Strong Buy, 60+ Buy, 45+ Hold, 30+ Sell, <30 Strong Sell

## Disclaimer

This tool is for **informational and educational purposes only**. It is not financial advice. Always conduct your own research and consult with qualified financial advisors before making investment decisions.

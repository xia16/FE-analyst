# Production Workflow — FE-Analyst Dashboard

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React)                   │
│              localhost:3000 (Vite dev)                │
│                                                       │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌────────┐ │
│  │Portfolio  │ │Supply Chain│ │  Moat    │ │ Buy    │ │
│  │Dashboard  │ │  Map View  │ │ Heatmap  │ │ Alerts │ │
│  └──────────┘ └───────────┘ └──────────┘ └────────┘ │
│  ┌──────────────────────────────────────────────────┐ │
│  │              Stock Detail View                    │ │
│  │  (Price chart, Technicals, RSI, MACD, Signals)   │ │
│  └──────────────────────────────────────────────────┘ │
└─────────────┬───────────────────────────────────────┘
              │ /api/* proxy
              ▼
┌─────────────────────────────────────────────────────┐
│                  API Server (FastAPI)                  │
│                  localhost:8000                        │
│                                                       │
│  ┌────────────┐ ┌──────────────┐ ┌────────────────┐ │
│  │ Live Quotes │ │  Technicals  │ │  Alert Engine  │ │
│  │  (yfinance) │ │  RSI/MACD/BB │ │  Daily Scanner │ │
│  └────────────┘ └──────────────┘ └────────────────┘ │
│  ┌────────────┐ ┌──────────────┐ ┌────────────────┐ │
│  │ Price Hist  │ │ Moat Heatmap │ │  Sector Perf   │ │
│  └────────────┘ └──────────────┘ └────────────────┘ │
└─────────────┬───────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────┐
│              Config Layer (YAML)                      │
│                                                       │
│  ai_moat_universe.yaml   ← 40 companies, moat scores │
│  watchlists.yaml         ← Named watchlists           │
│  settings.yaml           ← Analyzer configs           │
└─────────────────────────────────────────────────────┘
```

## Quick Start

```bash
cd dashboard
bash start.sh
# Frontend: http://localhost:3000
# API:      http://localhost:8000
# Swagger:  http://localhost:8000/docs
```

Or start individually:
```bash
# API
cd dashboard/api
source venv/bin/activate
uvicorn server:app --reload --port 8000

# Frontend
cd dashboard/frontend
npm run dev
```

## Dashboard Views

### 1. Portfolio Dashboard
- Live quotes for all 11 portfolio positions
- Target allocation pie chart (by recommendation rating)
- Daily performance bar chart
- Holdings table with price, change, market cap, P/E, rating

### 2. Supply Chain Map
- Visual grid of 8 supply chain categories
- Click to expand any category and see all companies
- Each company shows moat score, AI exposure, tier badge
- Mini bar charts showing 5-dimension moat breakdown
- Click any company to jump to Stock Detail

### 3. Moat Heatmap
- Radar chart comparing top 8 companies across 5 moat dimensions
- Full 40-company heatmap table with color-coded scores
- Sortable by composite moat score
- Click any row to view detailed stock analysis

### 4. Buy Alerts
- Automated daily scan at 09:00 UTC
- Manual "Run Scan Now" button for on-demand analysis
- Criteria: RSI oversold (<35), >25% from 52-week high, 2+ bullish signals, near lower Bollinger Band
- Each alert shows reasons, technical data, recommendation

### 5. Stock Detail
- Search any ticker
- Live quote with market cap, P/E, 52-week range
- Interactive price chart (1mo to 2y periods)
- Technical indicator gauges (RSI, MACD, Bollinger)
- Active signal cards (bullish/bearish)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/universe` | GET | Full moat universe with 40 companies |
| `/api/watchlists` | GET | All configured watchlists |
| `/api/portfolio` | GET | Portfolio positions with live quotes |
| `/api/quote/{ticker}` | GET | Single live quote |
| `/api/quotes?tickers=A,B,C` | GET | Bulk quotes |
| `/api/technicals/{ticker}` | GET | RSI, MACD, BB, signals |
| `/api/history/{ticker}?period=1y` | GET | OHLCV price history |
| `/api/alerts` | GET | Recent buy-opportunity alerts |
| `/api/alerts/scan` | POST | Trigger manual scan |
| `/api/moat-heatmap` | GET | Full moat scores for heatmap |
| `/api/sector-performance` | GET | Monthly returns by sector |

## Alert System

The buy-opportunity scanner runs automatically at 09:00 UTC daily via APScheduler.

**Buy signal criteria (any triggers alert):**
1. RSI (14-day) < 35 — oversold territory
2. Price > 25% below 52-week high — significant drawdown
3. 2+ concurrent bullish technical signals
4. Price near lower Bollinger Band (< 10th percentile)

Alerts are stored in-memory and accessible via `/api/alerts`.

## Production Roadmap (Team Brainstorm)

See `BRAINSTORM.md` for full discussion on making this production-grade.

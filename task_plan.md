# Hedge Fund Grade Analysis Upgrade — Task Plan

## Goal
Upgrade FE-analyst from ~30% to ~85% of institutional-grade analysis across 3 phases.

## Phase 1: Quick Wins — Pure Computation on Existing Data
Status: `complete`

### 1A. Valuation Engine Overhaul (`src/analysis/valuation.py`) — 952 lines
- [x] Proper WACC with debt weighting (Ke*E/(E+D) + Kd*(1-t)*D/(E+D))
- [x] Two-stage DCF (high growth 5yr → linear fade to terminal over yr 6-10)
- [x] Exit multiple terminal value (compare vs Gordon Growth)
- [x] Reverse DCF (solve for implied growth rate at current price)
- [x] Probability-weighted fair value (25% bear / 50% base / 25% bull)
- [x] Risk/reward ratio (upside to bull / downside to bear)
- [x] Analyst consensus price targets (yfinance analyst_price_targets)

### 1B. Fundamental Engine Overhaul (`src/analysis/fundamental.py`) — 873 lines
- [x] ROIC calculation (NOPAT / Invested Capital)
- [x] Piotroski F-Score (9-point binary scoring)
- [x] DuPont decomposition (3-way and 5-way)
- [x] Quality of earnings (accruals ratio, FCF/NI divergence)
- [x] Cash conversion cycle (DSO + DIO - DPO)
- [x] Capital allocation scoring (R&D intensity, capex/depr, buyback yield)
- [x] Multi-quarter trend analysis (8-12 quarters revenue/margin trajectory)
- [x] SG&A efficiency trends

### 1C. Sentiment/Moat Additions (`src/analysis/sentiment.py`) — 397 lines
- [x] Insider ownership % (from yfinance major_holders)
- [x] Earnings calendar (next earnings date from yfinance)
- [x] Analyst price targets
- [x] Short interest integration

### 1D. Scoring Engine Updates (`src/analysis/scoring.py`) — 269 lines
- [x] Wire new metrics into composite scoring (ROIC, Piotroski, earnings quality, capital allocation)
- [x] Add conviction scoring meta-metric (agreement, extremity, boosters)

### 1E. run_analysis.py Output Updates — 139 lines
- [x] Surface all new metrics in JSON output (5 new modules wired in)
- [x] Update analysis_watcher.py prompt with new data

## Phase 2: New Data Sources + Portfolio Risk
Status: `complete`

### 2A. New Data Source Modules
- [x] `src/data_sources/short_interest.py` — Short interest data (137 lines)
- [x] `src/data_sources/whale_tracking.py` — 13F position changes (346 lines)
- [x] `src/data_sources/earnings_estimates.py` — EPS revision tracking (298 lines)
- [x] `src/data_sources/catalyst_calendar.py` — Catalyst calendar (282 lines)

### 2B. SEC Integration (`src/data_sources/sec_filings.py`) — 370 lines
- [x] 8-K material event monitoring (with impact classification)
- [x] Risk factor extraction from 10-K (Item 1A parsing)
- [x] 10-K risk factor change detection (year-over-year diff)

### 2C. Portfolio Risk Module (`src/analysis/portfolio_risk.py`) — 429 lines
- [x] Correlation matrix across holdings
- [x] Portfolio-level VaR (historical + parametric)
- [x] Sector/country/currency concentration
- [x] Position sizing framework (fractional Kelly)
- [x] Stress testing (COVID crash, 2022 rate hike, China tech crackdown)
- [x] Factor exposure decomposition (5-factor using ETF proxies)

### 2D. Catalyst Calendar
- [x] Earnings dates + countdown
- [x] FOMC dates + sector catalysts
- [x] Hard vs soft catalyst classification

### 2E. International Analysis (`src/analysis/international.py`) — 229 lines
- [x] ADR premium/discount tracking
- [x] FX sensitivity analysis (correlation, beta, volatility)

### 2F. Dashboard Integration
- [x] New API endpoints: /api/portfolio/risk, /api/catalysts/{ticker}, /api/earnings/{ticker}
- [x] Frontend tab components updated for all new data

## Phase 3: Advanced Analytics
Status: `complete`

### 3A. Advanced Modules
- [x] Stress testing (COVID crash, 2022 rate hike, China tech crackdown) — in portfolio_risk.py
- [x] Factor exposure decomposition (5-factor using ETF proxies) — in portfolio_risk.py
- [x] FX impact analysis for Japan ADR portfolio — in international.py
- [x] 10-K risk factor change detection (year-over-year diff) — in sec_filings.py

### 3B. Enhanced Claude Code Thesis (`analysis_watcher.py`) — 309 lines
- [x] Upgrade prompt to include all new metrics (international, earnings, short interest, whale, catalysts, conviction)
- [x] "Why the market is wrong" articulation
- [x] Catalyst-driven thesis structure with specific dates
- [x] Position sizing recommendation (SMALL/MEDIUM/FULL)
- [x] Key metrics to watch (what would change the thesis)

### 3C. Dashboard Phase 3
- [x] Portfolio risk API endpoint
- [x] Enhanced ValuationTab (WACC breakdown, sensitivity matrix, scenarios, reverse DCF)
- [x] Enhanced FundamentalsTab (ROIC, Piotroski, DuPont, CCC, earnings quality, capital allocation)
- [x] Enhanced OverviewTab (conviction badge, international analysis)
- [x] Enhanced InsiderTab (whale tracking, short interest)
- [x] Enhanced ThesisTab (market mispricing, position sizing, key metrics to watch)

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| Write before Read | 1 | Read file first, then Write full content |
| python not found (macOS) | 1 | Use python3 instead |
| ModuleNotFoundError: ta | 1 | Used ast.parse() for syntax verification instead |

## Key Decisions
- All Phase 1 changes modify existing files (no new modules needed)
- Phase 2 creates new data source modules
- Phase 3 creates new analysis modules + enhances SEC client
- Parallel implementation: split by file/module boundaries across background agents
- SEC risk factor extraction uses direct EDGAR API (no edgartools dependency for new features)
- Stress testing and factor decomposition consolidated into portfolio_risk.py

## Files Summary (15 files, ~7,600+ lines)

| File | Lines | Status |
|------|-------|--------|
| src/analysis/valuation.py | 952 | Modified (overhaul) |
| src/analysis/fundamental.py | 873 | Modified (overhaul) |
| src/analysis/sentiment.py | 397 | Modified (additions) |
| src/analysis/scoring.py | 269 | Modified (conviction) |
| src/analysis/portfolio_risk.py | 429 | NEW |
| src/analysis/international.py | 229 | NEW |
| src/data_sources/sec_filings.py | 370 | Modified (8-K, risk factors) |
| src/data_sources/earnings_estimates.py | 298 | NEW |
| src/data_sources/short_interest.py | 137 | NEW |
| src/data_sources/whale_tracking.py | 346 | NEW |
| src/data_sources/catalyst_calendar.py | 282 | NEW |
| dashboard/api/run_analysis.py | 139 | Modified (5 new modules) |
| dashboard/api/analysis_watcher.py | 309 | Modified (enhanced prompt) |
| dashboard/api/server.py | 1863 | Modified (3 new endpoints) |
| dashboard/frontend/src/views/stock-detail/*.jsx | 2227 | Modified (8 tabs enhanced) |

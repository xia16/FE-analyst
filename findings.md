# Findings & Discoveries

## Current File Structure
- `src/analysis/valuation.py` — DCF + comps, needs WACC fix, two-stage, reverse DCF
- `src/analysis/fundamental.py` — Health/growth/val scoring, needs ROIC, Piotroski, DuPont
- `src/analysis/scoring.py` — Composite weighted scorer, needs conviction scoring
- `src/analysis/risk.py` — Per-stock risk, needs portfolio-level
- `src/analysis/sentiment.py` — News/Reddit/analyst/insider, needs ownership%, estimates
- `src/analysis/moat.py` — 6-dim moat, mostly config-driven
- `src/data_sources/sec_filings.py` — EXISTS but not wired into pipeline
- `src/data_sources/macro_data.py` — FRED series, treasury yields

## Key API Data Available
- yfinance: quarterly_income_stmt, quarterly_balance_sheet, quarterly_cashflow, earnings_dates, analyst_price_targets, major_holders
- Finnhub: earnings_estimates, earnings_calendar, short_interest, filings
- FRED: DGS10 (risk-free rate), VIXCLS (VIX), DEXJPUS (JPY/USD)
- SEC EDGAR: 10-K, 10-Q, 8-K, 13-F (client exists)

## WACC Bug (Critical)
Line ~141 in valuation.py: `"wacc": round(cost_of_equity, 4)` — ignores debt entirely.
Fix: WACC = Ke * E/(E+D) + Kd * (1-t) * D/(E+D)

# Production Upgrade Brainstorm — Making FE-Analyst General Purpose

## Current State: Analyst Prototype
- CLI-based research pipeline (Python)
- Static markdown reports
- Dashboard with live quotes + technicals + alert system
- Focused on Japanese AI infrastructure thesis

## Goal: Production-grade system usable for ANY investment thesis

---

## Team Roles & Brainstorm Contributions

### 1. DATA ENGINEER — Reliability & Scalability

**Problem:** yfinance is rate-limited, undocumented, breaks frequently.

**Proposals:**
- **Add persistent data layer (SQLite/PostgreSQL)**
  - Store all fetched quotes, fundamentals, and technicals
  - Enable historical backtesting without re-fetching
  - Schema: `prices`, `fundamentals`, `technicals`, `alerts`, `watchlists`
  - Estimated effort: 2-3 days

- **Implement multi-source failover**
  - Primary: yfinance → Fallback: Finnhub → Fallback: Alpha Vantage
  - Health checks on each source, automatic failover
  - Rate limit pooling across sources

- **Add data quality checks**
  - Detect stale prices (> 24h old on trading day)
  - Cross-validate between sources (price diff > 2% = flag)
  - Missing data alerts in dashboard

- **Scheduling with Celery or APScheduler persistence**
  - Replace in-memory APScheduler with Redis-backed Celery
  - Job history, retry logic, dead letter queue
  - Configurable scan schedules per watchlist

### 2. QUANT ANALYST — Signal Quality

**Problem:** Current signals are basic (RSI/MACD/BB only). High false positive rate.

**Proposals:**
- **Multi-timeframe confirmation**
  - Require signal on both daily AND weekly timeframe
  - Reduces noise by ~60% based on academic research

- **Volume confirmation layer**
  - RSI oversold + above-average volume = much stronger signal
  - Add OBV (On-Balance Volume) divergence detection
  - Climax volume identification

- **Fundamental filter overlay**
  - Don't alert on stocks with Altman Z < 1.81 (distress zone)
  - Require positive free cash flow for BUY alerts
  - PEG < 2.0 filter for growth-adjusted value

- **Backtesting framework**
  - Test current signal criteria against 5 years of history
  - Measure hit rate, average return, max drawdown per signal
  - Optimize thresholds (RSI 30 vs 35 vs 40)
  - Report: "This RSI oversold signal historically returns X% in 30 days"

- **Composite scoring model**
  - Combine technical + fundamental + moat into single 0-100 buy score
  - Weight configurable per thesis (growth vs value vs momentum)
  - Alert only when composite > threshold

### 3. PRODUCT MANAGER — User Experience

**Problem:** Dashboard is functional but not workflow-oriented.

**Proposals:**
- **Thesis-based workspace system**
  - Create named workspaces: "Japan AI Infra", "US Value Plays", "Biotech Pipeline"
  - Each workspace has its own watchlist, alert rules, allocation targets
  - Switch between workspaces from nav bar
  - Makes the tool general-purpose for any investment thesis

- **Custom alert rules UI**
  - Allow users to define custom alert criteria in the dashboard
  - Example: "Alert me when HTHIY RSI < 30 AND price < $45"
  - Drag-and-drop rule builder with AND/OR logic
  - Email/webhook notification support

- **Portfolio tracker with cost basis**
  - Enter actual positions: shares, avg cost, date
  - Track P&L, unrealized gains, portfolio value
  - Compare actual allocation vs target allocation
  - Daily/weekly/monthly performance tracking

- **News & catalyst feed**
  - Integrate Finnhub news API per watchlist
  - FinBERT sentiment scoring on headlines
  - Earnings calendar overlay (highlight upcoming earnings)
  - Configurable: show only negative sentiment or all

- **Mobile-responsive PWA**
  - Make dashboard installable as mobile app
  - Push notifications for buy alerts
  - Critical for checking alerts on the go

### 4. DEVOPS ENGINEER — Deployment & Reliability

**Problem:** Currently localhost-only, no persistence, no CI/CD.

**Proposals:**
- **Docker Compose setup**
  ```yaml
  services:
    api:
      build: ./api
      ports: ["8000:8000"]
      volumes: ["./configs:/app/configs"]
    frontend:
      build: ./frontend
      ports: ["3000:3000"]
    db:
      image: postgres:16
      volumes: ["pgdata:/var/lib/postgresql/data"]
    redis:
      image: redis:7
  ```

- **Cloud deployment options**
  - Railway/Render: $0-7/mo for hobby tier
  - Fly.io: good for always-on with generous free tier
  - Self-hosted: Raspberry Pi + Tailscale for private access

- **Notification pipeline**
  - Slack webhook for buy alerts
  - Email via SendGrid/Resend (free tier)
  - Telegram bot integration
  - Webhook for n8n/Zapier automation

- **Monitoring**
  - Uptime checks on API health endpoint
  - Alert if daily scan fails
  - Data freshness dashboard (when was each ticker last updated?)

### 5. SECURITY & COMPLIANCE

**Proposals:**
- **API key vault** — Move all API keys to environment variables or secrets manager
- **Authentication** — Add basic auth or JWT if deploying to cloud
- **Audit logging** — Log all alert triggers and user actions
- **Disclaimer system** — Auto-append "not financial advice" to all views/exports
- **Rate limit API** — Prevent abuse if exposed publicly

---

## Priority Matrix

| Priority | Item | Impact | Effort | Sprint |
|----------|------|--------|--------|--------|
| P0 | SQLite persistence for alerts & prices | HIGH | 2d | 1 |
| P0 | Thesis-based workspaces | HIGH | 3d | 1 |
| P0 | Docker Compose | MEDIUM | 1d | 1 |
| P1 | Multi-timeframe signal confirmation | HIGH | 2d | 2 |
| P1 | Portfolio tracker with cost basis | HIGH | 3d | 2 |
| P1 | Slack/email notifications | HIGH | 1d | 2 |
| P1 | Backtesting framework | HIGH | 5d | 2 |
| P2 | Custom alert rules UI | MEDIUM | 3d | 3 |
| P2 | News & catalyst feed | MEDIUM | 2d | 3 |
| P2 | Cloud deployment | MEDIUM | 2d | 3 |
| P3 | Mobile PWA | LOW | 2d | 4 |
| P3 | Multi-source failover | LOW | 3d | 4 |
| P3 | Composite scoring model | MEDIUM | 4d | 4 |

---

## Migration Path: Thesis-Specific → General Purpose

### Phase 1: Foundation (Current + Sprint 1)
- Dashboard works for Japanese AI infrastructure thesis ✅
- Add workspaces so you can create new thesis without changing code
- Add persistence so alerts survive restarts
- Docker for easy deployment anywhere

### Phase 2: Signal Quality (Sprint 2)
- Reduce false positives with multi-timeframe + volume confirmation
- Add backtesting to validate signals before trusting them
- Track actual portfolio performance

### Phase 3: Workflow Automation (Sprint 3)
- Get alerts on your phone/Slack without opening the dashboard
- Custom rules per workspace
- News integration for context

### Phase 4: Scale (Sprint 4)
- Deploy to cloud for 24/7 monitoring
- Mobile app for quick checks
- Advanced scoring model

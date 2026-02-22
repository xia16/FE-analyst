# Multi-Domain Dashboard Architecture Plan

## Core Concept

The dashboard has two layers:

1. **Domain views** — scoped to one investment thesis (e.g. "AI Infrastructure", "Supermarkets")
   - Each domain has its own YAML file, its own universe of companies, scoring dimensions, tiers, categories, portfolio recommendations
   - Portfolio, Universe map, Scoring heatmap are all domain-specific

2. **Global tools** — work across all domains holistically
   - Stock Detail, Analyze, Reports, Buy Alerts work on any ticker regardless of domain
   - Alerts scan ALL domains' companies, with a domain filter chip
   - Reports are stored flat and browsable, with domain tag if generated from a domain context

## Navigation UX

```
┌─────────────────────────────────────────────────────────────────┐
│ FE  FE-Analyst Dashboard    [domain selector ▾]    Tools ▾     │
│                              AI Infrastructure     Stock Detail │
│                              (future: Supermarkets) Analyze     │
│                                                     Reports     │
│                                                     Buy Alerts  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  When a domain is selected, show sub-tabs:                      │
│  ┌──────────┬──────────────────┬───────────────┐                │
│  │ Portfolio │ Supply Chain Map │ Moat Heatmap  │                │
│  └──────────┴──────────────────┴───────────────┘                │
│  (tab labels come from the domain's YAML)                       │
│                                                                 │
│  When a tool is selected (Stock Detail/Analyze/Reports/Alerts): │
│  Shows global view with optional domain filter                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Layout**: Left side of nav has the domain selector (dropdown). Right side has global tool buttons. When a domain is active, its sub-tabs render below the main nav (or inline). This is a clean separation: "where am I looking" (domain) vs "what tool am I using" (global).

## File Structure

```
configs/
  domains/
    ai_infrastructure.yaml    ← renamed from ai_moat_universe.yaml
    (future: supermarkets.yaml, commercial_goods.yaml, etc.)
  profiles.yaml               ← stays global
  watchlists.yaml             ← stays global
```

Each domain YAML has the exact same structure as `ai_moat_universe.yaml` today — with `domain:` metadata block and `categories:` block. No format changes needed.

A new `configs/domains.yaml` registry file lists active domains:
```yaml
domains:
  - id: ai_infrastructure
    file: domains/ai_infrastructure.yaml
    icon: "cpu"     # optional icon hint
    color: "#3b82f6"
  # - id: supermarkets
  #   file: domains/supermarkets.yaml
  #   icon: "shopping-cart"
  #   color: "#22c55e"
```

## Backend Changes

### New endpoints
- `GET /api/domains` — returns list of all registered domains with id, name, color, icon
- `GET /api/domains/{domain_id}` — returns full domain metadata (replaces `/api/domain`)
- `GET /api/domains/{domain_id}/universe` — returns universe for that domain (replaces `/api/universe`)
- `GET /api/domains/{domain_id}/heatmap` — returns heatmap for that domain (replaces `/api/moat-heatmap`)
- `GET /api/domains/{domain_id}/portfolio` — returns portfolio for that domain (replaces `/api/portfolio`)

### Updated endpoints (global, cross-domain)
- `GET /api/alerts` — scans ALL domains, each alert tagged with `domainId`
- `POST /api/alerts/scan` — scans ALL domains
- `GET /api/reports` — stays global (reports dir is flat)
- `GET /api/quote/{ticker}` — stays global
- `GET /api/technicals/{ticker}` — stays global
- `GET /api/history/{ticker}` — stays global
- `POST /api/reports/generate` — stays global

### Removed/replaced
- `GET /api/domain` → replaced by `/api/domains/{id}`
- `GET /api/universe` → replaced by `/api/domains/{id}/universe`
- `GET /api/moat-heatmap` → replaced by `/api/domains/{id}/heatmap`
- `GET /api/portfolio` → replaced by `/api/domains/{id}/portfolio`

### Internal changes
- `load_universe()` → `load_domain_file(domain_id)` — loads from `configs/domains/{id}.yaml`
- `_load_domain_config()` → reads from specific domain file
- `_load_portfolio_recs()` → scoped to domain
- `check_buy_opportunities()` → iterates ALL domains, tags alerts with domain_id
- `_build_name_lookup()` → builds from ALL domains

## Frontend Changes

### State
```
activeDomain: string | null     ← which domain is selected (null = global tools)
activeView: string              ← 'portfolio' | 'universe' | 'heatmap' | 'alerts' | 'detail' | 'generate' | 'reports'
```

### New hooks
- `useDomains()` → fetches `/api/domains` — list of all domains
- `useDomainMeta(domainId)` → fetches `/api/domains/{id}` — single domain metadata
- `useDomainUniverse(domainId)` → fetches `/api/domains/{id}/universe`
- `useDomainHeatmap(domainId)` → fetches `/api/domains/{id}/heatmap`
- `useDomainPortfolio(domainId)` → fetches `/api/domains/{id}/portfolio`

### Navigation Component
Top bar layout:
- Left: FE logo + "FE-Analyst"
- Center: Domain selector dropdown (shows domain name + colored dot)
  - When a domain is selected, show its sub-tabs inline: Portfolio | {tabLabel} | {heatmapLabel}
- Right: Global tool buttons: Alerts (with badge) | Stock Detail | Analyze | Reports

### View routing
- If `activeDomain` is set AND `activeView` is `portfolio`/`universe`/`heatmap`:
  → render domain-scoped views (same components as today, but fetching from domain-scoped endpoints)
- If `activeView` is `alerts`/`detail`/`generate`/`reports`:
  → render global views (same as today)
  → Alerts view gets a domain filter dropdown at the top

### Alerts enhancement
- Each alert includes `domainId` and `domainName`
- AlertsView shows a filter bar at top: "All Domains | AI Infrastructure | ..."
- Clicking a domain filter shows only alerts from that domain

## Adding a New Domain

When user asks in Claude Code: "add a Supermarkets domain", the workflow is:
1. Create `configs/domains/supermarkets.yaml` with the same structure (domain metadata + categories + companies)
2. Add entry to `configs/domains.yaml` registry
3. No code changes needed — dashboard auto-discovers it

## Implementation Order

1. Create `configs/domains.yaml` registry + move `ai_moat_universe.yaml` → `configs/domains/ai_infrastructure.yaml`
2. Update `server.py` — new domain-scoped endpoints, multi-domain alert scanning
3. Update `hooks.js` — new domain-scoped hooks
4. Rewrite `App.jsx` navigation — domain selector + global tools split
5. Update domain-scoped views to use new hooks
6. Update AlertsView with domain filter
7. Test everything end-to-end

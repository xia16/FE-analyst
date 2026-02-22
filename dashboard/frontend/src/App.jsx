import React, { useState, useEffect, useCallback } from 'react'
import {
  useDomains, useDomainMeta, useDomainPortfolio, useDomainUniverse, useDomainHeatmap,
  useAlerts, useTechnicals, useHistory, useReports, useReport, useProfiles,
  useHoldings, useTradeHistory, useAllocation, usePerformance, useBenchmark, useMovers,
} from './hooks'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  AreaChart, Area, BarChart, Bar, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, PieChart, Pie,
  LineChart, Line, Legend
} from 'recharts'

// ─── Utility ───────────────────────────────────────────────
const fmt = (n, decimals = 2) => n == null ? '—' : Number(n).toFixed(decimals)
const fmtPct = (n) => n == null ? '—' : `${n >= 0 ? '+' : ''}${Number(n).toFixed(2)}%`
const fmtCurrency = (n) => {
  if (n == null) return '—'
  if (n >= 1e12) return `$${(n / 1e12).toFixed(1)}T`
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`
  return `$${n.toLocaleString()}`
}

const RATING_COLORS = {
  'STRONG BUY': '#22c55e',
  'BUY': '#4ade80',
  'HOLD': '#eab308',
  'AVOID': '#ef4444',
}

const DEFAULT_TIER_COLOR = '#3b82f6'

// ─── Components ────────────────────────────────────────────

function Card({ children, className = '', onClick, style }) {
  return (
    <div
      className={`bg-[#1e2130] border border-[#2a2d3e] rounded-xl p-4 ${onClick ? 'cursor-pointer hover:bg-[#252940] transition-colors' : ''} ${className}`}
      onClick={onClick}
      style={style}
    >
      {children}
    </div>
  )
}

function Badge({ children, color = '#3b82f6' }) {
  return (
    <span
      className="px-2 py-0.5 rounded-full text-xs font-medium"
      style={{ background: `${color}20`, color }}
    >
      {children}
    </span>
  )
}

function Spinner() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="w-8 h-8 border-2 border-[#3b82f6] border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

// ─── Navigation ────────────────────────────────────────────

function Nav({ activeDomain, setActiveDomain, activeView, setActiveView, alertCount, domains, domainMeta }) {
  const [domainOpen, setDomainOpen] = useState(false)

  const currentDomain = domains?.find(d => d.id === activeDomain)

  // Domain sub-tabs (only shown when a domain is active)
  const domainTabs = activeDomain ? [
    { id: 'portfolio', label: 'Portfolio' },
    { id: 'universe', label: domainMeta?.tabLabel || 'Universe' },
    { id: 'heatmap', label: domainMeta?.heatmapLabel || 'Heatmap' },
  ] : []

  // Global tool buttons
  const globalTools = [
    { id: 'holdings', label: 'My Holdings' },
    { id: 'alerts', label: 'Buy Alerts' },
    { id: 'detail', label: 'Stock Detail' },
    { id: 'generate', label: 'Analyze' },
    { id: 'reports', label: 'Reports' },
  ]

  const isDomainView = ['portfolio', 'universe', 'heatmap'].includes(activeView)

  return (
    <header className="sticky top-0 z-50 bg-[#0f1117]/90 backdrop-blur-md border-b border-[#2a2d3e]">
      <div className="max-w-[1600px] mx-auto px-4 sm:px-6">
        {/* Main bar */}
        <div className="flex items-center justify-between h-14">
          {/* Left: Logo + Domain selector */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-sm font-bold">
              FE
            </div>
            <span className="font-semibold text-sm hidden sm:block">FE-Analyst</span>

            {/* Domain selector */}
            {domains && domains.length > 0 && (
              <div className="relative ml-2">
                <button
                  onClick={() => setDomainOpen(!domainOpen)}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    activeDomain
                      ? 'bg-[#1e2130] text-white border border-[#2a2d3e]'
                      : 'text-[#8b8d97] hover:text-white hover:bg-[#1e2130]'
                  }`}
                >
                  {currentDomain && (
                    <div className="w-2 h-2 rounded-full" style={{ background: currentDomain.color }} />
                  )}
                  {currentDomain?.name || 'Select Domain'}
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {domainOpen && (
                  <div className="absolute top-full left-0 mt-1 bg-[#1e2130] border border-[#2a2d3e] rounded-lg shadow-xl min-w-[200px] py-1 z-50">
                    {domains.map(d => (
                      <button
                        key={d.id}
                        onClick={() => {
                          setActiveDomain(d.id)
                          setActiveView('portfolio')
                          setDomainOpen(false)
                        }}
                        className={`w-full text-left px-3 py-2 text-xs flex items-center gap-2 transition-colors ${
                          activeDomain === d.id ? 'bg-[#252940] text-white' : 'text-[#8b8d97] hover:bg-[#252940] hover:text-white'
                        }`}
                      >
                        <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: d.color }} />
                        <div>
                          <div className="font-medium">{d.name}</div>
                          {d.description && <div className="text-[10px] text-[#8b8d97] mt-0.5 line-clamp-1">{d.description}</div>}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right: Global tools */}
          <nav className="flex items-center gap-1">
            {globalTools.map(tool => (
              <button
                key={tool.id}
                onClick={() => setActiveView(tool.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors relative ${
                  activeView === tool.id && !isDomainView
                    ? 'bg-[#3b82f6] text-white'
                    : 'text-[#8b8d97] hover:text-white hover:bg-[#1e2130]'
                }`}
              >
                {tool.label}
                {tool.id === 'alerts' && alertCount > 0 && (
                  <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-500 text-[10px] flex items-center justify-center">
                    {alertCount}
                  </span>
                )}
              </button>
            ))}
          </nav>
        </div>

        {/* Domain sub-tabs (second row, only when domain active) */}
        {activeDomain && domainTabs.length > 0 && (
          <div className="flex items-center gap-1 pb-2 -mt-1">
            {domainTabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveView(tab.id)}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                  activeView === tab.id
                    ? 'text-white'
                    : 'text-[#8b8d97] hover:text-white hover:bg-[#1e2130]'
                }`}
                style={activeView === tab.id ? { background: `${currentDomain?.color || '#3b82f6'}30`, color: currentDomain?.color || '#3b82f6' } : {}}
              >
                {tab.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </header>
  )
}

// ─── Portfolio Dashboard ───────────────────────────────────

function PortfolioView({ domainId }) {
  const { data, loading, error } = useDomainPortfolio(domainId)

  if (loading) return <Spinner />
  if (error) return <div className="text-red-400 p-4">Error: {error}</div>
  if (!data?.portfolio) return null

  const portfolio = data.portfolio.filter(p => !p.error)
  const sorted = [...portfolio].sort((a, b) => (b.changePct || 0) - (a.changePct || 0))

  const allocationData = portfolio
    .filter(p => p.recommendation?.allocation > 0)
    .map(p => ({
      name: p.ticker,
      value: p.recommendation.allocation,
      rating: p.recommendation.rating,
    }))

  return (
    <div className="space-y-6 animate-slide-in">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <div className="text-[#8b8d97] text-xs mb-1">Tracked Positions</div>
          <div className="text-2xl font-bold">{portfolio.length}</div>
        </Card>
        <Card>
          <div className="text-[#8b8d97] text-xs mb-1">Strong Buy / Buy</div>
          <div className="text-2xl font-bold text-green-400">
            {portfolio.filter(p => p.recommendation?.rating?.includes('BUY')).length}
          </div>
        </Card>
        <Card>
          <div className="text-[#8b8d97] text-xs mb-1">Today's Gainers</div>
          <div className="text-2xl font-bold text-green-400">
            {portfolio.filter(p => (p.changePct || 0) > 0).length}
          </div>
        </Card>
        <Card>
          <div className="text-[#8b8d97] text-xs mb-1">Today's Losers</div>
          <div className="text-2xl font-bold text-red-400">
            {portfolio.filter(p => (p.changePct || 0) < 0).length}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-1">
          <h3 className="text-sm font-semibold mb-4">Target Allocation</h3>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={allocationData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={100}
                dataKey="value"
                label={({ name, value }) => `${name} ${value}%`}
                labelLine={false}
              >
                {allocationData.map((entry) => (
                  <Cell
                    key={entry.name}
                    fill={RATING_COLORS[entry.rating] || '#3b82f6'}
                    stroke="none"
                  />
                ))}
              </Pie>
              <Tooltip formatter={(v) => `${v}%`} contentStyle={{ background: '#1e2130', border: '1px solid #2a2d3e', borderRadius: 8 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap gap-2 mt-2 justify-center">
            {Object.entries(RATING_COLORS).map(([label, color]) => (
              <div key={label} className="flex items-center gap-1 text-xs">
                <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
                {label}
              </div>
            ))}
          </div>
        </Card>

        <Card className="lg:col-span-2 overflow-x-auto">
          <h3 className="text-sm font-semibold mb-4">Portfolio Holdings — Live</h3>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[#8b8d97] border-b border-[#2a2d3e]">
                <th className="text-left py-2 pr-2">Ticker</th>
                <th className="text-left py-2 pr-2">Name</th>
                <th className="text-right py-2 pr-2">Price</th>
                <th className="text-right py-2 pr-2">Change</th>
                <th className="text-right py-2 pr-2">Mkt Cap</th>
                <th className="text-right py-2 pr-2">Fwd P/E</th>
                <th className="text-center py-2 pr-2">Rating</th>
                <th className="text-right py-2">Alloc</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(p => (
                <tr key={p.ticker} className="border-b border-[#2a2d3e]/50 hover:bg-[#252940] transition-colors">
                  <td className="py-2 pr-2 font-mono font-semibold">{p.ticker}</td>
                  <td className="py-2 pr-2 text-[#8b8d97] max-w-[160px] truncate">{p.name}</td>
                  <td className="py-2 pr-2 text-right font-mono">{fmt(p.price)}</td>
                  <td className={`py-2 pr-2 text-right font-mono ${(p.changePct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {fmtPct(p.changePct)}
                  </td>
                  <td className="py-2 pr-2 text-right text-[#8b8d97]">{fmtCurrency(p.marketCap)}</td>
                  <td className="py-2 pr-2 text-right">{fmt(p.recommendation?.fwd_pe, 0)}x</td>
                  <td className="py-2 pr-2 text-center">
                    <Badge color={RATING_COLORS[p.recommendation?.rating] || '#8b8d97'}>
                      {p.recommendation?.rating || '—'}
                    </Badge>
                  </td>
                  <td className="py-2 text-right font-mono">{p.recommendation?.allocation || 0}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>

      <Card>
        <h3 className="text-sm font-semibold mb-4">Today's Performance (%)</h3>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={sorted} layout="vertical" margin={{ left: 60 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3e" />
            <XAxis type="number" tick={{ fill: '#8b8d97', fontSize: 10 }} tickFormatter={v => `${v}%`} />
            <YAxis type="category" dataKey="ticker" tick={{ fill: '#e4e5e7', fontSize: 10, fontFamily: 'monospace' }} width={55} />
            <Tooltip
              contentStyle={{ background: '#1e2130', border: '1px solid #2a2d3e', borderRadius: 8 }}
              formatter={(v) => [`${v}%`, 'Change']}
            />
            <Bar dataKey="changePct" radius={[0, 4, 4, 0]}>
              {sorted.map((entry) => (
                <Cell key={entry.ticker} fill={(entry.changePct || 0) >= 0 ? '#22c55e' : '#ef4444'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Card>
    </div>
  )
}

// ─── Universe View ─────────────────────────────────────────

function UniverseView({ domainId, domainMeta, onSelectTicker }) {
  const tiers = domainMeta?.tiers || {}
  const dimensions = domainMeta?.dimensions || {}
  const extraMetrics = domainMeta?.extraMetrics || {}
  const { data, loading, error } = useDomainUniverse(domainId)
  const [expandedCat, setExpandedCat] = useState(null)

  if (loading) return <Spinner />
  if (error) return <div className="text-red-400 p-4">Error: {error}</div>
  if (!data) return null

  const categories = Object.entries(data)

  return (
    <div className="space-y-6 animate-slide-in">
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {categories.map(([key, cat]) => (
          <Card key={key} onClick={() => setExpandedCat(expandedCat === key ? null : key)}>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold" style={{ color: cat.color || '#3b82f6' }}>
                {cat.label || key}
              </h3>
              <span className="text-xs text-[#8b8d97]">{cat.companies.length} cos</span>
            </div>
            <p className="text-[10px] text-[#8b8d97] mb-3 line-clamp-2">{cat.description}</p>
            <div className="flex flex-wrap gap-1">
              {cat.companies.slice(0, 5).map(c => {
                const tierColor = tiers[c.tier]?.color || DEFAULT_TIER_COLOR
                return (
                  <span
                    key={c.ticker}
                    className="px-1.5 py-0.5 rounded text-[10px] font-mono cursor-pointer hover:opacity-80 transition"
                    style={{
                      background: `${tierColor}15`,
                      color: tierColor,
                      border: `1px solid ${tierColor}30`
                    }}
                    onClick={(e) => { e.stopPropagation(); onSelectTicker(c.adr || c.ticker) }}
                  >
                    {c.adr || c.ticker}
                  </span>
                )
              })}
              {cat.companies.length > 5 && (
                <span className="text-[10px] text-[#8b8d97]">+{cat.companies.length - 5} more</span>
              )}
            </div>
          </Card>
        ))}
      </div>

      {expandedCat && data[expandedCat] && (
        <Card className="animate-slide-in">
          <h3 className="text-sm font-semibold mb-4" style={{ color: data[expandedCat].color || '#3b82f6' }}>
            {data[expandedCat].label || expandedCat} — Full List
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {data[expandedCat].companies.map(c => {
              const tierColor = tiers[c.tier]?.color || DEFAULT_TIER_COLOR
              const tierShort = tiers[c.tier]?.label?.split('—')[1]?.trim() || c.tier
              return (
                <div
                  key={c.ticker}
                  className="p-3 rounded-lg bg-[#0f1117] border border-[#2a2d3e] hover:border-[#3b82f6] transition-colors cursor-pointer"
                  onClick={() => onSelectTicker(c.adr || c.ticker)}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono font-semibold text-sm">{c.adr || c.ticker}</span>
                    <Badge color={tierColor}>{tierShort}</Badge>
                  </div>
                  <div className="text-xs text-[#8b8d97] mb-2">{c.name} ({c.country})</div>
                  <p className="text-[10px] text-[#8b8d97] line-clamp-2 mb-2">{c.moat}</p>
                  <div className="flex items-center gap-3 text-[10px]">
                    <span>Score: <strong className="text-white">{c.moatScore}</strong>/100</span>
                    {Object.entries(c.extras || {}).map(([ek, ev]) => {
                      const metric = extraMetrics[ek]
                      return ev != null ? (
                        <span key={ek}>
                          {metric?.label || ek}: <strong style={{ color: metric?.color || '#8b8d97' }}>{ev}{metric?.suffix || ''}</strong>
                        </span>
                      ) : null
                    })}
                    {c.recommendation?.rating && (
                      <Badge color={RATING_COLORS[c.recommendation.rating]}>{c.recommendation.rating}</Badge>
                    )}
                  </div>
                  <div className="mt-2 space-y-0.5">
                    {Object.entries(c.breakdown || {}).map(([k, v]) => (
                      <div key={k} className="flex items-center gap-1">
                        <span className="text-[9px] text-[#8b8d97] w-24 truncate">{dimensions[k]?.label || k}</span>
                        <div className="flex-1 h-1.5 bg-[#1a1d27] rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{
                              width: `${v}%`,
                              background: v >= 90 ? '#22c55e' : v >= 75 ? '#3b82f6' : v >= 60 ? '#eab308' : '#ef4444'
                            }}
                          />
                        </div>
                        <span className="text-[9px] font-mono w-6 text-right">{v}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        </Card>
      )}

      {Object.keys(tiers).length > 0 && (
        <Card>
          <h3 className="text-sm font-semibold mb-3">Tier Classification</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {Object.entries(tiers).map(([tier, info]) => (
              <div key={tier} className="flex items-start gap-2">
                <div className="w-3 h-3 rounded-full mt-0.5 flex-shrink-0" style={{ background: info.color }} />
                <div>
                  <div className="text-xs font-semibold" style={{ color: info.color }}>{info.label}</div>
                  {info.description && (
                    <div className="text-[10px] text-[#8b8d97]">{info.description}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

// ─── Heatmap View ──────────────────────────────────────────

function HeatmapView({ domainId, domainMeta, onSelectTicker }) {
  const { data, loading, error } = useDomainHeatmap(domainId)
  const tiers = domainMeta?.tiers || {}
  const domainDims = domainMeta?.dimensions || {}

  if (loading) return <Spinner />
  if (error) return <div className="text-red-400 p-4">Error: {error}</div>
  if (!data) return null

  const heatmapData = Array.isArray(data) ? data : []
  const dimKeys = Object.keys(domainDims)
  const dimLabels = Object.fromEntries(
    Object.entries(domainDims).map(([k, v]) => [k, v.label || k])
  )

  const heatColor = (v) => {
    if (v >= 95) return '#22c55e'
    if (v >= 85) return '#4ade80'
    if (v >= 75) return '#3b82f6'
    if (v >= 65) return '#60a5fa'
    return '#8b8d97'
  }

  const top8 = heatmapData.slice(0, 8)
  const radarData = dimKeys.map(dim => {
    const entry = { dimension: dimLabels[dim] }
    top8.forEach(c => { entry[c.ticker] = c[dim] })
    return entry
  })

  const radarColors = ['#3b82f6', '#22c55e', '#ef4444', '#eab308', '#a855f7', '#06b6d4', '#ec4899', '#f97316']

  return (
    <div className="space-y-6 animate-slide-in">
      <Card>
        <h3 className="text-sm font-semibold mb-4">Scoring Radar — Top 8 Companies</h3>
        <ResponsiveContainer width="100%" height={400}>
          <RadarChart data={radarData}>
            <PolarGrid stroke="#2a2d3e" />
            <PolarAngleAxis dataKey="dimension" tick={{ fill: '#8b8d97', fontSize: 10 }} />
            <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: '#8b8d97', fontSize: 9 }} />
            {top8.map((c, i) => (
              <Radar
                key={c.ticker}
                name={c.ticker}
                dataKey={c.ticker}
                stroke={radarColors[i]}
                fill={radarColors[i]}
                fillOpacity={0.05}
                strokeWidth={1.5}
              />
            ))}
            <Legend wrapperStyle={{ fontSize: 10 }} />
            <Tooltip contentStyle={{ background: '#1e2130', border: '1px solid #2a2d3e', borderRadius: 8, fontSize: 11 }} />
          </RadarChart>
        </ResponsiveContainer>
      </Card>

      <Card className="overflow-x-auto">
        <h3 className="text-sm font-semibold mb-4">Full Heatmap — {heatmapData.length} Companies</h3>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-[#8b8d97] border-b border-[#2a2d3e]">
              <th className="text-left py-2 pr-2">#</th>
              <th className="text-left py-2 pr-2">Ticker</th>
              <th className="text-left py-2 pr-2">Name</th>
              <th className="text-center py-2 pr-2">Tier</th>
              <th className="text-center py-2 pr-2">Category</th>
              {dimKeys.map(d => (
                <th key={d} className="text-center py-2 px-1">{dimLabels[d]}</th>
              ))}
              <th className="text-center py-2 pl-2 font-bold">Composite</th>
            </tr>
          </thead>
          <tbody>
            {heatmapData.map((c, i) => (
              <tr
                key={c.ticker}
                className="border-b border-[#2a2d3e]/30 hover:bg-[#252940] transition-colors cursor-pointer"
                onClick={() => onSelectTicker(c.ticker)}
              >
                <td className="py-1.5 pr-2 text-[#8b8d97]">{i + 1}</td>
                <td className="py-1.5 pr-2 font-mono font-semibold">{c.ticker}</td>
                <td className="py-1.5 pr-2 text-[#8b8d97] max-w-[140px] truncate">{c.name}</td>
                <td className="py-1.5 pr-2 text-center">
                  <span className="inline-block w-2 h-2 rounded-full" style={{ background: tiers[c.tier]?.color || DEFAULT_TIER_COLOR }} />
                </td>
                <td className="py-1.5 pr-2 text-center text-[10px]" style={{ color: c.categoryColor || '#3b82f6' }}>
                  {c.categoryLabel?.split(' ')[0] || c.category}
                </td>
                {dimKeys.map(d => (
                  <td key={d} className="py-1.5 px-1 text-center">
                    <span
                      className="inline-block px-2 py-0.5 rounded text-[10px] font-mono font-bold"
                      style={{ background: `${heatColor(c[d])}20`, color: heatColor(c[d]) }}
                    >
                      {c[d]}
                    </span>
                  </td>
                ))}
                <td className="py-1.5 pl-2 text-center">
                  <span
                    className="inline-block px-2.5 py-0.5 rounded-full text-xs font-bold"
                    style={{ background: `${heatColor(c.composite)}25`, color: heatColor(c.composite) }}
                  >
                    {c.composite}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}

// ─── Buy Alerts ────────────────────────────────────────────

function AlertsView({ onSelectTicker, domains }) {
  const { data, loading, error, refetch } = useAlerts()
  const [scanning, setScanning] = useState(false)
  const [domainFilter, setDomainFilter] = useState(null)

  const triggerScan = async () => {
    setScanning(true)
    try {
      const res = await fetch('/api/alerts/scan', { method: 'POST' })
      await res.json()
      refetch()
    } finally {
      setScanning(false)
    }
  }

  if (loading) return <Spinner />
  if (error) return <div className="text-red-400 p-4">Error: {error}</div>

  const allAlerts = data?.alerts || []
  const alerts = domainFilter
    ? allAlerts.filter(a => a.domainId === domainFilter)
    : allAlerts

  // Get unique domains from alerts
  const alertDomains = [...new Set(allAlerts.map(a => a.domainId).filter(Boolean))]

  return (
    <div className="space-y-6 animate-slide-in">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold">Buy Opportunity Alerts</h2>
          <p className="text-xs text-[#8b8d97]">
            Scans run daily at 09:00 UTC across all domains. Looking for: RSI oversold, near 52-week lows, Bollinger Band support, bullish crossovers.
          </p>
        </div>
        <button
          onClick={triggerScan}
          disabled={scanning}
          className="px-4 py-2 bg-[#3b82f6] text-white text-xs font-medium rounded-lg hover:bg-[#2563eb] disabled:opacity-50 transition-colors"
        >
          {scanning ? 'Scanning...' : 'Run Scan Now'}
        </button>
      </div>

      {/* Domain filter chips */}
      {alertDomains.length > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-[#8b8d97]">Filter:</span>
          <button
            onClick={() => setDomainFilter(null)}
            className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
              !domainFilter ? 'bg-[#3b82f6] text-white' : 'bg-[#1e2130] text-[#8b8d97] hover:text-white'
            }`}
          >
            All Domains
          </button>
          {alertDomains.map(dId => {
            const d = domains?.find(x => x.id === dId)
            return (
              <button
                key={dId}
                onClick={() => setDomainFilter(domainFilter === dId ? null : dId)}
                className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors flex items-center gap-1.5 ${
                  domainFilter === dId ? 'bg-[#3b82f6] text-white' : 'bg-[#1e2130] text-[#8b8d97] hover:text-white'
                }`}
              >
                {d && <div className="w-2 h-2 rounded-full" style={{ background: d.color }} />}
                {d?.name || dId}
              </button>
            )
          })}
        </div>
      )}

      {alerts.length === 0 ? (
        <Card>
          <div className="text-center py-12 text-[#8b8d97]">
            <p className="text-lg mb-2">No Alerts</p>
            <p>{domainFilter ? 'No alerts for this domain.' : 'No buy alerts yet. Click "Run Scan Now" to scan all tracked companies.'}</p>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {alerts.map(alert => {
            const d = domains?.find(x => x.id === alert.domainId)
            return (
              <Card
                key={alert.id}
                className="border-l-4"
                style={{ borderLeftColor: '#22c55e' }}
                onClick={() => onSelectTicker(alert.ticker)}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-sm">{alert.ticker}</span>
                    <span className="text-xs text-[#8b8d97]">{alert.name}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {d && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-medium" style={{ background: `${d.color}20`, color: d.color }}>
                        {d.name}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-4 text-xs text-[#8b8d97] mb-3">
                  {alert.rsi && <span>RSI: <strong className={alert.rsi < 30 ? 'text-green-400' : 'text-white'}>{fmt(alert.rsi, 1)}</strong></span>}
                  {alert.distFromHigh && <span>From High: <strong className="text-yellow-400">{fmtPct(alert.distFromHigh)}</strong></span>}
                </div>
                <div className="space-y-1">
                  {alert.reasons.map((r, i) => (
                    <div key={i} className="flex items-center gap-1.5 text-xs">
                      <span className="text-green-400">*</span>
                      <span>{r}</span>
                    </div>
                  ))}
                </div>
                <div className="text-[10px] text-[#8b8d97] mt-2">
                  {new Date(alert.timestamp).toLocaleString()}
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ─── Stock Detail ──────────────────────────────────────────

function StockDetailView({ ticker, setTicker }) {
  const [inputVal, setInputVal] = useState(ticker || '')
  const [period, setPeriod] = useState('6mo')
  const { data: techData, loading: techLoading } = useTechnicals(ticker)
  const { data: histData, loading: histLoading } = useHistory(ticker, period)
  const [quoteData, setQuoteData] = useState(null)

  useEffect(() => {
    if (!ticker) return
    fetch(`/api/quote/${ticker}`).then(r => r.json()).then(setQuoteData)
  }, [ticker])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (inputVal.trim()) setTicker(inputVal.trim().toUpperCase())
  }

  return (
    <div className="space-y-6 animate-slide-in">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          placeholder="Enter ticker (e.g. ATEYY, HTHIY, 8035.T)"
          className="flex-1 bg-[#1e2130] border border-[#2a2d3e] rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-[#3b82f6] transition-colors"
        />
        <button
          type="submit"
          className="px-6 py-2 bg-[#3b82f6] text-white text-sm font-medium rounded-lg hover:bg-[#2563eb] transition-colors"
        >
          Load
        </button>
      </form>

      {!ticker ? (
        <Card>
          <div className="text-center py-12 text-[#8b8d97]">
            <p className="text-lg mb-2">Search</p>
            <p>Enter a ticker symbol above or click on a company from other views.</p>
          </div>
        </Card>
      ) : (
        <>
          {quoteData && !quoteData.error && (
            <Card>
              <div className="flex items-center justify-between flex-wrap gap-4">
                <div>
                  <div className="flex items-center gap-3">
                    <h2 className="text-xl font-bold font-mono">{quoteData.ticker}</h2>
                    <span className="text-sm text-[#8b8d97]">{quoteData.name}</span>
                  </div>
                  <div className="flex items-center gap-4 mt-1">
                    <span className="text-2xl font-bold">{quoteData.currency === 'JPY' ? '\u00a5' : '$'}{fmt(quoteData.price)}</span>
                    <span className={`text-lg font-semibold ${(quoteData.changePct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {fmtPct(quoteData.changePct)}
                    </span>
                  </div>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
                  <div>
                    <div className="text-[#8b8d97]">Market Cap</div>
                    <div className="font-semibold">{fmtCurrency(quoteData.marketCap)}</div>
                  </div>
                  <div>
                    <div className="text-[#8b8d97]">P/E (Trailing)</div>
                    <div className="font-semibold">{fmt(quoteData.trailingPE, 1)}x</div>
                  </div>
                  <div>
                    <div className="text-[#8b8d97]">52W High</div>
                    <div className="font-semibold">{fmt(quoteData.fiftyTwoWeekHigh)}</div>
                  </div>
                  <div>
                    <div className="text-[#8b8d97]">52W Low</div>
                    <div className="font-semibold">{fmt(quoteData.fiftyTwoWeekLow)}</div>
                  </div>
                </div>
              </div>
            </Card>
          )}

          <Card>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold">Price History</h3>
              <div className="flex gap-1">
                {['1mo', '3mo', '6mo', '1y', '2y'].map(p => (
                  <button
                    key={p}
                    onClick={() => setPeriod(p)}
                    className={`px-2 py-1 rounded text-[10px] font-medium transition-colors ${
                      period === p ? 'bg-[#3b82f6] text-white' : 'text-[#8b8d97] hover:text-white hover:bg-[#252940]'
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
            {histLoading ? <Spinner /> : histData?.data ? (
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={histData.data}>
                  <defs>
                    <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3e" />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: '#8b8d97', fontSize: 9 }}
                    tickFormatter={d => new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    minTickGap={40}
                  />
                  <YAxis tick={{ fill: '#8b8d97', fontSize: 10 }} domain={['auto', 'auto']} />
                  <Tooltip
                    contentStyle={{ background: '#1e2130', border: '1px solid #2a2d3e', borderRadius: 8, fontSize: 11 }}
                    labelFormatter={d => new Date(d).toLocaleDateString()}
                    formatter={(v) => [fmt(v), 'Close']}
                  />
                  <Area type="monotone" dataKey="close" stroke="#3b82f6" fill="url(#colorPrice)" strokeWidth={1.5} dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            ) : <div className="text-[#8b8d97] text-center py-8">No chart data</div>}
          </Card>

          {techLoading ? <Spinner /> : techData && !techData.error && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card>
                <h3 className="text-sm font-semibold mb-4">Technical Indicators</h3>
                <div className="space-y-3">
                  <div>
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-[#8b8d97]">RSI (14)</span>
                      <span className={`font-bold ${
                        techData.rsi < 30 ? 'text-green-400' : techData.rsi > 70 ? 'text-red-400' : 'text-white'
                      }`}>{fmt(techData.rsi, 1)}</span>
                    </div>
                    <div className="h-2 bg-[#0f1117] rounded-full overflow-hidden relative">
                      <div className="absolute inset-0 flex">
                        <div className="w-[30%] bg-green-500/20" />
                        <div className="w-[40%] bg-gray-500/10" />
                        <div className="w-[30%] bg-red-500/20" />
                      </div>
                      <div
                        className="absolute top-0 h-full w-1 bg-white rounded-full"
                        style={{ left: `${Math.min(100, Math.max(0, techData.rsi))}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-[9px] text-[#8b8d97] mt-0.5">
                      <span>Oversold</span><span>Neutral</span><span>Overbought</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-xs">
                    <span className="text-[#8b8d97]">MACD Histogram</span>
                    <span className={`font-bold ${(techData.macd || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {fmt(techData.macd, 4)}
                    </span>
                  </div>

                  <div>
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-[#8b8d97]">Bollinger Band Position</span>
                      <span className="font-bold">{fmt((techData.bbPosition || 0) * 100, 0)}%</span>
                    </div>
                    <div className="h-2 bg-[#0f1117] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500 rounded-full transition-all"
                        style={{ width: `${(techData.bbPosition || 0) * 100}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-[9px] text-[#8b8d97] mt-0.5">
                      <span>Lower Band</span><span>Upper Band</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="text-xs">
                      <span className="text-[#8b8d97]">SMA 50</span>
                      <div className="font-mono font-bold">{fmt(techData.sma50)}</div>
                    </div>
                    <div className="text-xs">
                      <span className="text-[#8b8d97]">SMA 200</span>
                      <div className="font-mono font-bold">{techData.sma200 ? fmt(techData.sma200) : '—'}</div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="text-xs">
                      <span className="text-[#8b8d97]">From 52W High</span>
                      <div className={`font-mono font-bold ${(techData.distFromHigh || 0) < -20 ? 'text-yellow-400' : ''}`}>
                        {fmtPct(techData.distFromHigh)}
                      </div>
                    </div>
                    <div className="text-xs">
                      <span className="text-[#8b8d97]">From 52W Low</span>
                      <div className="font-mono font-bold text-green-400">{fmtPct(techData.distFromLow)}</div>
                    </div>
                  </div>
                </div>
              </Card>

              <Card>
                <h3 className="text-sm font-semibold mb-4">Active Signals</h3>
                {techData.signals?.length > 0 ? (
                  <div className="space-y-2">
                    {techData.signals.map((s, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-2 p-2 rounded-lg"
                        style={{ background: s.bullish ? '#22c55e10' : '#ef444410' }}
                      >
                        <span className={`text-lg ${s.bullish ? 'text-green-400' : 'text-red-400'}`}>
                          {s.bullish ? '\u25B2' : '\u25BC'}
                        </span>
                        <div>
                          <div className="text-xs font-semibold" style={{ color: s.bullish ? '#22c55e' : '#ef4444' }}>
                            {s.type.replace(/_/g, ' ')}
                          </div>
                          <div className="text-[10px] text-[#8b8d97]">{s.message}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-[#8b8d97] text-xs">
                    No active technical signals
                  </div>
                )}
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ─── Reports View ─────────────────────────────────────────

const REPORT_TYPE_META = {
  research:   { label: 'Research',   color: '#a855f7' },
  quick:      { label: 'Quick',      color: '#22c55e' },
  comparison: { label: 'Comparison', color: '#3b82f6' },
  screening:  { label: 'Screening',  color: '#f59e0b' },
  analysis:   { label: 'Analysis',   color: '#8b8d97' },
}

const REPORT_TYPE_ORDER = ['research', 'quick', 'comparison', 'screening', 'analysis']

function ReportsView() {
  const { data, loading, error, refetch } = useReports()
  const [selectedPath, setSelectedPath] = useState(null)
  const [typeFilter, setTypeFilter] = useState(null)
  const [archiving, setArchiving] = useState(null)
  const { data: reportData, loading: reportLoading } = useReport(selectedPath)

  const handleArchive = async (e, path) => {
    e.stopPropagation()
    setArchiving(path)
    try {
      await fetch(`/api/reports/archive?path=${encodeURIComponent(path)}`, { method: 'POST' })
      if (selectedPath === path) setSelectedPath(null)
      refetch()
    } finally {
      setArchiving(null)
    }
  }

  if (loading) return <Spinner />
  if (error) return <div className="text-red-400 p-4">Error: {error}</div>

  const allReports = data?.reports || []
  const filtered = typeFilter ? allReports.filter(r => r.type === typeFilter) : allReports

  // Group by type
  const grouped = {}
  for (const r of filtered) {
    const t = r.type || 'analysis'
    if (!grouped[t]) grouped[t] = []
    grouped[t].push(r)
  }

  // Type counts for filter chips
  const typeCounts = {}
  for (const r of allReports) {
    typeCounts[r.type] = (typeCounts[r.type] || 0) + 1
  }

  return (
    <div className="space-y-4 animate-slide-in">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">Analysis Reports</h2>
        <span className="text-xs text-[#8b8d97]">{allReports.length} reports</span>
      </div>

      {/* Type filter chips */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => setTypeFilter(null)}
          className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
            !typeFilter ? 'bg-[#3b82f6] text-white' : 'bg-[#1e2130] text-[#8b8d97] hover:text-white'
          }`}
        >
          All ({allReports.length})
        </button>
        {REPORT_TYPE_ORDER.filter(t => typeCounts[t]).map(t => {
          const meta = REPORT_TYPE_META[t]
          return (
            <button
              key={t}
              onClick={() => setTypeFilter(typeFilter === t ? null : t)}
              className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors flex items-center gap-1.5 ${
                typeFilter === t ? 'text-white' : 'bg-[#1e2130] text-[#8b8d97] hover:text-white'
              }`}
              style={typeFilter === t ? { background: meta.color } : {}}
            >
              <div className="w-1.5 h-1.5 rounded-full" style={{ background: meta.color }} />
              {meta.label} ({typeCounts[t]})
            </button>
          )
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Grouped sidebar */}
        <div className="lg:col-span-4 space-y-3 max-h-[78vh] overflow-y-auto pr-1">
          {allReports.length === 0 ? (
            <Card>
              <div className="text-center py-8 text-[#8b8d97] text-xs">
                <p>No reports yet.</p>
                <p className="mt-1">Go to Analyze tab to generate one.</p>
              </div>
            </Card>
          ) : REPORT_TYPE_ORDER.filter(t => grouped[t]).map(t => {
            const meta = REPORT_TYPE_META[t]
            const reports = grouped[t]
            return (
              <div key={t}>
                <div className="flex items-center gap-2 mb-1.5 px-1">
                  <div className="w-2 h-2 rounded-full" style={{ background: meta.color }} />
                  <span className="text-[11px] font-semibold" style={{ color: meta.color }}>{meta.label}</span>
                  <span className="text-[10px] text-[#8b8d97]">({reports.length})</span>
                </div>
                <div className="space-y-1">
                  {reports.map(r => (
                    <div
                      key={r.path}
                      onClick={() => setSelectedPath(r.path)}
                      className={`group p-2.5 rounded-lg cursor-pointer transition-colors border ${
                        selectedPath === r.path
                          ? 'bg-[#252940] border-[#3b82f6]'
                          : 'bg-[#1e2130] border-[#2a2d3e] hover:bg-[#252940]'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="text-xs font-semibold truncate">{r.title}</div>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-[10px] text-[#8b8d97]">
                              {new Date(r.modified).toLocaleDateString()}
                            </span>
                            <span className="text-[10px] text-[#8b8d97]">
                              {r.size >= 1024 ? `${(r.size / 1024).toFixed(0)} KB` : `${r.size} B`}
                            </span>
                          </div>
                          {r.tickers?.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-1.5">
                              {r.tickers.map(tk => (
                                <span key={tk} className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-[#0f1117] text-[#8b8d97]">
                                  {tk}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        <button
                          onClick={(e) => handleArchive(e, r.path)}
                          className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-[#0f1117] transition-all text-[#8b8d97] hover:text-red-400 flex-shrink-0"
                          title="Archive report"
                        >
                          {archiving === r.path ? (
                            <div className="w-3 h-3 border border-[#8b8d97] border-t-transparent rounded-full animate-spin" />
                          ) : (
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
                            </svg>
                          )}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>

        {/* Report content */}
        <Card className="lg:col-span-8 max-h-[78vh] overflow-y-auto">
          {!selectedPath ? (
            <div className="text-center py-12 text-[#8b8d97]">
              <p>Select a report from the list to view it.</p>
            </div>
          ) : reportLoading ? (
            <Spinner />
          ) : reportData?.content ? (
            <div className="markdown-report">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {reportData.content}
              </ReactMarkdown>
            </div>
          ) : (
            <div className="text-center py-12 text-[#8b8d97]">Failed to load report.</div>
          )}
        </Card>
      </div>
    </div>
  )
}

// ─── Generate Report View ─────────────────────────────────

const PROFILE_COLORS = {
  quick: '#22c55e',
  full: '#3b82f6',
  deep_dive: '#a855f7',
  comparison: '#f59e0b',
  screening: '#ec4899',
}

function GenerateReportView({ onViewReport }) {
  const { data: profileData, loading: profileLoading } = useProfiles()
  const [ticker, setTicker] = useState('')
  const [selectedProfile, setSelectedProfile] = useState('full')
  const [jobId, setJobId] = useState(null)
  const [jobStatus, setJobStatus] = useState(null)
  const [generating, setGenerating] = useState(false)

  useEffect(() => {
    if (!jobId) return
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/reports/job/${jobId}`)
        const job = await res.json()
        setJobStatus(job)
        if (job.status === 'completed' || job.status === 'failed') {
          clearInterval(interval)
          setGenerating(false)
        }
      } catch {
        // keep polling
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [jobId])

  const handleGenerate = async () => {
    if (!ticker.trim()) return
    setGenerating(true)
    setJobStatus(null)
    try {
      const res = await fetch(`/api/reports/generate?ticker=${encodeURIComponent(ticker.trim().toUpperCase())}&profile=${selectedProfile}`, {
        method: 'POST',
      })
      const data = await res.json()
      if (data.job_id) {
        setJobId(data.job_id)
        setJobStatus({ status: 'queued' })
      } else {
        setJobStatus({ status: 'failed', error: data.detail || 'Unknown error' })
        setGenerating(false)
      }
    } catch (err) {
      setJobStatus({ status: 'failed', error: err.message })
      setGenerating(false)
    }
  }

  const profiles = profileData?.profiles || {}

  return (
    <div className="space-y-6 animate-slide-in">
      <div>
        <h2 className="text-lg font-bold">Generate Analysis Report</h2>
        <p className="text-xs text-[#8b8d97]">
          Enter a ticker and select an analysis profile. The pipeline runs locally using your Python analysis engine.
        </p>
      </div>

      <Card>
        <label className="text-xs text-[#8b8d97] mb-2 block">Ticker Symbol</label>
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="e.g. ASML, HTHIY, TSM, 8035.T"
          className="w-full bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-4 py-2.5 text-sm font-mono focus:outline-none focus:border-[#3b82f6] transition-colors"
          onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
        />
      </Card>

      <div>
        <h3 className="text-sm font-semibold mb-3">Analysis Profile</h3>
        {profileLoading ? <Spinner /> : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
            {Object.entries(profiles).map(([key, p]) => (
              <div
                key={key}
                onClick={() => setSelectedProfile(key)}
                className={`p-3 rounded-lg cursor-pointer transition-all border-2 ${
                  selectedProfile === key
                    ? 'border-[#3b82f6] bg-[#252940]'
                    : 'border-[#2a2d3e] bg-[#1e2130] hover:border-[#3b82f6]/50'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ background: PROFILE_COLORS[key] || '#3b82f6' }} />
                  <span className="text-xs font-semibold capitalize">{key.replace(/_/g, ' ')}</span>
                </div>
                <p className="text-[10px] text-[#8b8d97] line-clamp-2">{p.description}</p>
                <div className="flex flex-wrap gap-1 mt-2">
                  {(p.analyzers === 'all' ? ['all analyzers'] : p.analyzers || []).map(a => (
                    <span key={a} className="px-1.5 py-0.5 rounded text-[9px] bg-[#0f1117] text-[#8b8d97]">{a}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <button
        onClick={handleGenerate}
        disabled={generating || !ticker.trim()}
        className="px-6 py-3 bg-[#3b82f6] text-white text-sm font-medium rounded-lg hover:bg-[#2563eb] disabled:opacity-50 transition-colors"
      >
        {generating ? 'Generating...' : 'Generate Report'}
      </button>

      {jobStatus && (
        <Card>
          {jobStatus.status === 'queued' || jobStatus.status === 'running' ? (
            <div className="flex items-center gap-3">
              <div className="w-5 h-5 border-2 border-[#3b82f6] border-t-transparent rounded-full animate-spin" />
              <div>
                <div className="text-sm font-semibold">
                  {jobStatus.status === 'queued' ? 'Queued...' : 'Running analysis pipeline...'}
                </div>
                <div className="text-[10px] text-[#8b8d97]">
                  This may take 30-120 seconds depending on the profile.
                </div>
              </div>
            </div>
          ) : jobStatus.status === 'completed' ? (
            <div>
              <div className="text-sm font-semibold text-green-400 mb-2">Report generated!</div>
              <button
                onClick={() => onViewReport(jobStatus.report_path)}
                className="px-4 py-2 bg-[#22c55e] text-white text-xs font-medium rounded-lg hover:bg-[#16a34a] transition-colors"
              >
                View Report
              </button>
            </div>
          ) : jobStatus.status === 'failed' ? (
            <div>
              <div className="text-sm font-semibold text-red-400 mb-1">Generation failed</div>
              <pre className="text-[10px] text-[#8b8d97] whitespace-pre-wrap max-h-40 overflow-y-auto bg-[#0f1117] rounded p-2">
                {jobStatus.error}
              </pre>
            </div>
          ) : null}
        </Card>
      )}
    </div>
  )
}

// ─── My Holdings (Full Portfolio Tracker) ──────────────────

const SECTOR_COLORS = [
  '#3b82f6', '#22c55e', '#ef4444', '#eab308', '#a855f7',
  '#06b6d4', '#ec4899', '#f97316', '#64748b', '#14b8a6',
  '#8b5cf6', '#f43f5e',
]

function HoldingsView({ onSelectTicker }) {
  const { data, loading, error, refetch } = useHoldings()
  const { data: tradeData } = useTradeHistory(20)
  const { data: allocData } = useAllocation()
  const { data: moversData } = useMovers()
  const [activeTab, setActiveTab] = useState('overview') // overview | performance | trades
  const [perfPeriod, setPerfPeriod] = useState('3mo')
  const { data: perfData, loading: perfLoading } = usePerformance(perfPeriod)
  const [benchPeriod, setBenchPeriod] = useState('3mo')
  const [benchTicker, setBenchTicker] = useState('SPY')
  const { data: benchData, loading: benchLoading } = useBenchmark(benchPeriod, benchTicker)
  const [sortCol, setSortCol] = useState('market_value')
  const [sortDir, setSortDir] = useState('desc')

  if (loading) return <Spinner />
  if (error) return <div className="text-red-400 p-4">Error: {error}</div>

  const holdings = data?.holdings || []
  const summary = data?.summary || {}
  const trades = tradeData?.trades || []
  const gainers = moversData?.gainers || []
  const losers = moversData?.losers || []
  const sectors = allocData?.sectors || []
  const countries = allocData?.countries || []

  // Sortable holdings
  const handleSort = (col) => {
    if (sortCol === col) setSortDir(sortDir === 'desc' ? 'asc' : 'desc')
    else { setSortCol(col); setSortDir('desc') }
  }
  const sorted = [...holdings].sort((a, b) => {
    const av = a[sortCol] ?? 0, bv = b[sortCol] ?? 0
    return sortDir === 'desc' ? bv - av : av - bv
  })

  // Portfolio weight calculation
  const totalMV = summary.total_market_value || 0

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'performance', label: 'Performance' },
    { id: 'trades', label: 'Trade History' },
  ]

  return (
    <div className="space-y-6 animate-slide-in">
      {/* Hero: Total Value + P&L */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <div className="text-[#8b8d97] text-xs mb-1">Total Portfolio Value</div>
          <div className="text-3xl sm:text-4xl font-bold tracking-tight">
            {summary.total_market_value != null
              ? `$${summary.total_market_value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
              : '—'}
          </div>
          <div className="flex items-center gap-3 mt-1">
            <span className={`text-lg font-semibold ${(summary.total_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {summary.total_pnl != null
                ? `${summary.total_pnl >= 0 ? '+' : ''}$${Math.abs(summary.total_pnl).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
                : ''}
            </span>
            <span className={`text-sm font-medium px-2 py-0.5 rounded-full ${
              (summary.total_pnl_pct || 0) >= 0
                ? 'bg-green-500/15 text-green-400'
                : 'bg-red-500/15 text-red-400'
            }`}>
              {fmtPct(summary.total_pnl_pct)}
            </span>
            <span className="text-xs text-[#8b8d97]">all time</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-[#8b8d97]">{summary.count || 0} positions</span>
          <button
            onClick={refetch}
            className="px-3 py-1.5 rounded-lg text-xs font-medium text-[#8b8d97] hover:text-white hover:bg-[#1e2130] transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card>
          <div className="text-[#8b8d97] text-[10px] mb-1">Total Invested</div>
          <div className="text-lg font-bold">{fmtCurrency(summary.total_invested)}</div>
        </Card>
        <Card>
          <div className="text-[#8b8d97] text-[10px] mb-1">Today's Gainers</div>
          <div className="text-lg font-bold text-green-400">
            {holdings.filter(h => (h.change_pct || 0) > 0).length}
            <span className="text-xs text-[#8b8d97] font-normal ml-1">/ {holdings.length}</span>
          </div>
        </Card>
        <Card>
          <div className="text-[#8b8d97] text-[10px] mb-1">Best Today</div>
          {gainers[0] ? (
            <div className="text-lg font-bold text-green-400 font-mono">
              {gainers[0].ticker} <span className="text-sm">{fmtPct(gainers[0].changePct)}</span>
            </div>
          ) : <div className="text-lg font-bold text-[#8b8d97]">—</div>}
        </Card>
        <Card>
          <div className="text-[#8b8d97] text-[10px] mb-1">Worst Today</div>
          {losers[0] ? (
            <div className="text-lg font-bold text-red-400 font-mono">
              {losers[0].ticker} <span className="text-sm">{fmtPct(losers[0].changePct)}</span>
            </div>
          ) : <div className="text-lg font-bold text-[#8b8d97]">—</div>}
        </Card>
      </div>

      {/* Sub-tabs */}
      <div className="flex items-center gap-1 border-b border-[#2a2d3e] pb-1">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 text-xs font-medium rounded-t-lg transition-colors ${
              activeTab === tab.id
                ? 'bg-[#1e2130] text-white border-b-2 border-[#3b82f6]'
                : 'text-[#8b8d97] hover:text-white'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ═══ OVERVIEW TAB ═══ */}
      {activeTab === 'overview' && (
        <div className="space-y-6 animate-slide-in">
          {/* Holdings Table */}
          <Card className="overflow-x-auto">
            <h3 className="text-sm font-semibold mb-4">Holdings — Live</h3>
            {holdings.length === 0 ? (
              <div className="text-center py-12 text-[#8b8d97]">
                <p className="text-lg mb-2">No Holdings Yet</p>
                <p className="text-xs">Trade SMS messages forwarded via Telegram will automatically update your portfolio here.</p>
              </div>
            ) : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-[#8b8d97] border-b border-[#2a2d3e]">
                    {[
                      { key: 'ticker', label: 'Ticker', align: 'left' },
                      { key: 'name', label: 'Name', align: 'left' },
                      { key: 'quantity', label: 'Shares', align: 'right' },
                      { key: 'avg_cost', label: 'Avg Cost', align: 'right' },
                      { key: 'current_price', label: 'Price', align: 'right' },
                      { key: 'change_pct', label: 'Today', align: 'right' },
                      { key: 'market_value', label: 'Mkt Value', align: 'right' },
                      { key: 'unrealized_pnl', label: 'P&L', align: 'right' },
                      { key: 'unrealized_pct', label: 'Return', align: 'right' },
                      { key: 'weight', label: 'Weight', align: 'right' },
                    ].map(col => (
                      <th
                        key={col.key}
                        className={`py-2 pr-2 cursor-pointer hover:text-white transition-colors select-none ${col.align === 'right' ? 'text-right' : 'text-left'}`}
                        onClick={() => col.key !== 'name' && col.key !== 'weight' && handleSort(col.key)}
                      >
                        {col.label}
                        {sortCol === col.key && <span className="ml-0.5">{sortDir === 'desc' ? '\u25BC' : '\u25B2'}</span>}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sorted.map(h => {
                    const weight = totalMV > 0 && h.market_value ? (h.market_value / totalMV * 100) : 0
                    return (
                      <tr
                        key={h.ticker}
                        className="border-b border-[#2a2d3e]/50 hover:bg-[#252940] transition-colors cursor-pointer"
                        onClick={() => onSelectTicker(h.ticker)}
                      >
                        <td className="py-2 pr-2 font-mono font-semibold">{h.ticker}</td>
                        <td className="py-2 pr-2 text-[#8b8d97] max-w-[140px] truncate">{h.quote_name || h.name}</td>
                        <td className="py-2 pr-2 text-right font-mono">{h.quantity.toLocaleString()}</td>
                        <td className="py-2 pr-2 text-right font-mono">${fmt(h.avg_cost)}</td>
                        <td className="py-2 pr-2 text-right font-mono">{h.current_price ? `$${fmt(h.current_price)}` : '—'}</td>
                        <td className={`py-2 pr-2 text-right font-mono ${(h.change_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {fmtPct(h.change_pct)}
                        </td>
                        <td className="py-2 pr-2 text-right font-mono">{h.market_value ? fmtCurrency(h.market_value) : '—'}</td>
                        <td className={`py-2 pr-2 text-right font-mono ${(h.unrealized_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {h.unrealized_pnl != null ? `${h.unrealized_pnl >= 0 ? '+' : ''}$${Math.abs(h.unrealized_pnl).toLocaleString(undefined, { maximumFractionDigits: 0 })}` : '—'}
                        </td>
                        <td className={`py-2 pr-2 text-right font-mono font-semibold ${(h.unrealized_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {fmtPct(h.unrealized_pct)}
                        </td>
                        <td className="py-2 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <div className="w-12 h-1.5 bg-[#0f1117] rounded-full overflow-hidden">
                              <div className="h-full bg-[#3b82f6] rounded-full" style={{ width: `${Math.min(100, weight)}%` }} />
                            </div>
                            <span className="text-[10px] font-mono text-[#8b8d97] w-8 text-right">{weight.toFixed(1)}%</span>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </Card>

          {/* Allocation Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Sector Allocation */}
            <Card>
              <h3 className="text-sm font-semibold mb-4">Sector Allocation</h3>
              {sectors.length > 0 ? (
                <>
                  <ResponsiveContainer width="100%" height={240}>
                    <PieChart>
                      <Pie
                        data={sectors}
                        cx="50%"
                        cy="50%"
                        innerRadius={55}
                        outerRadius={90}
                        dataKey="value"
                        nameKey="name"
                        label={({ name, pct }) => `${name.split(' ')[0]} ${pct}%`}
                        labelLine={false}
                      >
                        {sectors.map((s, i) => (
                          <Cell key={s.name} fill={SECTOR_COLORS[i % SECTOR_COLORS.length]} stroke="none" />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{ background: '#1e2130', border: '1px solid #2a2d3e', borderRadius: 8, fontSize: 11 }}
                        formatter={(v) => [fmtCurrency(v), 'Value']}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2 justify-center">
                    {sectors.map((s, i) => (
                      <div key={s.name} className="flex items-center gap-1 text-[10px]">
                        <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: SECTOR_COLORS[i % SECTOR_COLORS.length] }} />
                        <span className="text-[#8b8d97]">{s.name}</span>
                        <span className="font-semibold">{s.pct}%</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : <div className="text-center py-8 text-[#8b8d97] text-xs">No allocation data</div>}
            </Card>

            {/* Country Allocation */}
            <Card>
              <h3 className="text-sm font-semibold mb-4">Country Allocation</h3>
              {countries.length > 0 ? (
                <>
                  <ResponsiveContainer width="100%" height={240}>
                    <PieChart>
                      <Pie
                        data={countries}
                        cx="50%"
                        cy="50%"
                        innerRadius={55}
                        outerRadius={90}
                        dataKey="value"
                        nameKey="name"
                        label={({ name, pct }) => `${name} ${pct}%`}
                        labelLine={false}
                      >
                        {countries.map((c, i) => (
                          <Cell key={c.name} fill={SECTOR_COLORS[(i + 3) % SECTOR_COLORS.length]} stroke="none" />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{ background: '#1e2130', border: '1px solid #2a2d3e', borderRadius: 8, fontSize: 11 }}
                        formatter={(v) => [fmtCurrency(v), 'Value']}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2 justify-center">
                    {countries.map((c, i) => (
                      <div key={c.name} className="flex items-center gap-1 text-[10px]">
                        <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: SECTOR_COLORS[(i + 3) % SECTOR_COLORS.length] }} />
                        <span className="text-[#8b8d97]">{c.name}</span>
                        <span className="font-semibold">{c.pct}%</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : <div className="text-center py-8 text-[#8b8d97] text-xs">No allocation data</div>}
            </Card>
          </div>

          {/* Top Movers */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <h3 className="text-sm font-semibold mb-3 text-green-400">Top Gainers Today</h3>
              {gainers.length > 0 ? (
                <div className="space-y-2">
                  {gainers.map(m => (
                    <div
                      key={m.ticker}
                      className="flex items-center justify-between p-2 rounded-lg bg-green-500/5 hover:bg-green-500/10 cursor-pointer transition-colors"
                      onClick={() => onSelectTicker(m.ticker)}
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-semibold text-xs">{m.ticker}</span>
                        <span className="text-[10px] text-[#8b8d97] max-w-[100px] truncate">{m.name}</span>
                      </div>
                      <div className="text-right">
                        <div className="text-xs font-mono font-bold text-green-400">{fmtPct(m.changePct)}</div>
                        <div className="text-[10px] text-[#8b8d97]">${fmt(m.price)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : <div className="text-center py-4 text-[#8b8d97] text-xs">No gainers today</div>}
            </Card>
            <Card>
              <h3 className="text-sm font-semibold mb-3 text-red-400">Top Losers Today</h3>
              {losers.length > 0 ? (
                <div className="space-y-2">
                  {losers.map(m => (
                    <div
                      key={m.ticker}
                      className="flex items-center justify-between p-2 rounded-lg bg-red-500/5 hover:bg-red-500/10 cursor-pointer transition-colors"
                      onClick={() => onSelectTicker(m.ticker)}
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-semibold text-xs">{m.ticker}</span>
                        <span className="text-[10px] text-[#8b8d97] max-w-[100px] truncate">{m.name}</span>
                      </div>
                      <div className="text-right">
                        <div className="text-xs font-mono font-bold text-red-400">{fmtPct(m.changePct)}</div>
                        <div className="text-[10px] text-[#8b8d97]">${fmt(m.price)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : <div className="text-center py-4 text-[#8b8d97] text-xs">No losers today</div>}
            </Card>
          </div>

          {/* P&L bar chart */}
          {holdings.length > 0 && holdings.some(h => h.unrealized_pnl != null) && (
            <Card>
              <h3 className="text-sm font-semibold mb-4">Unrealized P&L by Position</h3>
              <ResponsiveContainer width="100%" height={Math.max(200, sorted.length * 28)}>
                <BarChart data={sorted.filter(h => h.unrealized_pnl != null)} layout="vertical" margin={{ left: 60 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3e" />
                  <XAxis type="number" tick={{ fill: '#8b8d97', fontSize: 10 }} tickFormatter={v => `$${v.toLocaleString()}`} />
                  <YAxis type="category" dataKey="ticker" tick={{ fill: '#e4e5e7', fontSize: 10, fontFamily: 'monospace' }} width={55} />
                  <Tooltip
                    contentStyle={{ background: '#1e2130', border: '1px solid #2a2d3e', borderRadius: 8 }}
                    formatter={(v) => [`$${v.toLocaleString()}`, 'P&L']}
                  />
                  <Bar dataKey="unrealized_pnl" radius={[0, 4, 4, 0]}>
                    {sorted.filter(h => h.unrealized_pnl != null).map((entry) => (
                      <Cell key={entry.ticker} fill={(entry.unrealized_pnl || 0) >= 0 ? '#22c55e' : '#ef4444'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}
        </div>
      )}

      {/* ═══ PERFORMANCE TAB ═══ */}
      {activeTab === 'performance' && (
        <div className="space-y-6 animate-slide-in">
          {/* Portfolio Value Over Time */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold">Portfolio Value Over Time</h3>
              <div className="flex gap-1">
                {['1mo', '3mo', '6mo', '1y'].map(p => (
                  <button
                    key={p}
                    onClick={() => setPerfPeriod(p)}
                    className={`px-2.5 py-1 rounded text-[10px] font-medium transition-colors ${
                      perfPeriod === p ? 'bg-[#3b82f6] text-white' : 'text-[#8b8d97] hover:text-white hover:bg-[#252940]'
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
            {perfLoading ? <Spinner /> : perfData?.data?.length > 0 ? (
              <ResponsiveContainer width="100%" height={320}>
                <AreaChart data={perfData.data}>
                  <defs>
                    <linearGradient id="perfGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={perfData.data[perfData.data.length - 1]?.pnl >= 0 ? '#22c55e' : '#ef4444'} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={perfData.data[perfData.data.length - 1]?.pnl >= 0 ? '#22c55e' : '#ef4444'} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3e" />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: '#8b8d97', fontSize: 9 }}
                    tickFormatter={d => new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    minTickGap={50}
                  />
                  <YAxis
                    tick={{ fill: '#8b8d97', fontSize: 10 }}
                    domain={['auto', 'auto']}
                    tickFormatter={v => `$${(v / 1000).toFixed(0)}k`}
                  />
                  <Tooltip
                    contentStyle={{ background: '#1e2130', border: '1px solid #2a2d3e', borderRadius: 8, fontSize: 11 }}
                    labelFormatter={d => new Date(d).toLocaleDateString()}
                    formatter={(v, name) => {
                      if (name === 'value') return [`$${v.toLocaleString()}`, 'Portfolio Value']
                      return [v, name]
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke={perfData.data[perfData.data.length - 1]?.pnl >= 0 ? '#22c55e' : '#ef4444'}
                    fill="url(#perfGrad)"
                    strokeWidth={2}
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : <div className="text-center py-12 text-[#8b8d97] text-xs">Loading performance data...</div>}

            {/* P&L summary below chart */}
            {perfData?.data?.length > 0 && (
              <div className="grid grid-cols-3 gap-4 mt-4 pt-4 border-t border-[#2a2d3e]">
                <div className="text-center">
                  <div className="text-[10px] text-[#8b8d97]">Period Start</div>
                  <div className="text-sm font-bold font-mono">${(perfData.data[0]?.value / 1000).toFixed(1)}k</div>
                </div>
                <div className="text-center">
                  <div className="text-[10px] text-[#8b8d97]">Current</div>
                  <div className="text-sm font-bold font-mono">${(perfData.data[perfData.data.length - 1]?.value / 1000).toFixed(1)}k</div>
                </div>
                <div className="text-center">
                  <div className="text-[10px] text-[#8b8d97]">Period P&L</div>
                  <div className={`text-sm font-bold ${(perfData.data[perfData.data.length - 1]?.pnlPct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {fmtPct(perfData.data[perfData.data.length - 1]?.pnlPct)}
                  </div>
                </div>
              </div>
            )}
          </Card>

          {/* Benchmark Comparison */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <h3 className="text-sm font-semibold">vs Benchmark</h3>
                <div className="flex gap-1">
                  {['SPY', 'QQQ', 'VOO'].map(b => (
                    <button
                      key={b}
                      onClick={() => setBenchTicker(b)}
                      className={`px-2 py-0.5 rounded text-[10px] font-mono font-medium transition-colors ${
                        benchTicker === b ? 'bg-[#a855f7] text-white' : 'text-[#8b8d97] hover:text-white hover:bg-[#252940]'
                      }`}
                    >
                      {b}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex gap-1">
                {['1mo', '3mo', '6mo', '1y'].map(p => (
                  <button
                    key={p}
                    onClick={() => setBenchPeriod(p)}
                    className={`px-2.5 py-1 rounded text-[10px] font-medium transition-colors ${
                      benchPeriod === p ? 'bg-[#3b82f6] text-white' : 'text-[#8b8d97] hover:text-white hover:bg-[#252940]'
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
            {benchLoading ? <Spinner /> : benchData?.portfolio?.length > 0 ? (
              <>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3e" />
                    <XAxis
                      dataKey="date"
                      data={benchData.benchmark}
                      tick={{ fill: '#8b8d97', fontSize: 9 }}
                      tickFormatter={d => new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                      minTickGap={50}
                    />
                    <YAxis
                      tick={{ fill: '#8b8d97', fontSize: 10 }}
                      tickFormatter={v => `${v}%`}
                    />
                    <Tooltip
                      contentStyle={{ background: '#1e2130', border: '1px solid #2a2d3e', borderRadius: 8, fontSize: 11 }}
                      labelFormatter={d => new Date(d).toLocaleDateString()}
                      formatter={(v) => [`${v.toFixed(2)}%`]}
                    />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line
                      data={benchData.portfolio}
                      type="monotone"
                      dataKey="value"
                      name="My Portfolio"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      data={benchData.benchmark}
                      type="monotone"
                      dataKey="value"
                      name={benchTicker}
                      stroke="#a855f7"
                      strokeWidth={2}
                      dot={false}
                      strokeDasharray="5 5"
                    />
                  </LineChart>
                </ResponsiveContainer>
                {/* Alpha calculation */}
                {benchData.portfolio.length > 0 && benchData.benchmark.length > 0 && (
                  <div className="flex items-center justify-center gap-6 mt-4 pt-4 border-t border-[#2a2d3e]">
                    <div className="text-center">
                      <div className="text-[10px] text-[#8b8d97]">Portfolio Return</div>
                      <div className={`text-sm font-bold ${benchData.portfolio[benchData.portfolio.length - 1]?.value >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {fmtPct(benchData.portfolio[benchData.portfolio.length - 1]?.value)}
                      </div>
                    </div>
                    <div className="text-center">
                      <div className="text-[10px] text-[#8b8d97]">{benchTicker} Return</div>
                      <div className={`text-sm font-bold ${benchData.benchmark[benchData.benchmark.length - 1]?.value >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {fmtPct(benchData.benchmark[benchData.benchmark.length - 1]?.value)}
                      </div>
                    </div>
                    <div className="text-center">
                      <div className="text-[10px] text-[#8b8d97]">Alpha</div>
                      {(() => {
                        const alpha = (benchData.portfolio[benchData.portfolio.length - 1]?.value || 0) -
                          (benchData.benchmark[benchData.benchmark.length - 1]?.value || 0)
                        return (
                          <div className={`text-sm font-bold ${alpha >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {alpha >= 0 ? '+' : ''}{alpha.toFixed(2)}%
                          </div>
                        )
                      })()}
                    </div>
                  </div>
                )}
              </>
            ) : <div className="text-center py-12 text-[#8b8d97] text-xs">Loading benchmark data...</div>}
          </Card>

          {/* Day-by-Day Performance */}
          {holdings.length > 0 && (
            <Card>
              <h3 className="text-sm font-semibold mb-4">Today's Change by Position (%)</h3>
              <ResponsiveContainer width="100%" height={Math.max(200, sorted.length * 26)}>
                <BarChart
                  data={[...holdings].sort((a, b) => (b.change_pct || 0) - (a.change_pct || 0)).filter(h => h.change_pct != null)}
                  layout="vertical"
                  margin={{ left: 60 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3e" />
                  <XAxis type="number" tick={{ fill: '#8b8d97', fontSize: 10 }} tickFormatter={v => `${v}%`} />
                  <YAxis type="category" dataKey="ticker" tick={{ fill: '#e4e5e7', fontSize: 10, fontFamily: 'monospace' }} width={55} />
                  <Tooltip
                    contentStyle={{ background: '#1e2130', border: '1px solid #2a2d3e', borderRadius: 8 }}
                    formatter={(v) => [`${v}%`, 'Change']}
                  />
                  <Bar dataKey="change_pct" radius={[0, 4, 4, 0]}>
                    {[...holdings].sort((a, b) => (b.change_pct || 0) - (a.change_pct || 0)).filter(h => h.change_pct != null).map((entry) => (
                      <Cell key={entry.ticker} fill={(entry.change_pct || 0) >= 0 ? '#22c55e' : '#ef4444'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}
        </div>
      )}

      {/* ═══ TRADES TAB ═══ */}
      {activeTab === 'trades' && (
        <Card className="animate-slide-in">
          <h3 className="text-sm font-semibold mb-4">Trade History</h3>
          {trades.length === 0 ? (
            <div className="text-center py-12 text-[#8b8d97]">
              <p className="text-lg mb-2">No Trades Recorded</p>
              <p className="text-xs">Trade SMS messages forwarded via Telegram will automatically appear here.</p>
            </div>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-[#8b8d97] border-b border-[#2a2d3e]">
                  <th className="text-left py-2 pr-2">Date</th>
                  <th className="text-left py-2 pr-2">Action</th>
                  <th className="text-left py-2 pr-2">Ticker</th>
                  <th className="text-left py-2 pr-2">Name</th>
                  <th className="text-right py-2 pr-2">Shares</th>
                  <th className="text-right py-2 pr-2">Price</th>
                  <th className="text-right py-2">Total</th>
                </tr>
              </thead>
              <tbody>
                {trades.map(t => (
                  <tr key={t.id} className="border-b border-[#2a2d3e]/50 hover:bg-[#252940] transition-colors">
                    <td className="py-2 pr-2 text-[#8b8d97]">{new Date(t.timestamp).toLocaleDateString()}</td>
                    <td className="py-2 pr-2">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                        t.action === 'BUY' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                      }`}>
                        {t.action}
                      </span>
                    </td>
                    <td className="py-2 pr-2 font-mono font-semibold">{t.ticker}</td>
                    <td className="py-2 pr-2 text-[#8b8d97] max-w-[140px] truncate">{t.name}</td>
                    <td className="py-2 pr-2 text-right font-mono">{t.quantity.toLocaleString()}</td>
                    <td className="py-2 pr-2 text-right font-mono">${fmt(t.price)}</td>
                    <td className="py-2 text-right font-mono">{fmtCurrency(t.total_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}
    </div>
  )
}

// ─── Main App ──────────────────────────────────────────────

export default function App() {
  const { data: domainsData } = useDomains()
  const domains = domainsData?.domains || []

  // Auto-select first domain on load
  const [activeDomain, setActiveDomain] = useState(null)
  const [activeView, setActiveView] = useState('portfolio')
  const [selectedTicker, setSelectedTicker] = useState(null)
  const [selectedReportPath, setSelectedReportPath] = useState(null)
  const { data: alertData } = useAlerts()

  // Fetch domain meta when activeDomain changes
  const { data: domainMeta } = useDomainMeta(activeDomain)

  // Auto-select first domain when domains load
  useEffect(() => {
    if (domains.length > 0 && !activeDomain) {
      setActiveDomain(domains[0].id)
    }
  }, [domains, activeDomain])

  // When switching to a domain view without a domain, select the first one
  const handleSetActiveView = useCallback((view) => {
    const domainViews = ['portfolio', 'universe', 'heatmap']
    if (domainViews.includes(view) && !activeDomain && domains.length > 0) {
      setActiveDomain(domains[0].id)
    }
    setActiveView(view)
  }, [activeDomain, domains])

  const handleSelectTicker = useCallback((ticker) => {
    setSelectedTicker(ticker)
    setActiveView('detail')
  }, [])

  const handleViewReport = useCallback((reportPath) => {
    setSelectedReportPath(reportPath)
    setActiveView('reports')
  }, [])

  const alertCount = alertData?.alerts?.length || 0
  const isDomainView = ['portfolio', 'universe', 'heatmap'].includes(activeView)

  return (
    <div className="min-h-screen">
      <Nav
        activeDomain={activeDomain}
        setActiveDomain={setActiveDomain}
        activeView={activeView}
        setActiveView={handleSetActiveView}
        alertCount={alertCount}
        domains={domains}
        domainMeta={domainMeta}
      />
      <main className="max-w-[1600px] mx-auto px-4 sm:px-6 py-6">
        {activeView === 'portfolio' && activeDomain && (
          <PortfolioView domainId={activeDomain} />
        )}
        {activeView === 'universe' && activeDomain && (
          <UniverseView domainId={activeDomain} domainMeta={domainMeta} onSelectTicker={handleSelectTicker} />
        )}
        {activeView === 'heatmap' && activeDomain && (
          <HeatmapView domainId={activeDomain} domainMeta={domainMeta} onSelectTicker={handleSelectTicker} />
        )}
        {activeView === 'holdings' && (
          <HoldingsView onSelectTicker={handleSelectTicker} />
        )}
        {activeView === 'alerts' && (
          <AlertsView onSelectTicker={handleSelectTicker} domains={domains} />
        )}
        {activeView === 'detail' && (
          <StockDetailView ticker={selectedTicker} setTicker={setSelectedTicker} />
        )}
        {activeView === 'generate' && <GenerateReportView onViewReport={handleViewReport} />}
        {activeView === 'reports' && <ReportsView />}

        {/* Show empty state if domain view but no domain */}
        {isDomainView && !activeDomain && (
          <Card>
            <div className="text-center py-12 text-[#8b8d97]">
              <p className="text-lg mb-2">No Domain Selected</p>
              <p>Select a domain from the dropdown in the navigation bar.</p>
            </div>
          </Card>
        )}
      </main>
      <footer className="text-center text-[10px] text-[#8b8d97] py-4 border-t border-[#2a2d3e]">
        FE-Analyst Dashboard v3.0 — Multi-domain — Not financial advice
      </footer>
    </div>
  )
}

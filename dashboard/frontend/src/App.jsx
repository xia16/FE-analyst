import React, { useState, useEffect, useCallback } from 'react'
import {
  useDomains, useDomainMeta, useDomainWatchlist, useDomainUniverse, useDomainHeatmap,
  useAlerts, useHistory,
} from './hooks'
import {
  AreaChart, Area, BarChart, Bar, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, PieChart, Pie, Legend,
} from 'recharts'

import { Card, Badge, Spinner, fmt, fmtPct, fmtCurrency, RATING_COLORS, DEFAULT_TIER_COLOR } from './components/shared'
import Nav from './components/Nav'
import MyPortfolioView from './views/MyPortfolioView'
import StockDetailView from './views/StockDetailView'
import { ReportsView, GenerateReportView } from './views/ReportsView'

// ─── Watchlist Dashboard (was PortfolioView) ──────────────

function WatchlistView({ domainId, onSelectTicker }) {
  const { data, loading, error } = useDomainWatchlist(domainId)

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
          <h3 className="text-sm font-semibold mb-4">Recommended Allocation</h3>
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
              <Tooltip formatter={(v) => `${v}%`} contentStyle={{ background: '#1a1d2e', border: '1px solid rgba(59,130,246,0.3)', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.4)' }} />
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
          <h3 className="text-sm font-semibold mb-4">Tracked Positions — Live</h3>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[#a0a2ab] border-b border-[#2a2d3e] bg-[#0f1117]/40 text-[10px] uppercase tracking-wider">
                <th className="text-left py-2.5 pr-2 font-semibold">Ticker</th>
                <th className="text-left py-2.5 pr-2 font-semibold">Name</th>
                <th className="text-right py-2.5 pr-2 font-semibold">Price</th>
                <th className="text-right py-2.5 pr-2 font-semibold">Change</th>
                <th className="text-right py-2.5 pr-2 font-semibold">Mkt Cap</th>
                <th className="text-right py-2.5 pr-2 font-semibold">Fwd P/E</th>
                <th className="text-center py-2.5 pr-2 font-semibold">Rating</th>
                <th className="text-right py-2.5 font-semibold">Alloc</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(p => (
                <tr key={p.ticker} className="border-b border-[#2a2d3e]/50 hover:bg-[#1a1f2e] transition-colors cursor-pointer" onClick={() => onSelectTicker && onSelectTicker(p.ticker)}>
                  <td className="py-2 pr-2 font-mono font-semibold text-blue-400">{p.ticker}</td>
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
        <h3 className="text-sm font-semibold mb-4">Today's Performance</h3>
        <ResponsiveContainer width="100%" height={Math.max(240, sorted.length * 26)}>
          <BarChart data={sorted} layout="vertical" margin={{ left: 55, right: 20 }} barCategoryGap="20%">
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3e" horizontal={false} />
            <XAxis type="number" tick={{ fill: '#8b8d97', fontSize: 10 }} tickFormatter={v => `${v}%`} axisLine={{ stroke: '#2a2d3e' }} />
            <YAxis type="category" dataKey="ticker" tick={{ fill: '#e4e5e7', fontSize: 10, fontFamily: 'monospace' }} width={50} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{ background: '#1a1d2e', border: '1px solid rgba(59,130,246,0.3)', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.4)' }}
              formatter={(v) => [`${v}%`, 'Change']}
              cursor={{ fill: 'rgba(255,255,255,0.03)' }}
            />
            <Bar dataKey="changePct" radius={[0, 3, 3, 0]} maxBarSize={18}>
              {sorted.map((entry) => (
                <Cell key={entry.ticker} fill={(entry.changePct || 0) >= 0 ? '#22c55e' : '#ef4444'} fillOpacity={0.85} />
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
                        <span className="text-[9px] text-[#8b8d97] w-20 sm:w-24 truncate">{dimensions[k]?.label || k}</span>
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
        <ResponsiveContainer width="100%" height={280}>
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
            <Tooltip contentStyle={{ background: '#1a1d2e', border: '1px solid rgba(59,130,246,0.3)', borderRadius: 8, fontSize: 11, boxShadow: '0 4px 12px rgba(0,0,0,0.4)' }} />
          </RadarChart>
        </ResponsiveContainer>
      </Card>

      <Card className="overflow-x-auto">
        <h3 className="text-sm font-semibold mb-4">Full Heatmap — {heatmapData.length} Companies</h3>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-[#a0a2ab] border-b border-[#2a2d3e] bg-[#0f1117]/40 text-[10px] uppercase tracking-wider">
              <th className="text-left py-2.5 pr-2 font-semibold">#</th>
              <th className="text-left py-2.5 pr-2 font-semibold">Ticker</th>
              <th className="text-left py-2.5 pr-2 font-semibold">Name</th>
              <th className="text-center py-2.5 pr-2 font-semibold">Tier</th>
              <th className="text-center py-2.5 pr-2 font-semibold">Category</th>
              {dimKeys.map(d => (
                <th key={d} className="text-center py-2.5 px-1 font-semibold">{dimLabels[d]}</th>
              ))}
              <th className="text-center py-2.5 pl-2 font-bold">Composite</th>
            </tr>
          </thead>
          <tbody>
            {heatmapData.map((c, i) => (
              <tr
                key={c.ticker}
                className="border-b border-[#2a2d3e]/30 hover:bg-[#1a1f2e] transition-colors cursor-pointer"
                onClick={() => onSelectTicker(c.ticker)}
              >
                <td className="py-1.5 pr-2 text-[#8b8d97]">{i + 1}</td>
                <td className="py-1.5 pr-2 font-mono font-semibold">{c.ticker}</td>
                <td className="py-1.5 pr-2 text-[#8b8d97] max-w-[80px] md:max-w-[140px] truncate">{c.name}</td>
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

// ─── Main App ──────────────────────────────────────────────

export default function App() {
  const { data: domainsData } = useDomains()
  const domains = domainsData?.domains || []

  const [activeDomain, setActiveDomain] = useState(null)
  const [activeView, setActiveView] = useState('myportfolio')
  const [selectedTicker, setSelectedTicker] = useState(null)
  const [selectedReportPath, setSelectedReportPath] = useState(null)
  const { data: alertData } = useAlerts()

  const { data: domainMeta } = useDomainMeta(activeDomain)

  // Auto-select first domain when entering a research view (not on initial load)
  const handleSetActiveView = useCallback((view) => {
    const domainViews = ['watchlist', 'universe', 'heatmap']
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
  const isDomainView = ['watchlist', 'universe', 'heatmap'].includes(activeView)

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
        {activeView === 'myportfolio' && (
          <MyPortfolioView onSelectTicker={handleSelectTicker} />
        )}
        {activeView === 'watchlist' && activeDomain && (
          <WatchlistView domainId={activeDomain} onSelectTicker={handleSelectTicker} />
        )}
        {activeView === 'universe' && activeDomain && (
          <UniverseView domainId={activeDomain} domainMeta={domainMeta} onSelectTicker={handleSelectTicker} />
        )}
        {activeView === 'heatmap' && activeDomain && (
          <HeatmapView domainId={activeDomain} domainMeta={domainMeta} onSelectTicker={handleSelectTicker} />
        )}
        {activeView === 'alerts' && (
          <AlertsView onSelectTicker={handleSelectTicker} domains={domains} />
        )}
        {activeView === 'detail' && (
          <StockDetailView ticker={selectedTicker} setTicker={setSelectedTicker} />
        )}
        {activeView === 'generate' && <GenerateReportView onViewReport={handleViewReport} />}
        {activeView === 'reports' && <ReportsView initialPath={selectedReportPath} />}

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
        FE-Analyst Dashboard v3.1 — Not financial advice
      </footer>
    </div>
  )
}

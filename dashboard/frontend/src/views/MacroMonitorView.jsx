import React, { useState, useEffect, useCallback } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { Card, Spinner } from '../components/shared'

// AI Bubble / Liquidity Monitor — tracks the five liquidity & momentum
// indicators from the "AI bubble mechanics" thesis. Percentile-scored
// (auto-recalibrating); the creator's absolute thresholds appear as dashed
// reference lines, not primary triggers.

const STATUS = {
  red:         { color: '#dc2626', bg: 'rgba(220,38,38,0.12)',  label: 'RED' },
  yellow:      { color: '#d97706', bg: 'rgba(217,119,6,0.12)',  label: 'YELLOW' },
  normal:      { color: '#16a34a', bg: 'rgba(22,163,74,0.10)',  label: 'NORMAL' },
  unavailable: { color: '#6b7280', bg: 'rgba(107,114,128,0.10)', label: 'NO DATA' },
}

// Which metrics to render a chart for, and how to interpret the reference lines.
const METRIC_ORDER = [
  'reserves', 'sofr_iorb_spread', 'tga', 'on_rrp',
  'srf_usage', 'cloud_capex_accel', 'options_skew',
]

function Gauge({ percentile, color }) {
  // Trailing-window percentile as a horizontal bar (0–100).
  const pct = percentile == null ? 0 : percentile
  return (
    <div className="mt-2">
      <div className="flex justify-between text-[10px] text-[#8b8d97] mb-1">
        <span>trailing pctile</span>
        <span className="font-mono">{percentile == null ? '—' : `${percentile.toFixed(0)}th`}</span>
      </div>
      <div className="h-1.5 rounded-full bg-[#2a2d3e] overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  )
}

function SellBadge({ sell, active }) {
  if (!sell) return null
  const high = sell.priority === 'high'
  const cls = active
    ? 'bg-red-600 text-white'
    : high
      ? 'text-red-400 border border-red-500/50'
      : 'text-amber-400 border border-amber-500/40'
  const text = active ? '⚑ SELL NOW' : (high ? '⚑ SELL-NOW TRIGGER' : 'SELL-CONFIRM')
  return (
    <div className="mt-2" title={`${sell.when} → ${sell.action}`}>
      <span className={`inline-flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded ${cls} ${active ? 'animate-pulse' : ''}`}>
        {text}
      </span>
    </div>
  )
}

function MetricCard({ m, selected, onClick }) {
  const ctx = m.context_only
  const s = ctx ? STATUS.unavailable : (STATUS[m.status] || STATUS.unavailable)
  const chip = ctx ? 'CONTEXT' : s.label
  const ring = m.sell_active ? '#dc2626' : (selected ? s.color : null)
  return (
    <Card
      onClick={onClick}
      className="cursor-pointer transition-all"
      style={ring ? { boxShadow: `0 0 0 2px ${ring}` } : {}}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="text-xs text-[#a0a2ab] leading-tight">{m.label}</div>
        <span
          className="text-[9px] font-bold px-1.5 py-0.5 rounded whitespace-nowrap"
          style={{ color: s.color, background: s.bg }}
        >
          {chip}
        </span>
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-2xl font-bold" style={{ color: s.color }}>
          {m.display_value ?? '—'}
        </span>
        {m.stale && <span className="text-[9px] text-[#d97706]">stale</span>}
      </div>
      <Gauge percentile={m.percentile} color={s.color} />
      {m.as_of_quarter && (
        <div className="mt-2 text-[9px] text-[#6b7280] leading-relaxed">
          latest <span className="text-[#a0a2ab]">{m.as_of_quarter}</span>
          {m.as_of_filed && <> · filed {m.as_of_filed}</>}
          {m.next_expected && <> · next ~{m.next_expected}</>}
        </div>
      )}
      <SellBadge sell={m.sell_signal} active={m.sell_active} />
    </Card>
  )
}

function SellNowBanner({ snap }) {
  if (!snap.sell_now) return null
  const reasons = snap.sell_reasons || []
  return (
    <Card style={{ borderColor: '#dc2626', borderWidth: 2, background: 'rgba(220,38,38,0.08)' }}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-red-500 text-lg animate-pulse">⚑</span>
        <span className="text-sm font-bold text-red-400 uppercase tracking-wide">Sell-now signal active</span>
      </div>
      {reasons.length > 0 ? (
        <ul className="space-y-1">
          {reasons.map(r => (
            <li key={r.key} className="text-xs text-[#e5e7eb]">
              <span className="font-semibold text-red-400">{r.label}</span> — {r.action}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-[#e5e7eb]">Confluence reached a structural-top (red) state — clear positions.</p>
      )}
    </Card>
  )
}

function ConfluenceBanner({ conf }) {
  if (!conf) return null
  const s = STATUS[conf.level] || STATUS.normal
  const Row = ({ c }) => (
    <div className="flex items-center gap-2 text-xs py-0.5">
      <span className="w-4 font-bold" style={{ color: c.met ? s.color : '#6b7280' }}>
        {c.met ? '✓' : '○'}
      </span>
      <span className="flex-1 text-[#d1d5db]">{c.label}</span>
      <span className="text-[#8b8d97] font-mono text-[11px]">{c.detail}</span>
    </div>
  )
  return (
    <Card style={{ borderColor: s.color, borderWidth: 1 }}>
      <div className="flex items-center gap-3 mb-1">
        <span className="text-sm font-bold uppercase tracking-wide" style={{ color: s.color }}>
          Confluence · {conf.level}
        </span>
      </div>
      <p className="text-xs text-[#a0a2ab] mb-3">{conf.headline}</p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-x-6 gap-y-1">
        <div>
          <div className="text-[10px] uppercase text-[#8b8d97] mb-1">Yellow combo (all)</div>
          {conf.yellow?.map((c, i) => <Row key={i} c={c} />)}
        </div>
        <div>
          <div className="text-[10px] uppercase text-[#8b8d97] mb-1">Red combo (any)</div>
          {conf.red?.map((c, i) => <Row key={i} c={c} />)}
        </div>
        <div>
          <div className="text-[10px] uppercase text-[#8b8d97] mb-1">Top resonance</div>
          {conf.top?.map((c, i) => <Row key={i} c={c} />)}
        </div>
      </div>
    </Card>
  )
}

function TopModelPanel({ snap }) {
  const tm = snap.top_model || []
  if (!tm.length) return null
  const fmtVal = (t) => {
    if (t.value == null) return '—'
    if (t.unit === 'percent' || t.unit === 'percent_ratio') return `${t.value.toFixed(1)}%`
    return `${t.value}`
  }
  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold">Secondary Top-Model Checklist</h3>
        <span className="text-xs text-[#8b8d97]">
          {snap.top_model_triggered}/{snap.top_model_total} triggered
        </span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {tm.map((t) => (
          <div key={t.key} className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-[#0f1117]/50 border border-[#2a2d3e]">
            <span className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                  style={{ background: t.triggered ? STATUS.red.color : STATUS.normal.color }} />
            <div className="flex-1 min-w-0">
              <div className="text-xs text-[#d1d5db] truncate">{t.label}</div>
              <div className="text-[10px] text-[#6b7280]">
                {t.as_of ? `as-of ${t.as_of}` : 'live'}{t.next_expected ? ` · next ~${t.next_expected}` : ''}
              </div>
            </div>
            <span className="text-sm font-mono font-semibold">{fmtVal(t)}</span>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-[#8b8d97] mt-3 leading-relaxed">
        Fully automated (FRED + State Street SPY holdings) — each with its own as-of date. The video's
        other four (margin debt, SPX 0DTE share, insider ratio, Nasdaq-100 fwd P/E) are omitted — no
        reliable free feed, and nothing here is hand-maintained.
      </p>
    </Card>
  )
}

function MetricChart({ metricKey, meta }) {
  const [series, setSeries] = useState(null)

  useEffect(() => {
    let active = true
    fetch(`/api/macro/series/${metricKey}`)
      .then(r => r.json())
      .then(d => { if (active) setSeries(d.series || []) })
      .catch(() => { if (active) setSeries([]) })
    return () => { active = false }
  }, [metricKey])

  if (series == null) return <Spinner />
  if (!series.length) return <div className="text-[#8b8d97] text-sm py-8 text-center">No stored history yet — run a refresh.</div>

  // Reference lines: convert config thresholds into chart units.
  const refs = []
  const toUnit = (v) => {
    if (v == null) return null
    if (meta.unit === 'usd_millions') return v      // series already in millions
    if (meta.unit === 'basis_points') return v
    return v
  }
  if (meta.reference_yellow != null) refs.push({ y: toUnit(meta.reference_yellow), color: '#d97706', label: 'yellow' })
  if (meta.reference_red != null) refs.push({ y: toUnit(meta.reference_red), color: '#dc2626', label: 'red' })

  const s = STATUS[meta.status] || STATUS.unavailable
  const data = series.map(p => ({ date: p.date, value: p.value }))

  return (
    <div>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={`grad-${metricKey}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={s.color} stopOpacity={0.35} />
              <stop offset="100%" stopColor={s.color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3e" />
          <XAxis dataKey="date" tick={{ fill: '#8b8d97', fontSize: 10 }} minTickGap={40} />
          <YAxis tick={{ fill: '#8b8d97', fontSize: 10 }} width={56}
                 tickFormatter={(v) => meta.unit === 'usd_millions' ? `${(v / 1e6).toFixed(1)}T` : v} />
          <Tooltip
            contentStyle={{ background: '#1a1d2e', border: '1px solid rgba(59,130,246,0.3)', borderRadius: 8 }}
            labelStyle={{ color: '#a0a2ab' }}
          />
          {refs.map((r, i) => (
            <ReferenceLine key={i} y={r.y} stroke={r.color} strokeDasharray="5 4" strokeOpacity={0.7}
              label={{ value: r.label, fill: r.color, fontSize: 10, position: 'insideTopRight' }} />
          ))}
          <Area type="monotone" dataKey="value" stroke={s.color} strokeWidth={2}
                fill={`url(#grad-${metricKey})`} />
        </AreaChart>
      </ResponsiveContainer>
      <p className="text-xs text-[#8b8d97] mt-3 leading-relaxed">{meta.note}</p>
    </div>
  )
}

export default function MacroMonitorView() {
  const [snap, setSnap] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [selected, setSelected] = useState('reserves')

  const load = useCallback(() => {
    setLoading(true)
    fetch('/api/macro/monitor')
      .then(r => r.json())
      .then(d => { setSnap(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const refresh = async () => {
    setRefreshing(true)
    try {
      const res = await fetch('/api/macro/refresh', { method: 'POST' })
      const d = await res.json()
      setSnap(d)
    } catch (e) { /* ignore */ }
    setRefreshing(false)
  }

  if (loading) return <Spinner />
  if (!snap?.metrics) return <div className="text-red-400 p-4">Failed to load monitor.</div>

  const overall = STATUS[snap.overall_status] || STATUS.unavailable
  const metrics = snap.metrics
  const selectedMeta = metrics[selected]
  const generated = snap.generated_at ? new Date(snap.generated_at).toLocaleString() : '—'

  return (
    <div className="space-y-6 animate-slide-in">
      {/* Header / overall status */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-lg font-bold flex items-center gap-3">
            AI Bubble Monitor
            <span className="text-xs font-bold px-2 py-1 rounded" style={{ color: overall.color, background: overall.bg }}>
              {overall.label}
            </span>
          </h2>
          <p className="text-xs text-[#8b8d97] mt-1">
            Overall follows the creator's confluence logic · updated {generated}
          </p>
        </div>
        <button
          onClick={refresh}
          disabled={refreshing}
          className="px-4 py-2 rounded-lg text-xs font-semibold bg-[#3b82f6] hover:bg-[#2563eb] disabled:opacity-50 transition-colors"
        >
          {refreshing ? 'Refreshing…' : 'Refresh now'}
        </button>
      </div>

      {/* AI daily note (DeepSeek) */}
      {snap.ai_commentary && (
        <Card style={{ borderLeft: '3px solid #6366f1' }}>
          <div className="text-[11px] font-bold uppercase tracking-wide text-indigo-300 mb-1.5">
            🤖 AI daily note
          </div>
          <p className="text-sm text-[#d1d5db] leading-relaxed">{snap.ai_commentary}</p>
        </Card>
      )}

      {/* High-priority SELL-NOW banner (only when a sell trigger is active) */}
      <SellNowBanner snap={snap} />

      {/* Confluence banner — the creator's actual combo alert logic */}
      <ConfluenceBanner conf={snap.confluence} />

      {/* Metric cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {METRIC_ORDER.filter(k => metrics[k]).map(k => (
          <MetricCard key={k} m={metrics[k]} selected={selected === k} onClick={() => setSelected(k)} />
        ))}
      </div>

      {/* Selected metric chart */}
      {selectedMeta && (
        <Card>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold">{selectedMeta.label}</h3>
            <div className="text-xs text-[#8b8d97]">
              current <span className="font-mono text-white">{selectedMeta.display_value}</span>
              {selectedMeta.percentile != null && <> · {selectedMeta.percentile.toFixed(0)}th pctile</>}
            </div>
          </div>
          <MetricChart metricKey={selected} meta={selectedMeta} />
        </Card>
      )}

      {/* Secondary top-model checklist */}
      <TopModelPanel snap={snap} />

      <p className="text-[10px] text-[#8b8d97] text-center">
        <span className="text-red-400 font-semibold">⚑ SELL-NOW TRIGGER</span> = his immediate-liquidation signals ·{' '}
        <span className="text-amber-400 font-semibold">SELL-CONFIRM</span> = structural-top confirmation. Dashed lines = static thesis thresholds.
        Monitoring only — not financial advice.
      </p>
    </div>
  )
}

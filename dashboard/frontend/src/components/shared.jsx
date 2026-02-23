// ─── Shared Components & Utilities ──────────────────────────

export const fmt = (n, decimals = 2) => n == null ? '—' : Number(n).toFixed(decimals)
export const fmtPct = (n) => n == null ? '—' : `${n >= 0 ? '+' : ''}${Number(n).toFixed(2)}%`
export const fmtCurrency = (n) => {
  if (n == null) return '—'
  if (n >= 1e12) return `$${(n / 1e12).toFixed(1)}T`
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`
  return `$${n.toLocaleString()}`
}

export const RATING_COLORS = {
  'STRONG BUY': '#22c55e',
  'BUY': '#4ade80',
  'HOLD': '#eab308',
  'AVOID': '#ef4444',
}

export const DEFAULT_TIER_COLOR = '#3b82f6'

export const SECTOR_COLORS = [
  '#3b82f6', '#22c55e', '#ef4444', '#eab308', '#a855f7',
  '#06b6d4', '#ec4899', '#f97316', '#64748b', '#14b8a6',
  '#8b5cf6', '#f43f5e',
]

export function Card({ children, className = '', onClick, style }) {
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

export function Badge({ children, color = '#3b82f6' }) {
  return (
    <span
      className="px-2 py-0.5 rounded-full text-xs font-medium"
      style={{ background: `${color}20`, color }}
    >
      {children}
    </span>
  )
}

export function Spinner() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="w-8 h-8 border-2 border-[#3b82f6] border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

// ─── Analysis-specific utilities ─────────────────────────

export const SIGNAL_COLORS = {
  BULLISH: '#22c55e',
  BEARISH: '#ef4444',
  NEUTRAL: '#eab308',
}

export const RECOMMENDATION_COLORS = {
  'STRONG BUY': '#22c55e',
  'BUY': '#4ade80',
  'HOLD': '#eab308',
  'SELL': '#f97316',
  'STRONG SELL': '#ef4444',
}

export function getScoreColor(score) {
  if (score >= 75) return '#22c55e'
  if (score >= 60) return '#4ade80'
  if (score >= 45) return '#eab308'
  if (score >= 30) return '#f97316'
  return '#ef4444'
}

export function ScoreBar({ label, score, max = 100 }) {
  const pct = Math.min(100, Math.max(0, (score / max) * 100))
  const color = getScoreColor(score)
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="text-[#8b8d97]">{label}</span>
        <span className="font-bold font-mono" style={{ color }}>{fmt(score, 1)}</span>
      </div>
      <div className="h-2 bg-[#0f1117] rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  )
}

export function StatusBadge({ status }) {
  const colors = {
    completed: '#22c55e',
    running: '#3b82f6',
    pending: '#eab308',
    failed: '#ef4444',
    none: '#8b8d97',
  }
  const color = colors[status] || '#8b8d97'
  return <Badge color={color}>{status}</Badge>
}

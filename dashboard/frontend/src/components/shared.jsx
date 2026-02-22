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

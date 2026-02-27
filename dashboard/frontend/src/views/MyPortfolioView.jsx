import React, { useState, useCallback } from 'react'
import {
  useHoldings, useTradeHistory, useAllocation, usePerformance, useBenchmark, useMovers, useRealizedPnl,
} from '../hooks'
import { Card, Spinner, fmt, fmtPct, fmtCurrency, SECTOR_COLORS } from '../components/shared'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, PieChart, Pie, LineChart, Line, Legend,
} from 'recharts'

// ─── Custom chart components ────────────────────────────────

const ChartTooltip = ({ children }) => (
  <div className="bg-[#1a1d2e] border border-[#3b82f6]/30 rounded-lg px-3 py-2 shadow-xl shadow-black/40 text-xs">
    {children}
  </div>
)

const PieTooltipContent = ({ active, payload }) => {
  if (!active || !payload?.[0]) return null
  const d = payload[0].payload
  return (
    <ChartTooltip>
      <div className="flex items-center gap-2 mb-1">
        <div className="w-2.5 h-2.5 rounded-full" style={{ background: payload[0].payload.fill || payload[0].color }} />
        <span className="font-semibold text-white">{d.name}</span>
      </div>
      <div className="text-[#8b8d97]">
        {fmtCurrency(d.value)} &middot; <span className="text-white font-medium">{d.pct}%</span>
      </div>
    </ChartTooltip>
  )
}

const BarTooltipContent = ({ active, payload, label, valuePrefix = '$', valueSuffix = '' }) => {
  if (!active || !payload?.[0]) return null
  const v = payload[0].value
  const isPos = v >= 0
  return (
    <ChartTooltip>
      <div className="font-mono font-semibold text-white mb-0.5">{label}</div>
      <div className={isPos ? 'text-green-400' : 'text-red-400'}>
        {isPos ? '+' : ''}{valuePrefix}{Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}{valueSuffix}
      </div>
    </ChartTooltip>
  )
}

// Custom pie label that only shows for slices > threshold
const renderPieLabel = ({ name, pct, cx, cy, midAngle, innerRadius, outerRadius }) => {
  if (pct < 4) return null // skip labels for small slices
  const RADIAN = Math.PI / 180
  const radius = outerRadius + 18
  const x = cx + radius * Math.cos(-midAngle * RADIAN)
  const y = cy + radius * Math.sin(-midAngle * RADIAN)
  return (
    <text x={x} y={y} fill="#e4e5e7" fontSize={10} fontWeight={600}
      textAnchor={x > cx ? 'start' : 'end'} dominantBaseline="central">
      {name.length > 12 ? name.split(' ')[0] : name} {pct}%
    </text>
  )
}

// SHA-256 hash of the unlock password
const UNLOCK_HASH = '4a1fbc000b185c7646f9ecce96ac62cc65797b9472a82893b668d7a86408574b'

async function sha256(text) {
  const data = new TextEncoder().encode(text)
  const hashBuffer = await crypto.subtle.digest('SHA-256', data)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
}

// Mask currency values when locked
const mask = (locked) => locked ? '$\u2022\u2022\u2022\u2022\u2022' : null
const maskNum = (locked) => locked ? '\u2022\u2022\u2022\u2022' : null

export default function MyPortfolioView({ onSelectTicker }) {
  const { data, loading, error, refetch } = useHoldings()
  const { data: tradeData, refetch: refetchTrades } = useTradeHistory(20)
  const { data: allocData } = useAllocation()
  const { data: moversData } = useMovers()
  const [activeTab, setActiveTab] = useState('overview')
  const [perfPeriod, setPerfPeriod] = useState('3mo')
  const { data: perfData, loading: perfLoading } = usePerformance(perfPeriod)
  const [benchPeriod, setBenchPeriod] = useState('3mo')
  const [benchTicker, setBenchTicker] = useState('SPY')
  const { data: benchData, loading: benchLoading } = useBenchmark(benchPeriod, benchTicker)
  const [sortCol, setSortCol] = useState('market_value')
  const [sortDir, setSortDir] = useState('desc')

  // Privacy lock state
  const [locked, setLocked] = useState(true)
  const [showPwPrompt, setShowPwPrompt] = useState(false)
  const [pwInput, setPwInput] = useState('')
  const [pwError, setPwError] = useState(false)

  // Adjust position modal state
  const [showAdjust, setShowAdjust] = useState(false)
  const [adjustForm, setAdjustForm] = useState({ ticker: '', name: '', quantity: '', avg_cost: '', sector: '', country: '' })
  const [adjustSaving, setAdjustSaving] = useState(false)
  const [adjustError, setAdjustError] = useState(null)

  // Ticker validation state (shared — only one modal open at a time)
  const [tickerValid, setTickerValid] = useState(null) // null=unchecked, true=valid, false=invalid
  const [tickerValidating, setTickerValidating] = useState(false)

  // Log Trade modal state
  const [showLogTrade, setShowLogTrade] = useState(false)
  const [tradeForm, setTradeForm] = useState({ action: 'BUY', ticker: '', name: '', quantity: '', price: '', sector: '', country: '', currency: 'USD' })
  const [tradeSaving, setTradeSaving] = useState(false)
  const [tradeError, setTradeError] = useState(null)

  // Realized P&L
  const { data: realizedData, refetch: refetchRealized } = useRealizedPnl()

  const [lockTimer, setLockTimer] = useState(null)

  const handleUnlock = async () => {
    const hash = await sha256(pwInput)
    if (hash === UNLOCK_HASH) {
      setLocked(false)
      setShowPwPrompt(false)
      setPwInput('')
      setPwError(false)
      // Auto-lock after 5 minutes
      if (lockTimer) clearTimeout(lockTimer)
      const timer = setTimeout(() => setLocked(true), 5 * 60 * 1000)
      setLockTimer(timer)
    } else {
      setPwError(true)
    }
  }

  const handleLock = () => {
    setLocked(true)
    if (lockTimer) { clearTimeout(lockTimer); setLockTimer(null) }
  }

  const openAdjust = (holding = null) => {
    if (holding) {
      setAdjustForm({
        ticker: holding.ticker,
        name: holding.quote_name || holding.name || '',
        quantity: String(holding.quantity),
        avg_cost: String(holding.avg_cost),
        sector: holding.sector || '',
        country: holding.country || '',
      })
    } else {
      setAdjustForm({ ticker: '', name: '', quantity: '', avg_cost: '', sector: '', country: '' })
    }
    setAdjustError(null)
    setTickerValid(null)
    setTickerValidating(false)
    setShowAdjust(true)
  }

  const handleAdjustSave = async () => {
    if (!adjustForm.ticker.trim() || !adjustForm.quantity || !adjustForm.avg_cost) {
      setAdjustError('Ticker, quantity, and avg cost are required')
      return
    }
    setAdjustSaving(true)
    setAdjustError(null)
    try {
      const res = await fetch('/api/holdings/adjust', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: adjustForm.ticker.trim().toUpperCase(),
          name: adjustForm.name.trim() || null,
          quantity: parseInt(adjustForm.quantity),
          avg_cost: parseFloat(adjustForm.avg_cost),
          sector: adjustForm.sector,
          country: adjustForm.country,
        }),
      })
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}))
        throw new Error(errBody.detail || `HTTP ${res.status}`)
      }
      setShowAdjust(false)
      refetch()
    } catch (err) {
      setAdjustError(err.message)
    } finally {
      setAdjustSaving(false)
    }
  }

  const handleRemovePosition = async (ticker) => {
    if (!confirm(`Remove ${ticker} from portfolio?`)) return
    try {
      await fetch(`/api/holdings/${ticker}`, { method: 'DELETE' })
      refetch()
    } catch (err) {
      console.error('Failed to remove position:', err)
    }
  }

  const lookupTicker = async (ticker, target = 'trade') => {
    if (!ticker || ticker.length < 1) return
    setTickerValidating(true)
    setTickerValid(null)
    try {
      const res = await fetch(`/api/ticker-info/${ticker.trim().toUpperCase()}`)
      if (!res.ok) { setTickerValid(false); return }
      const info = await res.json()
      setTickerValid(info.valid !== false)
      if (info.valid !== false) {
        if (target === 'trade') {
          setTradeForm(prev => ({
            ...prev,
            name: prev.name || info.name || '',
            sector: prev.sector || info.sector || '',
            country: prev.country || info.country || '',
            currency: info.currency || prev.currency || 'USD',
          }))
        } else if (target === 'adjust') {
          setAdjustForm(prev => ({
            ...prev,
            name: prev.name || info.name || '',
          }))
        }
      }
    } catch {
      setTickerValid(null) // network error — don't block
    } finally {
      setTickerValidating(false)
    }
  }

  const openLogTrade = (action = 'BUY', holding = null) => {
    setTradeForm({
      action,
      ticker: holding?.ticker || '',
      name: holding?.quote_name || holding?.name || '',
      quantity: '',
      price: '',
      sector: holding?.sector || '',
      country: holding?.country || '',
      currency: holding?.currency || 'USD',
    })
    setTradeError(null)
    setTickerValid(null)
    setTickerValidating(false)
    setShowLogTrade(true)
  }

  const handleLogTrade = async () => {
    if (!tradeForm.ticker.trim() || !tradeForm.quantity || !tradeForm.price) {
      setTradeError('Ticker, quantity, and price are required')
      return
    }
    const qty = parseInt(tradeForm.quantity)
    const action = tradeForm.action.toUpperCase()

    // Validate sell quantity against current holdings
    if (action === 'SELL') {
      const holding = holdings.find(h => h.ticker === tradeForm.ticker.trim().toUpperCase())
      if (!holding) {
        setTradeError(`You don't hold ${tradeForm.ticker.trim().toUpperCase()}`)
        return
      }
      if (qty > holding.quantity) {
        setTradeError(`Cannot sell ${qty} shares — you only hold ${holding.quantity}`)
        return
      }
    }

    setTradeSaving(true)
    setTradeError(null)
    try {
      const res = await fetch('/api/trades/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action,
          ticker: tradeForm.ticker.trim().toUpperCase(),
          name: tradeForm.name.trim() || null,
          quantity: qty,
          price: parseFloat(tradeForm.price),
          sector: tradeForm.sector,
          country: tradeForm.country,
          currency: tradeForm.currency,
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      setShowLogTrade(false)
      refetch()
      refetchTrades()
      refetchRealized()
    } catch (err) {
      setTradeError(err.message)
    } finally {
      setTradeSaving(false)
    }
  }

  if (loading) return <Spinner />
  if (error) return <div className="text-red-400 p-4">Error: {error}</div>

  const holdings = data?.holdings || []
  const summary = data?.summary || {}
  const trades = tradeData?.trades || []
  const gainers = moversData?.gainers || []
  const losers = moversData?.losers || []
  const sectors = allocData?.sectors || []
  const countries = allocData?.countries || []

  const handleSort = (col) => {
    if (sortCol === col) setSortDir(sortDir === 'desc' ? 'asc' : 'desc')
    else { setSortCol(col); setSortDir('desc') }
  }
  const sorted = [...holdings].sort((a, b) => {
    const av = a[sortCol] ?? 0, bv = b[sortCol] ?? 0
    return sortDir === 'desc' ? bv - av : av - bv
  })

  const totalMV = summary.total_market_value || 0

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'performance', label: 'Performance' },
    { id: 'trades', label: 'Trade History' },
    { id: 'realized', label: 'Realized P&L' },
  ]

  // Helper: render a dollar value or mask it
  const $v = (val, opts = {}) => {
    if (locked) return mask(true)
    if (val == null) return '—'
    const { sign, compact, decimals = 0 } = opts
    if (compact) return fmtCurrency(val)
    const abs = Math.abs(val)
    const formatted = `$${abs.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`
    if (sign) return `${val >= 0 ? '+' : '-'}${formatted}`
    return `$${val.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`
  }

  return (
    <div className="space-y-6 animate-slide-in">
      {/* Hero: Total Value + P&L + Lock button */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          {summary.portfolio_name && (
            <div className="text-[10px] font-medium text-[#3b82f6] mb-0.5">{summary.portfolio_name}</div>
          )}
          <div className="text-[#8b8d97] text-xs mb-1">Total Portfolio Value</div>
          <div className="text-3xl sm:text-4xl font-bold tracking-tight">
            {locked ? '$\u2022\u2022\u2022,\u2022\u2022\u2022' : (
              summary.total_market_value != null
                ? `$${summary.total_market_value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
                : '—'
            )}
          </div>
          <div className="flex items-center gap-3 mt-1">
            {locked ? (
              <span className="text-lg font-semibold text-[#8b8d97]">P&L hidden</span>
            ) : (
              <>
                <span className={`text-lg font-semibold ${(summary.total_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {summary.total_pnl != null
                    ? `${summary.total_pnl >= 0 ? '+' : '-'}$${Math.abs(summary.total_pnl).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
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
              </>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] text-[#8b8d97]">{summary.count || 0} positions</span>
          {data?.timestamp && (
            <span className="text-[10px] text-[#8b8d97]">
              · Updated {new Date(data.timestamp + 'Z').toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
          <button
            onClick={refetch}
            className="px-3 py-2 rounded-lg text-xs font-medium text-[#8b8d97] hover:text-white hover:bg-[#1e2130] transition-colors"
          >
            Refresh
          </button>
          {/* Log Trade button */}
          <button
            onClick={() => openLogTrade('BUY')}
            className="px-3 py-2 rounded-lg text-xs font-medium text-white hover:brightness-110 transition-all flex items-center gap-1.5 bg-gradient-to-r from-[#3b82f6] to-[#6366f1]"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            Log Trade
          </button>
          {/* Lock / Unlock button */}
          <button
            onClick={() => {
              if (locked) {
                setShowPwPrompt(true)
                setPwError(false)
                setPwInput('')
              } else {
                handleLock()
              }
            }}
            className={`px-3 py-2 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${
              locked
                ? 'bg-[#1e2130] text-[#8b8d97] hover:text-white border border-[#2a2d3e]'
                : 'bg-green-500/15 text-green-400 border border-green-500/30'
            }`}
            title={locked ? 'Unlock portfolio values' : 'Lock portfolio values'}
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {locked ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 11V7a4 4 0 118 0m-4 8v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z" />
              )}
            </svg>
            {locked ? 'Unlock' : 'Lock'}
          </button>
        </div>
      </div>

      {/* Password prompt modal */}
      {showPwPrompt && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-start justify-center overflow-y-auto pt-8 sm:pt-16 pb-8 px-4" onClick={() => setShowPwPrompt(false)}>
          <div className="bg-[#1e2130] border border-[#2a2d3e] rounded-xl p-6 w-full max-w-xs shadow-2xl" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold mb-3">Unlock Portfolio</h3>
            <p className="text-xs text-[#8b8d97] mb-4">Enter password to reveal portfolio values.</p>
            <input
              type="password"
              value={pwInput}
              onChange={e => { setPwInput(e.target.value); setPwError(false) }}
              onKeyDown={e => e.key === 'Enter' && handleUnlock()}
              placeholder="Password"
              autoFocus
              className={`w-full bg-[#0f1117] border rounded-lg px-4 py-2.5 text-sm focus:outline-none transition-colors ${
                pwError ? 'border-red-500 focus:border-red-500' : 'border-[#2a2d3e] focus:border-[#3b82f6]'
              }`}
            />
            {pwError && <p className="text-red-400 text-xs mt-2">Incorrect password</p>}
            <div className="flex gap-2 mt-4">
              <button
                onClick={() => setShowPwPrompt(false)}
                className="flex-1 px-4 py-2 rounded-lg text-xs font-medium text-[#8b8d97] hover:text-white bg-[#0f1117] transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleUnlock}
                className="flex-1 px-4 py-2 rounded-lg text-xs font-medium text-white bg-[#3b82f6] hover:bg-[#2563eb] transition-colors"
              >
                Unlock
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Adjust position modal (for editing existing positions) */}
      {showAdjust && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-start justify-center overflow-y-auto pt-8 sm:pt-16 pb-8 px-4" onClick={() => setShowAdjust(false)}>
          <div className="bg-[#1e2130] border border-[#2a2d3e] rounded-xl p-5 sm:p-6 w-full max-w-sm shadow-2xl" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold mb-4">Edit {adjustForm.ticker || 'Position'}</h3>
            <div className="space-y-3">
              <div>
                <label className="text-[10px] text-[#8b8d97] block mb-1">Ticker *</label>
                <input
                  value={adjustForm.ticker}
                  onChange={e => { setAdjustForm({ ...adjustForm, ticker: e.target.value }); setTickerValid(null) }}
                  onBlur={e => { if (e.target.value && !adjustForm.ticker) lookupTicker(e.target.value, 'adjust') }}
                  placeholder="e.g. AAPL"
                  disabled={!!adjustForm.ticker}
                  className={`w-full bg-[#0f1117] border rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-[#3b82f6] disabled:opacity-50 ${
                    !adjustForm.ticker ? (tickerValid === false ? 'border-red-500' : tickerValid === true ? 'border-green-500/50' : 'border-[#2a2d3e]') : 'border-[#2a2d3e]'
                  }`}
                />
                {tickerValidating && !adjustForm.ticker && <span className="text-[9px] text-[#8b8d97] mt-0.5 block">Checking ticker...</span>}
                {tickerValid === false && !adjustForm.ticker && <span className="text-[9px] text-red-400 mt-0.5 block">Ticker not found on Yahoo Finance</span>}
              </div>
              <div>
                <label className="text-[10px] text-[#8b8d97] block mb-1">Name</label>
                <input
                  value={adjustForm.name}
                  onChange={e => setAdjustForm({ ...adjustForm, name: e.target.value })}
                  placeholder="e.g. Apple Inc"
                  className="w-full bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#3b82f6]"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-[#8b8d97] block mb-1">Shares *</label>
                  <input
                    type="number"
                    value={adjustForm.quantity}
                    onChange={e => setAdjustForm({ ...adjustForm, quantity: e.target.value })}
                    placeholder="100"
                    className="w-full bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-[#3b82f6]"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-[#8b8d97] block mb-1">Avg Cost (USD) *</label>
                  <input
                    type="number"
                    step="0.01"
                    value={adjustForm.avg_cost}
                    onChange={e => setAdjustForm({ ...adjustForm, avg_cost: e.target.value })}
                    placeholder="150.00"
                    className="w-full bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-[#3b82f6]"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-[#8b8d97] block mb-1">Sector</label>
                  <input
                    value={adjustForm.sector}
                    onChange={e => setAdjustForm({ ...adjustForm, sector: e.target.value })}
                    placeholder="e.g. Tech"
                    className="w-full bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#3b82f6]"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-[#8b8d97] block mb-1">Country</label>
                  <input
                    value={adjustForm.country}
                    onChange={e => setAdjustForm({ ...adjustForm, country: e.target.value })}
                    placeholder="e.g. US"
                    className="w-full bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#3b82f6]"
                  />
                </div>
              </div>
            </div>
            {adjustError && <p className="text-red-400 text-xs mt-3">{adjustError}</p>}
            <div className="flex gap-2 mt-4">
              <button
                onClick={() => setShowAdjust(false)}
                className="flex-1 px-4 py-2 rounded-lg text-xs font-medium text-[#8b8d97] hover:text-white bg-[#0f1117] transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleAdjustSave}
                disabled={adjustSaving}
                className="flex-1 px-4 py-2 rounded-lg text-xs font-medium text-white bg-[#3b82f6] hover:bg-[#2563eb] disabled:opacity-50 transition-colors"
              >
                {adjustSaving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Log Trade modal */}
      {showLogTrade && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-start justify-center overflow-y-auto pt-8 sm:pt-16 pb-8 px-4" onClick={() => setShowLogTrade(false)}>
          <div className="bg-[#1e2130] border border-[#2a2d3e] rounded-xl p-5 sm:p-6 w-full max-w-sm shadow-2xl" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold mb-4">Log Trade</h3>
            {/* BUY / SELL toggle */}
            <div className="flex rounded-lg overflow-hidden border border-[#2a2d3e] mb-4">
              {['BUY', 'SELL'].map(a => (
                <button
                  key={a}
                  onClick={() => setTradeForm({ ...tradeForm, action: a })}
                  className={`flex-1 py-2 text-xs font-bold transition-colors ${
                    tradeForm.action === a
                      ? a === 'BUY'
                        ? 'bg-green-500/20 text-green-400 border-b-2 border-green-400'
                        : 'bg-red-500/20 text-red-400 border-b-2 border-red-400'
                      : 'text-[#8b8d97] hover:text-white'
                  }`}
                >
                  {a}
                </button>
              ))}
            </div>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-[#8b8d97] block mb-1">Ticker *</label>
                  <input
                    value={tradeForm.ticker}
                    onChange={e => { setTradeForm({ ...tradeForm, ticker: e.target.value }); setTickerValid(null) }}
                    onBlur={e => lookupTicker(e.target.value, 'trade')}
                    placeholder="e.g. AAPL"
                    className={`w-full bg-[#0f1117] border rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-[#3b82f6] ${
                      tickerValid === false ? 'border-red-500' : tickerValid === true ? 'border-green-500/50' : 'border-[#2a2d3e]'
                    }`}
                  />
                  {tickerValidating && <span className="text-[9px] text-[#8b8d97] mt-0.5 block">Checking ticker...</span>}
                  {tickerValid === false && <span className="text-[9px] text-red-400 mt-0.5 block">Ticker not found on Yahoo Finance</span>}
                </div>
                <div>
                  <label className="text-[10px] text-[#8b8d97] block mb-1">Name</label>
                  <input
                    value={tradeForm.name}
                    onChange={e => setTradeForm({ ...tradeForm, name: e.target.value })}
                    placeholder="e.g. Apple Inc"
                    className="w-full bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#3b82f6]"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-[#8b8d97] block mb-1">
                    Shares *
                    {tradeForm.action === 'SELL' && tradeForm.ticker && (() => {
                      const h = holdings.find(x => x.ticker === tradeForm.ticker.trim().toUpperCase())
                      return h ? <span className="text-[#8b8d97] ml-1">(hold: {h.quantity})</span> : null
                    })()}
                  </label>
                  <input
                    type="number"
                    value={tradeForm.quantity}
                    onChange={e => setTradeForm({ ...tradeForm, quantity: e.target.value })}
                    placeholder="100"
                    min="1"
                    className="w-full bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-[#3b82f6]"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-[#8b8d97] block mb-1">Price per Share *</label>
                  <input
                    type="number"
                    step="0.01"
                    value={tradeForm.price}
                    onChange={e => setTradeForm({ ...tradeForm, price: e.target.value })}
                    placeholder="150.00"
                    className="w-full bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-[#3b82f6]"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <div>
                  <label className="text-[10px] text-[#8b8d97] block mb-1">Sector</label>
                  <input
                    value={tradeForm.sector}
                    onChange={e => setTradeForm({ ...tradeForm, sector: e.target.value })}
                    placeholder="e.g. Tech"
                    className="w-full bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#3b82f6]"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-[#8b8d97] block mb-1">Country</label>
                  <input
                    value={tradeForm.country}
                    onChange={e => setTradeForm({ ...tradeForm, country: e.target.value })}
                    placeholder="e.g. US"
                    className="w-full bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#3b82f6]"
                  />
                </div>
                <div className="col-span-2 sm:col-span-1">
                  <label className="text-[10px] text-[#8b8d97] block mb-1">Currency</label>
                  <select
                    value={tradeForm.currency}
                    onChange={e => setTradeForm({ ...tradeForm, currency: e.target.value })}
                    className="w-full bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#3b82f6]"
                  >
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                    <option value="GBP">GBP</option>
                    <option value="JPY">JPY</option>
                    <option value="SGD">SGD</option>
                    <option value="HKD">HKD</option>
                    <option value="TWD">TWD</option>
                  </select>
                </div>
              </div>
              {/* Trade total preview */}
              {tradeForm.quantity && tradeForm.price && (
                <div className="p-2.5 rounded-lg bg-[#0f1117] border border-[#2a2d3e]">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-[#8b8d97]">Total {tradeForm.action === 'SELL' ? 'Proceeds' : 'Cost'}</span>
                    <span className={`font-mono font-bold ${tradeForm.action === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>
                      {tradeForm.currency === 'USD' ? '$' : tradeForm.currency + ' '}
                      {(parseInt(tradeForm.quantity) * parseFloat(tradeForm.price)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                </div>
              )}
            </div>
            {tradeError && <p className="text-red-400 text-xs mt-3">{tradeError}</p>}
            <div className="flex gap-2 mt-4">
              <button
                onClick={() => setShowLogTrade(false)}
                className="flex-1 px-4 py-2 rounded-lg text-xs font-medium text-[#8b8d97] hover:text-white bg-[#0f1117] transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleLogTrade}
                disabled={tradeSaving}
                className={`flex-1 px-4 py-2 rounded-lg text-xs font-medium text-white disabled:opacity-50 transition-colors ${
                  tradeForm.action === 'BUY'
                    ? 'bg-green-600 hover:bg-green-500'
                    : 'bg-red-600 hover:bg-red-500'
                }`}
              >
                {tradeSaving ? 'Saving...' : `${tradeForm.action === 'BUY' ? 'Buy' : 'Sell'}`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card>
          <div className="text-[#8b8d97] text-[10px] mb-1">Total Invested</div>
          <div className="text-lg font-bold">{locked ? mask(true) : fmtCurrency(summary.total_invested)}</div>
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
      <div className="flex items-center gap-1 border-b border-[#2a2d3e] pb-1 overflow-x-auto scrollbar-hide">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-xs font-medium rounded-t-lg transition-colors whitespace-nowrap ${
              activeTab === tab.id
                ? 'bg-[#3b82f6]/10 text-white border-b-2 border-[#3b82f6]'
                : 'text-[#8b8d97] hover:text-white hover:bg-[#1e2130]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ═══ OVERVIEW TAB ═══ */}
      {activeTab === 'overview' && (
        <div className="space-y-6 animate-slide-in">
          {/* Holdings */}
          <Card className="overflow-hidden">
            <h3 className="text-sm font-semibold mb-4">Holdings — Live</h3>
            {holdings.length === 0 ? (
              <div className="text-center py-12 text-[#8b8d97]">
                <p className="text-lg mb-2">No Holdings Yet</p>
                <p className="text-xs">Trade SMS messages forwarded via Telegram will automatically update your portfolio here.</p>
              </div>
            ) : (
              <>
                {/* ── Mobile card layout (< md) ── */}
                <div className="md:hidden space-y-2">
                  {sorted.map(h => {
                    const weight = totalMV > 0 && h.market_value ? (h.market_value / totalMV * 100) : 0
                    return (
                      <div
                        key={h.ticker}
                        className="bg-[#0f1117]/60 border border-[#2a2d3e]/50 rounded-lg p-3 cursor-pointer active:bg-[#252940] transition-colors"
                        onClick={() => onSelectTicker(h.ticker)}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="font-mono font-semibold text-sm">{h.ticker}</span>
                            <span className="text-[#8b8d97] text-xs truncate">{h.quote_name || h.name}</span>
                          </div>
                          <span className={`text-xs font-mono font-semibold flex-shrink-0 ${(h.change_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {fmtPct(h.change_pct)}
                          </span>
                        </div>
                        <div className="grid grid-cols-3 gap-2 text-xs">
                          <div>
                            <div className="text-[#8b8d97] text-[10px]">Price</div>
                            <div className="font-mono">{h.current_price_usd ? `$${fmt(h.current_price_usd)}` : h.current_price ? `$${fmt(h.current_price)}` : '\u2014'}</div>
                          </div>
                          <div>
                            <div className="text-[#8b8d97] text-[10px]">Mkt Value</div>
                            <div className="font-mono">{locked ? mask(true) : (h.market_value ? fmtCurrency(h.market_value) : '\u2014')}</div>
                          </div>
                          <div>
                            <div className="text-[#8b8d97] text-[10px]">P&L</div>
                            <div className={`font-mono ${(h.unrealized_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                              {locked ? mask(true) : (h.unrealized_pnl != null ? `${h.unrealized_pnl >= 0 ? '+' : '-'}$${Math.abs(h.unrealized_pnl).toLocaleString(undefined, { maximumFractionDigits: 0 })}` : '\u2014')}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center justify-between mt-2 pt-2 border-t border-[#2a2d3e]/30">
                          <div className="flex items-center gap-2 text-[10px] text-[#8b8d97]">
                            <span>{locked ? maskNum(true) : h.quantity.toLocaleString()} shares</span>
                            <span className="text-[#2a2d3e]">&middot;</span>
                            <span className={`font-semibold ${(h.unrealized_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>{fmtPct(h.unrealized_pct)}</span>
                            <span className="text-[#2a2d3e]">&middot;</span>
                            <span>{weight.toFixed(1)}%</span>
                          </div>
                          <div className="flex items-center gap-0.5">
                            <button onClick={(e) => { e.stopPropagation(); openLogTrade('SELL', h) }} className="p-1.5 rounded hover:bg-[#1e2130] text-[#8b8d97] hover:text-red-400" title="Sell">
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
                            </button>
                            <button onClick={(e) => { e.stopPropagation(); openAdjust(h) }} className="p-1.5 rounded hover:bg-[#1e2130] text-[#8b8d97] hover:text-[#3b82f6]" title="Edit">
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                            </button>
                            <button onClick={(e) => { e.stopPropagation(); handleRemovePosition(h.ticker) }} className="p-1.5 rounded hover:bg-[#1e2130] text-[#8b8d97] hover:text-red-400" title="Remove">
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                            </button>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
                {/* ── Desktop table (>= md) ── */}
                <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-[#a0a2ab] border-b border-[#2a2d3e] bg-[#0f1117]/40 text-[10px] uppercase tracking-wider">
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
                        className={`py-2.5 pr-2 cursor-pointer hover:text-white transition-colors select-none font-semibold ${col.align === 'right' ? 'text-right' : 'text-left'}`}
                        onClick={() => col.key !== 'name' && col.key !== 'weight' && handleSort(col.key)}
                      >
                        {col.label}
                        {sortCol === col.key && <span className="ml-0.5 text-[#3b82f6]">{sortDir === 'desc' ? '\u25BC' : '\u25B2'}</span>}
                      </th>
                    ))}
                    <th className="py-2.5 w-20" />
                  </tr>
                </thead>
                <tbody>
                  {sorted.map(h => {
                    const weight = totalMV > 0 && h.market_value ? (h.market_value / totalMV * 100) : 0
                    return (
                      <tr
                        key={h.ticker}
                        className="group border-b border-[#2a2d3e]/50 hover:bg-[#252940] transition-colors cursor-pointer"
                        onClick={() => onSelectTicker(h.ticker)}
                      >
                        <td className="py-2 pr-2 font-mono font-semibold">{h.ticker}</td>
                        <td className="py-2 pr-2 text-[#8b8d97] max-w-[140px] truncate">{h.quote_name || h.name}</td>
                        <td className="py-2 pr-2 text-right font-mono">{locked ? maskNum(true) : h.quantity.toLocaleString()}</td>
                        <td className="py-2 pr-2 text-right font-mono">
                          {locked ? mask(true) : `$${fmt(h.avg_cost_usd || h.avg_cost)}`}
                          {h.currency === 'EUR' && <span className="text-[9px] text-[#8b8d97] ml-0.5">EUR</span>}
                        </td>
                        <td className="py-2 pr-2 text-right font-mono">
                          {h.current_price_usd ? `$${fmt(h.current_price_usd)}` : h.current_price ? `$${fmt(h.current_price)}` : '—'}
                          {h.currency === 'EUR' && <span className="text-[9px] text-[#8b8d97] ml-0.5">EUR</span>}
                        </td>
                        <td className={`py-2 pr-2 text-right font-mono ${(h.change_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {fmtPct(h.change_pct)}
                        </td>
                        <td className="py-2 pr-2 text-right font-mono">{locked ? mask(true) : (h.market_value ? fmtCurrency(h.market_value) : '—')}</td>
                        <td className={`py-2 pr-2 text-right font-mono ${(h.unrealized_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {locked ? mask(true) : (h.unrealized_pnl != null ? `${h.unrealized_pnl >= 0 ? '+' : '-'}$${Math.abs(h.unrealized_pnl).toLocaleString(undefined, { maximumFractionDigits: 0 })}` : '—')}
                        </td>
                        <td className={`py-2 pr-2 text-right font-mono font-semibold ${(h.unrealized_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {fmtPct(h.unrealized_pct)}
                        </td>
                        <td className="py-2 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <div className="w-12 h-1.5 bg-[#0f1117] rounded-full overflow-hidden">
                              <div className="h-full bg-[#3b82f6] rounded-full" style={{ width: `${Math.min(100, weight)}%` }} />
                            </div>
                            <span className="text-[10px] font-mono text-white w-8 text-right">{weight.toFixed(1)}%</span>
                          </div>
                        </td>
                        <td className="py-2 pl-2">
                          <div className="flex items-center gap-1 opacity-30 group-hover:opacity-100 transition-opacity">
                            <button
                              onClick={(e) => { e.stopPropagation(); openLogTrade('SELL', h) }}
                              className="p-1 rounded hover:bg-[#0f1117] text-[#8b8d97] hover:text-red-400"
                              title="Sell shares"
                            >
                              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                              </svg>
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); openAdjust(h) }}
                              className="p-1 rounded hover:bg-[#0f1117] text-[#8b8d97] hover:text-[#3b82f6]"
                              title="Edit position"
                            >
                              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                              </svg>
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); handleRemovePosition(h.ticker) }}
                              className="p-1 rounded hover:bg-[#0f1117] text-[#8b8d97] hover:text-red-400"
                              title="Remove position"
                            >
                              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              </div>
              </>
            )}
          </Card>

          {/* Allocation Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <h3 className="text-sm font-semibold mb-4">Sector Allocation</h3>
              {sectors.length > 0 ? (() => {
                // Group small sectors (<2%) into "Other"
                const major = sectors.filter(s => s.pct >= 2)
                const minor = sectors.filter(s => s.pct < 2)
                const grouped = minor.length > 0
                  ? [...major, { name: 'Other', value: minor.reduce((s, m) => s + m.value, 0), pct: minor.reduce((s, m) => s + m.pct, 0) }]
                  : major
                return (
                  <>
                    <ResponsiveContainer width="100%" height={260}>
                      <PieChart>
                        <Pie
                          data={grouped}
                          cx="50%"
                          cy="50%"
                          innerRadius={60}
                          outerRadius={95}
                          dataKey="value"
                          nameKey="name"
                          label={locked ? false : renderPieLabel}
                          labelLine={false}
                          strokeWidth={2}
                          stroke="#0f1117"
                        >
                          {grouped.map((s, i) => (
                            <Cell key={s.name} fill={s.name === 'Other' ? '#4b5563' : SECTOR_COLORS[i % SECTOR_COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip content={locked ? () => null : (props) => <PieTooltipContent {...props} />} wrapperStyle={{ outline: 'none', background: 'transparent', border: 'none', boxShadow: 'none', padding: 0 }} contentStyle={{ background: 'transparent', border: 'none', padding: 0, boxShadow: 'none' }} />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="flex flex-wrap gap-x-3 gap-y-1.5 mt-3 justify-center">
                      {grouped.map((s, i) => (
                        <div key={s.name} className="flex items-center gap-1.5 text-[10px]">
                          <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: s.name === 'Other' ? '#4b5563' : SECTOR_COLORS[i % SECTOR_COLORS.length] }} />
                          <span className="text-[#8b8d97]">{s.name}</span>
                          <span className="font-semibold text-white">{s.pct}%</span>
                        </div>
                      ))}
                    </div>
                  </>
                )
              })() : <div className="text-center py-8 text-[#8b8d97] text-xs">No allocation data</div>}
            </Card>

            <Card>
              <h3 className="text-sm font-semibold mb-4">Country Allocation</h3>
              {countries.length > 0 ? (() => {
                const COUNTRY_COLORS = ['#eab308', '#06b6d4', '#ec4899', '#a855f7', '#22c55e', '#f97316']
                return (
                  <>
                    <ResponsiveContainer width="100%" height={260}>
                      <PieChart>
                        <Pie
                          data={countries}
                          cx="50%"
                          cy="50%"
                          innerRadius={60}
                          outerRadius={95}
                          dataKey="value"
                          nameKey="name"
                          label={locked ? false : renderPieLabel}
                          labelLine={false}
                          strokeWidth={2}
                          stroke="#0f1117"
                        >
                          {countries.map((c, i) => (
                            <Cell key={c.name} fill={COUNTRY_COLORS[i % COUNTRY_COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip content={locked ? () => null : (props) => <PieTooltipContent {...props} />} wrapperStyle={{ outline: 'none', background: 'transparent', border: 'none', boxShadow: 'none', padding: 0 }} contentStyle={{ background: 'transparent', border: 'none', padding: 0, boxShadow: 'none' }} />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-3 justify-center">
                      {countries.map((c, i) => (
                        <div key={c.name} className="flex items-center gap-1.5 text-[10px]">
                          <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: COUNTRY_COLORS[i % COUNTRY_COLORS.length] }} />
                          <span className="text-[#8b8d97]">{c.name}</span>
                          <span className="font-semibold text-white">{c.pct}%</span>
                        </div>
                      ))}
                    </div>
                  </>
                )
              })() : <div className="text-center py-8 text-[#8b8d97] text-xs">No allocation data</div>}
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
          {!locked && holdings.length > 0 && holdings.some(h => h.unrealized_pnl != null) && (() => {
            const pnlData = [...holdings]
              .filter(h => h.unrealized_pnl != null)
              .sort((a, b) => (b.unrealized_pnl || 0) - (a.unrealized_pnl || 0))
            return (
              <Card>
                <h3 className="text-sm font-semibold mb-4">Unrealized P&L by Position</h3>
                <ResponsiveContainer width="100%" height={Math.max(240, pnlData.length * 26)}>
                  <BarChart data={pnlData} layout="vertical" margin={{ left: 55, right: 20 }} barCategoryGap="20%">
                    <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3e" horizontal={false} />
                    <XAxis
                      type="number"
                      tick={{ fill: '#8b8d97', fontSize: 10 }}
                      tickFormatter={v => v === 0 ? '0' : `${v > 0 ? '+' : ''}$${(Math.abs(v) / 1000).toFixed(0)}k`}
                      axisLine={{ stroke: '#2a2d3e' }}
                    />
                    <YAxis
                      type="category"
                      dataKey="ticker"
                      tick={{ fill: '#e4e5e7', fontSize: 10, fontFamily: 'monospace' }}
                      width={50}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip content={<BarTooltipContent />} cursor={{ fill: '#ffffff08' }} />
                    <Bar dataKey="unrealized_pnl" radius={[0, 3, 3, 0]} maxBarSize={18}>
                      {pnlData.map((entry) => (
                        <Cell
                          key={entry.ticker}
                          fill={(entry.unrealized_pnl || 0) >= 0 ? '#22c55e' : '#ef4444'}
                          fillOpacity={0.85}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            )
          })()}
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
            {locked ? (
              <div className="text-center py-12 text-[#8b8d97] text-xs">
                <svg className="w-8 h-8 mx-auto mb-2 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                Unlock to view performance charts
              </div>
            ) : perfLoading ? <Spinner /> : perfData?.data?.length > 0 ? (
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

            {!locked && perfData?.data?.length > 0 && (
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
          {holdings.length > 0 && (() => {
            const dayData = [...holdings]
              .filter(h => h.change_pct != null)
              .sort((a, b) => (b.change_pct || 0) - (a.change_pct || 0))
            return (
              <Card>
                <h3 className="text-sm font-semibold mb-4">Today's Change by Position</h3>
                <ResponsiveContainer width="100%" height={Math.max(240, dayData.length * 26)}>
                  <BarChart data={dayData} layout="vertical" margin={{ left: 55, right: 20 }} barCategoryGap="20%">
                    <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3e" horizontal={false} />
                    <XAxis
                      type="number"
                      tick={{ fill: '#8b8d97', fontSize: 10 }}
                      tickFormatter={v => `${v}%`}
                      axisLine={{ stroke: '#2a2d3e' }}
                    />
                    <YAxis
                      type="category"
                      dataKey="ticker"
                      tick={{ fill: '#e4e5e7', fontSize: 10, fontFamily: 'monospace' }}
                      width={50}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip content={<BarTooltipContent valuePrefix="" valueSuffix="%" />} cursor={{ fill: '#ffffff08' }} />
                    <Bar dataKey="change_pct" radius={[0, 3, 3, 0]} maxBarSize={18}>
                      {dayData.map((entry) => (
                        <Cell
                          key={entry.ticker}
                          fill={(entry.change_pct || 0) >= 0 ? '#22c55e' : '#ef4444'}
                          fillOpacity={0.85}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            )
          })()}
        </div>
      )}

      {/* ═══ TRADES TAB ═══ */}
      {activeTab === 'trades' && (
        <Card className="animate-slide-in">
          <h3 className="text-sm font-semibold mb-4">Trade History</h3>
          {trades.length === 0 ? (
            <div className="text-center py-12 text-[#8b8d97]">
              <p className="text-lg mb-2">No Trades Recorded</p>
              <p className="text-xs">Use "Log Trade" to manually record buys and sells, or forward trade SMS via Telegram.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
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
                    <td className="py-2 pr-2 text-[#8b8d97] whitespace-nowrap">{new Date(t.timestamp).toLocaleDateString()}</td>
                    <td className="py-2 pr-2">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                        t.action === 'BUY' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                      }`}>
                        {t.action}
                      </span>
                    </td>
                    <td className="py-2 pr-2 font-mono font-semibold">{t.ticker}</td>
                    <td className="py-2 pr-2 text-[#8b8d97] max-w-[140px] truncate">{t.name}</td>
                    <td className="py-2 pr-2 text-right font-mono whitespace-nowrap">{locked ? maskNum(true) : t.quantity.toLocaleString()}</td>
                    <td className="py-2 pr-2 text-right font-mono whitespace-nowrap">{locked ? mask(true) : `$${fmt(t.price)}`}</td>
                    <td className="py-2 text-right font-mono whitespace-nowrap">{locked ? mask(true) : fmtCurrency(t.total_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          )}
        </Card>
      )}

      {/* ═══ REALIZED P&L TAB ═══ */}
      {activeTab === 'realized' && (
        <div className="space-y-6 animate-slide-in">
          {/* Summary cards */}
          {realizedData?.summary && (() => {
            const s = realizedData.summary
            return (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <Card>
                  <div className="text-[#8b8d97] text-[10px] mb-1">Total Realized P&L</div>
                  <div className={`text-lg font-bold font-mono ${(s.total_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {locked ? mask(true) : `${s.total_pnl >= 0 ? '+' : '-'}$${Math.abs(s.total_pnl).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                  </div>
                </Card>
                <Card>
                  <div className="text-[#8b8d97] text-[10px] mb-1">Closed Trades</div>
                  <div className="text-lg font-bold">{s.trade_count || 0}</div>
                </Card>
                <Card>
                  <div className="text-[#8b8d97] text-[10px] mb-1">Winners</div>
                  <div className="text-lg font-bold text-green-400">{s.winners || 0}</div>
                </Card>
                <Card>
                  <div className="text-[#8b8d97] text-[10px] mb-1">Losers</div>
                  <div className="text-lg font-bold text-red-400">{s.losers || 0}</div>
                </Card>
              </div>
            )
          })()}

          {/* Realized P&L records table */}
          <Card>
            <h3 className="text-sm font-semibold mb-4">Realized P&L Records</h3>
            {(!realizedData?.records || realizedData.records.length === 0) ? (
              <div className="text-center py-12 text-[#8b8d97]">
                <p className="text-lg mb-2">No Realized P&L Yet</p>
                <p className="text-xs">Sell trades will automatically track your realized profit/loss here.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-[#a0a2ab] border-b border-[#2a2d3e] bg-[#0f1117]/40 text-[10px] uppercase tracking-wider">
                    <th className="text-left py-2.5 pr-2 font-semibold whitespace-nowrap">Date</th>
                    <th className="text-left py-2.5 pr-2 font-semibold">Ticker</th>
                    <th className="text-left py-2.5 pr-2 font-semibold">Name</th>
                    <th className="text-right py-2.5 pr-2 font-semibold whitespace-nowrap">Shares Sold</th>
                    <th className="text-right py-2.5 pr-2 font-semibold whitespace-nowrap">Avg Cost</th>
                    <th className="text-right py-2.5 pr-2 font-semibold whitespace-nowrap">Sell Price</th>
                    <th className="text-right py-2.5 pr-2 font-semibold">P&L</th>
                    <th className="text-right py-2.5 font-semibold">Return</th>
                  </tr>
                </thead>
                <tbody>
                  {realizedData.records.map(r => (
                    <tr key={r.id} className="border-b border-[#2a2d3e]/50 hover:bg-[#252940] transition-colors">
                      <td className="py-2 pr-2 text-[#8b8d97] whitespace-nowrap">{new Date(r.timestamp).toLocaleDateString()}</td>
                      <td className="py-2 pr-2 font-mono font-semibold">{r.ticker}</td>
                      <td className="py-2 pr-2 text-[#8b8d97] max-w-[120px] truncate">{r.name}</td>
                      <td className="py-2 pr-2 text-right font-mono whitespace-nowrap">{locked ? maskNum(true) : r.quantity.toLocaleString()}</td>
                      <td className="py-2 pr-2 text-right font-mono whitespace-nowrap">{locked ? mask(true) : `$${fmt(r.buy_avg_cost)}`}</td>
                      <td className="py-2 pr-2 text-right font-mono whitespace-nowrap">{locked ? mask(true) : `$${fmt(r.sell_price)}`}</td>
                      <td className={`py-2 pr-2 text-right font-mono font-semibold whitespace-nowrap ${(r.realized_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {locked ? mask(true) : `${r.realized_pnl >= 0 ? '+' : ''}$${Math.abs(r.realized_pnl).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                      </td>
                      <td className={`py-2 text-right font-mono font-semibold whitespace-nowrap ${(r.realized_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {r.realized_pct >= 0 ? '+' : ''}{r.realized_pct?.toFixed(2)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  )
}

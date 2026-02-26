import { useState, useEffect, useRef, useCallback } from 'react'

const STORAGE_KEY = 'fe_search_history'
const MAX_HISTORY = 15

function getHistory() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
  } catch { return [] }
}

function saveHistory(history) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(history.slice(0, MAX_HISTORY)))
}

export function addToSearchHistory(ticker, name) {
  const history = getHistory()
  // Remove duplicate if it exists
  const filtered = history.filter(h => h.ticker !== ticker)
  filtered.unshift({ ticker, name: name || ticker, timestamp: Date.now() })
  saveHistory(filtered)
}

export default function SearchOverlay({ open, onClose, onSearch }) {
  const [query, setQuery] = useState('')
  const [history, setHistory] = useState([])
  const [validating, setValidating] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef(null)
  const overlayRef = useRef(null)

  // Load history when opening
  useEffect(() => {
    if (open) {
      setHistory(getHistory())
      setQuery('')
      setError('')
      // Focus after animation
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  // Close on Escape
  useEffect(() => {
    if (!open) return
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (overlayRef.current && !overlayRef.current.contains(e.target)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open, onClose])

  const handleSubmit = useCallback(async (ticker) => {
    const t = (ticker || query).trim().toUpperCase()
    if (!t) return

    setError('')
    setValidating(true)
    try {
      const res = await fetch(`/api/ticker-info/${t}`)
      const info = await res.json()
      if (!info.valid) {
        setError(`"${t}" is not a valid ticker`)
        setValidating(false)
        return
      }
      addToSearchHistory(t, info.name)
      setHistory(getHistory())
      onSearch(t)
      onClose()
    } catch {
      // Network error — still navigate, let detail page handle it
      addToSearchHistory(t, t)
      onSearch(t)
      onClose()
    } finally {
      setValidating(false)
    }
  }, [query, onSearch, onClose])

  const handleHistoryClick = (ticker) => {
    // Move to top of history
    addToSearchHistory(ticker, history.find(h => h.ticker === ticker)?.name || ticker)
    onSearch(ticker)
    onClose()
  }

  const removeHistoryItem = (e, ticker) => {
    e.stopPropagation()
    const updated = getHistory().filter(h => h.ticker !== ticker)
    saveHistory(updated)
    setHistory(updated)
  }

  const clearHistory = () => {
    saveHistory([])
    setHistory([])
  }

  if (!open) return null

  const filteredHistory = query.trim()
    ? history.filter(h =>
        h.ticker.includes(query.toUpperCase()) ||
        h.name?.toLowerCase().includes(query.toLowerCase())
      )
    : history

  const timeAgo = (ts) => {
    const mins = Math.floor((Date.now() - ts) / 60000)
    if (mins < 1) return 'just now'
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    const days = Math.floor(hrs / 24)
    return `${days}d ago`
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-16 sm:pt-24">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Search panel */}
      <div
        ref={overlayRef}
        className="relative w-full max-w-lg mx-4 bg-[#1a1d2e] border border-[#2a2d3e] rounded-xl shadow-2xl overflow-hidden animate-slide-in"
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-[#2a2d3e]">
          <svg className="w-5 h-5 text-[#8b8d97] flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => { setQuery(e.target.value); setError('') }}
            onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
            placeholder="Search ticker symbol... (e.g. AAPL, TSLA, ASML)"
            className="flex-1 bg-transparent text-sm font-mono text-white placeholder-[#8b8d97] focus:outline-none"
            autoComplete="off"
            spellCheck={false}
          />
          {validating && (
            <div className="w-4 h-4 border-2 border-[#3b82f6] border-t-transparent rounded-full animate-spin flex-shrink-0" />
          )}
          {query && !validating && (
            <button
              onClick={() => { setQuery(''); setError(''); inputRef.current?.focus() }}
              className="text-[#8b8d97] hover:text-white transition-colors flex-shrink-0"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
          <kbd className="hidden sm:inline-flex text-[10px] text-[#8b8d97] bg-[#0f1117] px-1.5 py-0.5 rounded border border-[#2a2d3e]">ESC</kbd>
        </div>

        {/* Error */}
        {error && (
          <div className="px-4 py-2 text-xs text-red-400 bg-red-400/10 border-b border-[#2a2d3e]">
            {error}
          </div>
        )}

        {/* History */}
        <div className="max-h-[340px] overflow-y-auto">
          {filteredHistory.length > 0 ? (
            <>
              <div className="flex items-center justify-between px-4 pt-3 pb-1">
                <span className="text-[10px] text-[#8b8d97] uppercase tracking-wider font-semibold">
                  {query.trim() ? 'Matching history' : 'Recent searches'}
                </span>
                {!query.trim() && history.length > 0 && (
                  <button
                    onClick={clearHistory}
                    className="text-[10px] text-[#8b8d97] hover:text-red-400 transition-colors"
                  >
                    Clear all
                  </button>
                )}
              </div>
              <div className="py-1">
                {filteredHistory.map(h => (
                  <button
                    key={h.ticker}
                    onClick={() => handleHistoryClick(h.ticker)}
                    className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-[#252940] transition-colors group"
                  >
                    <svg className="w-4 h-4 text-[#8b8d97] flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <div className="flex-1 text-left min-w-0">
                      <span className="text-sm font-mono font-semibold text-blue-400">{h.ticker}</span>
                      {h.name && h.name !== h.ticker && (
                        <span className="text-xs text-[#8b8d97] ml-2 truncate">{h.name}</span>
                      )}
                    </div>
                    <span className="text-[10px] text-[#8b8d97] flex-shrink-0">{timeAgo(h.timestamp)}</span>
                    <button
                      onClick={(e) => removeHistoryItem(e, h.ticker)}
                      className="opacity-0 group-hover:opacity-100 text-[#8b8d97] hover:text-red-400 transition-all flex-shrink-0 p-0.5"
                      title="Remove"
                    >
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </button>
                ))}
              </div>
            </>
          ) : query.trim() ? (
            <div className="px-4 py-8 text-center">
              <p className="text-xs text-[#8b8d97]">No matches in history</p>
              <p className="text-[10px] text-[#8b8d97] mt-1">Press Enter to search for <strong className="text-white font-mono">{query.toUpperCase()}</strong></p>
            </div>
          ) : (
            <div className="px-4 py-8 text-center">
              <svg className="w-8 h-8 text-[#2a2d3e] mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <p className="text-xs text-[#8b8d97]">No recent searches</p>
              <p className="text-[10px] text-[#8b8d97] mt-1">Type a ticker symbol and press Enter</p>
            </div>
          )}
        </div>

        {/* Footer hint */}
        <div className="px-4 py-2 border-t border-[#2a2d3e] flex items-center gap-4 text-[10px] text-[#8b8d97]">
          <span className="flex items-center gap-1">
            <kbd className="bg-[#0f1117] px-1 py-0.5 rounded border border-[#2a2d3e]">↵</kbd> to search
          </span>
          <span className="flex items-center gap-1">
            <kbd className="bg-[#0f1117] px-1 py-0.5 rounded border border-[#2a2d3e]">esc</kbd> to close
          </span>
        </div>
      </div>
    </div>
  )
}

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'

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

export default function SearchOverlay({ open, onClose, onSearch, allStocks = [], holdingTickers = new Set() }) {
  const [query, setQuery] = useState('')
  const [history, setHistory] = useState([])
  const [highlightIdx, setHighlightIdx] = useState(-1)
  const [yahooResults, setYahooResults] = useState([])
  const [yahooLoading, setYahooLoading] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef(null)
  const overlayRef = useRef(null)
  const dropdownRef = useRef(null)
  const yahooTimerRef = useRef(null)

  // Load history when opening
  useEffect(() => {
    if (open) {
      setHistory(getHistory())
      setQuery('')
      setError('')
      setHighlightIdx(-1)
      setYahooResults([])
      // Focus after animation
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (overlayRef.current && !overlayRef.current.contains(e.target)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open, onClose])

  // --- Local fuzzy search ---
  const localResults = useMemo(() => {
    const term = query.trim().toUpperCase()
    if (!term || !allStocks.length) return []

    const termLower = query.trim().toLowerCase()
    const scored = []

    for (const stock of allStocks) {
      const ticker = (stock.ticker || '').toUpperCase()
      const name = (stock.name || '').toLowerCase()
      let score = 0

      if (ticker === term) score = 1000
      else if (ticker.startsWith(term)) score = 500 - ticker.length
      else if (ticker.includes(term)) score = 200
      else if (name.startsWith(termLower)) score = 150
      else if (name.split(/\s+/).some(w => w.startsWith(termLower))) score = 100
      else if (name.includes(termLower)) score = 50

      if (score > 0) {
        const isHolding = holdingTickers.has(ticker)
        scored.push({ ...stock, _score: score + (isHolding ? 2000 : 0), _isHolding: isHolding })
      }
    }

    scored.sort((a, b) => b._score - a._score)
    return scored.slice(0, 20)
  }, [query, allStocks, holdingTickers])

  const holdingResults = useMemo(() => localResults.filter(r => r._isHolding), [localResults])
  const otherLocalResults = useMemo(() => localResults.filter(r => !r._isHolding), [localResults])

  // --- Yahoo fallback (debounced) ---
  useEffect(() => {
    if (yahooTimerRef.current) clearTimeout(yahooTimerRef.current)

    const term = query.trim()
    if (term.length < 2 || localResults.length >= 3) {
      setYahooResults([])
      setYahooLoading(false)
      return
    }

    setYahooLoading(true)
    yahooTimerRef.current = setTimeout(async () => {
      try {
        const res = await fetch(`/api/search/yahoo?q=${encodeURIComponent(term)}`)
        const data = await res.json()
        const localTickers = new Set(localResults.map(r => r.ticker))
        const filtered = (data.results || []).filter(r => !localTickers.has(r.ticker))
        setYahooResults(filtered.slice(0, 5))
      } catch {
        setYahooResults([])
      } finally {
        setYahooLoading(false)
      }
    }, 300)

    return () => { if (yahooTimerRef.current) clearTimeout(yahooTimerRef.current) }
  }, [query, localResults])

  // All selectable results (for keyboard nav)
  const allResults = useMemo(() => {
    if (!query.trim()) return []
    return [...holdingResults, ...otherLocalResults, ...yahooResults]
  }, [query, holdingResults, otherLocalResults, yahooResults])

  // Reset highlight when results change
  useEffect(() => {
    setHighlightIdx(allResults.length > 0 ? 0 : -1)
  }, [allResults.length, query])

  // Scroll highlighted item into view
  useEffect(() => {
    if (highlightIdx >= 0 && dropdownRef.current) {
      const items = dropdownRef.current.querySelectorAll('[data-result-item]')
      items[highlightIdx]?.scrollIntoView({ block: 'nearest' })
    }
  }, [highlightIdx])

  const handleSelect = useCallback((ticker, name) => {
    addToSearchHistory(ticker, name || ticker)
    onSearch(ticker)
    onClose()
  }, [onSearch, onClose])

  const handleHistoryClick = (ticker) => {
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

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape') {
      onClose()
      return
    }

    if (allResults.length > 0) {
      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault()
          setHighlightIdx(prev => Math.min(prev + 1, allResults.length - 1))
          return
        case 'ArrowUp':
          e.preventDefault()
          setHighlightIdx(prev => Math.max(prev - 1, 0))
          return
        case 'Enter':
          e.preventDefault()
          if (highlightIdx >= 0 && highlightIdx < allResults.length) {
            const item = allResults[highlightIdx]
            handleSelect(item.ticker, item.name)
          } else {
            // No highlight — submit raw query
            const t = query.trim().toUpperCase()
            if (t) handleSelect(t, t)
          }
          return
      }
    } else if (e.key === 'Enter') {
      // No results — submit raw query as ticker
      const t = query.trim().toUpperCase()
      if (t) handleSelect(t, t)
    }
  }, [allResults, highlightIdx, handleSelect, onClose, query])

  if (!open) return null

  const hasQuery = query.trim().length > 0

  const timeAgo = (ts) => {
    const mins = Math.floor((Date.now() - ts) / 60000)
    if (mins < 1) return 'just now'
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    const days = Math.floor(hrs / 24)
    return `${days}d ago`
  }

  const renderRow = (stock, globalIdx) => {
    const isHighlighted = globalIdx === highlightIdx
    return (
      <button
        key={`${stock.ticker}-${globalIdx}`}
        data-result-item
        onClick={() => handleSelect(stock.ticker, stock.name)}
        onMouseEnter={() => setHighlightIdx(globalIdx)}
        className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
          isHighlighted ? 'bg-[#252940]' : 'hover:bg-[#252940]/50'
        }`}
      >
        <span className="text-sm font-mono font-semibold text-blue-400 w-16 flex-shrink-0">
          {stock.ticker}
        </span>
        <span className="text-xs text-[#c4c5c9] flex-1 truncate">
          {stock.name}
        </span>
        <span className="text-[10px] text-[#8b8d97] flex-shrink-0">
          {stock.sector || stock.exchange || stock.market || ''}
        </span>
      </button>
    )
  }

  let globalIdx = 0

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
            onKeyDown={handleKeyDown}
            placeholder="Search by ticker or company name..."
            className="flex-1 bg-transparent text-sm font-mono text-white placeholder-[#8b8d97] focus:outline-none"
            autoComplete="off"
            spellCheck={false}
          />
          {yahooLoading && (
            <div className="w-4 h-4 border-2 border-[#3b82f6] border-t-transparent rounded-full animate-spin flex-shrink-0" />
          )}
          {query && !yahooLoading && (
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

        {/* Results / History */}
        <div ref={dropdownRef} className="max-h-[400px] overflow-y-auto">
          {hasQuery ? (
            /* ── Autocomplete Results ── */
            allResults.length > 0 ? (
              <>
                {/* Holdings section */}
                {holdingResults.length > 0 && (
                  <>
                    <div className="px-4 pt-3 pb-1">
                      <span className="text-[10px] text-[#8b8d97] uppercase tracking-wider font-semibold">
                        Your Holdings
                      </span>
                    </div>
                    {holdingResults.map((stock) => {
                      const row = renderRow(stock, globalIdx)
                      globalIdx++
                      return row
                    })}
                  </>
                )}

                {/* All Stocks section */}
                {otherLocalResults.length > 0 && (
                  <>
                    <div className="px-4 pt-3 pb-1">
                      <span className="text-[10px] text-[#8b8d97] uppercase tracking-wider font-semibold">
                        All Stocks
                      </span>
                    </div>
                    {otherLocalResults.map((stock) => {
                      const row = renderRow(stock, globalIdx)
                      globalIdx++
                      return row
                    })}
                  </>
                )}

                {/* Yahoo results */}
                {yahooResults.length > 0 && (
                  <>
                    <div className="px-4 pt-3 pb-1 flex items-center gap-2">
                      <span className="text-[10px] text-[#8b8d97] uppercase tracking-wider font-semibold">
                        Other Results
                      </span>
                    </div>
                    {yahooResults.map((stock) => {
                      const row = renderRow(stock, globalIdx)
                      globalIdx++
                      return row
                    })}
                  </>
                )}

                {/* Yahoo loading */}
                {yahooLoading && localResults.length < 3 && (
                  <div className="px-4 py-2 flex items-center gap-2">
                    <div className="w-3 h-3 border-2 border-[#3b82f6] border-t-transparent rounded-full animate-spin" />
                    <span className="text-[10px] text-[#8b8d97]">Searching more...</span>
                  </div>
                )}
              </>
            ) : yahooLoading ? (
              <div className="px-4 py-8 text-center">
                <div className="w-5 h-5 border-2 border-[#3b82f6] border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                <p className="text-xs text-[#8b8d97]">Searching...</p>
              </div>
            ) : (
              <div className="px-4 py-8 text-center">
                <p className="text-xs text-[#8b8d97]">No matches found</p>
                <p className="text-[10px] text-[#8b8d97] mt-1">
                  Press Enter to look up <strong className="text-white font-mono">{query.toUpperCase()}</strong>
                </p>
              </div>
            )
          ) : (
            /* ── Recent History (when query is empty) ── */
            history.length > 0 ? (
              <>
                <div className="flex items-center justify-between px-4 pt-3 pb-1">
                  <span className="text-[10px] text-[#8b8d97] uppercase tracking-wider font-semibold">
                    Recent searches
                  </span>
                  <button
                    onClick={clearHistory}
                    className="text-[10px] text-[#8b8d97] hover:text-red-400 transition-colors"
                  >
                    Clear all
                  </button>
                </div>
                <div className="py-1">
                  {history.map(h => (
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
            ) : (
              <div className="px-4 py-8 text-center">
                <svg className="w-8 h-8 text-[#2a2d3e] mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <p className="text-xs text-[#8b8d97]">Search by ticker or company name</p>
                <p className="text-[10px] text-[#8b8d97] mt-1">Type to see suggestions from 6,000+ stocks</p>
              </div>
            )
          )}
        </div>

        {/* Footer hint */}
        <div className="px-4 py-2 border-t border-[#2a2d3e] flex items-center gap-4 text-[10px] text-[#8b8d97]">
          <span className="flex items-center gap-1">
            <kbd className="bg-[#0f1117] px-1 py-0.5 rounded border border-[#2a2d3e]">↑↓</kbd> navigate
          </span>
          <span className="flex items-center gap-1">
            <kbd className="bg-[#0f1117] px-1 py-0.5 rounded border border-[#2a2d3e]">↵</kbd> select
          </span>
          <span className="flex items-center gap-1">
            <kbd className="bg-[#0f1117] px-1 py-0.5 rounded border border-[#2a2d3e]">esc</kbd> close
          </span>
        </div>
      </div>
    </div>
  )
}

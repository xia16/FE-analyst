import { useState, useEffect, useRef, useCallback, useMemo } from 'react'

/**
 * Reusable ticker autocomplete dropdown.
 *
 * Props:
 *   allStocks     — full stock index [{ticker, name, exchange, market, sector, source, type}]
 *   holdings      — Set of tickers in user's portfolio (for "Your Holdings" section)
 *   query         — current search query (controlled)
 *   onSelect      — callback(ticker, name) when user picks a result
 *   onQueryChange — callback(newQuery) to update parent's query state
 *   className     — optional class for the wrapper div
 *   inputRef      — optional ref forwarded to the input element
 *   placeholder   — input placeholder text
 *   showInput     — if false, only renders dropdown (parent owns the input)
 *   open          — if provided, controls dropdown visibility externally
 */
export default function TickerAutocomplete({
  allStocks = [],
  holdings = new Set(),
  query = '',
  onSelect,
  onQueryChange,
  className = '',
  inputRef: externalInputRef,
  placeholder = 'Search by ticker or company name...',
  showInput = true,
  open: externalOpen,
}) {
  const [internalQuery, setInternalQuery] = useState('')
  const [highlightIdx, setHighlightIdx] = useState(-1)
  const [yahooResults, setYahooResults] = useState([])
  const [yahooLoading, setYahooLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(false)
  const internalInputRef = useRef(null)
  const dropdownRef = useRef(null)
  const yahooTimerRef = useRef(null)

  const inputRefToUse = externalInputRef || internalInputRef
  const q = query !== undefined && onQueryChange ? query : internalQuery
  const setQ = onQueryChange || setInternalQuery
  const dropdownVisible = externalOpen !== undefined ? externalOpen && q.trim().length > 0 : isOpen && q.trim().length > 0

  // --- Local fuzzy search with relevance scoring ---
  const localResults = useMemo(() => {
    const term = q.trim().toUpperCase()
    if (!term || !allStocks.length) return []

    const termLower = q.trim().toLowerCase()
    const scored = []

    for (const stock of allStocks) {
      const ticker = (stock.ticker || '').toUpperCase()
      const name = (stock.name || '').toLowerCase()
      let score = 0

      // Exact ticker match → highest
      if (ticker === term) {
        score = 1000
      }
      // Ticker starts with query
      else if (ticker.startsWith(term)) {
        score = 500 - ticker.length  // shorter tickers rank higher
      }
      // Ticker contains query
      else if (ticker.includes(term)) {
        score = 200
      }
      // Name starts with query
      else if (name.startsWith(termLower)) {
        score = 150
      }
      // Name word starts with query
      else if (name.split(/\s+/).some(w => w.startsWith(termLower))) {
        score = 100
      }
      // Name contains query
      else if (name.includes(termLower)) {
        score = 50
      }

      if (score > 0) {
        // Boost holdings
        const isHolding = holdings.has(ticker)
        scored.push({ ...stock, _score: score + (isHolding ? 2000 : 0), _isHolding: isHolding })
      }
    }

    scored.sort((a, b) => b._score - a._score)
    return scored.slice(0, 20)
  }, [q, allStocks, holdings])

  // Split into holdings vs all stocks
  const holdingResults = useMemo(() => localResults.filter(r => r._isHolding), [localResults])
  const otherLocalResults = useMemo(() => localResults.filter(r => !r._isHolding), [localResults])

  // --- Yahoo fallback (debounced) ---
  useEffect(() => {
    if (yahooTimerRef.current) clearTimeout(yahooTimerRef.current)

    const term = q.trim()
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
        // Filter out stocks already in local results
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
  }, [q, localResults])

  // Combined results for keyboard nav
  const allResults = useMemo(() => {
    return [...holdingResults, ...otherLocalResults, ...yahooResults]
  }, [holdingResults, otherLocalResults, yahooResults])

  // Reset highlight when results change
  useEffect(() => {
    setHighlightIdx(allResults.length > 0 ? 0 : -1)
  }, [allResults.length, q])

  // Scroll highlighted item into view
  useEffect(() => {
    if (highlightIdx >= 0 && dropdownRef.current) {
      const items = dropdownRef.current.querySelectorAll('[data-result-item]')
      items[highlightIdx]?.scrollIntoView({ block: 'nearest' })
    }
  }, [highlightIdx])

  const handleSelect = useCallback((ticker, name) => {
    onSelect?.(ticker, name)
    setIsOpen(false)
    setYahooResults([])
  }, [onSelect])

  const handleKeyDown = useCallback((e) => {
    if (!dropdownVisible || allResults.length === 0) {
      if (e.key === 'ArrowDown' && q.trim()) {
        setIsOpen(true)
      }
      return
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setHighlightIdx(prev => Math.min(prev + 1, allResults.length - 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setHighlightIdx(prev => Math.max(prev - 1, 0))
        break
      case 'Enter':
        e.preventDefault()
        if (highlightIdx >= 0 && highlightIdx < allResults.length) {
          const item = allResults[highlightIdx]
          handleSelect(item.ticker, item.name)
        }
        break
      case 'Escape':
        setIsOpen(false)
        break
    }
  }, [dropdownVisible, allResults, highlightIdx, handleSelect, q])

  const renderRow = (stock, idx, globalIdx) => {
    const isHighlighted = globalIdx === highlightIdx
    return (
      <button
        key={`${stock.ticker}-${idx}`}
        data-result-item
        onClick={() => handleSelect(stock.ticker, stock.name)}
        onMouseEnter={() => setHighlightIdx(globalIdx)}
        className={`w-full flex items-center gap-3 px-3 py-2 text-left transition-colors ${
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
    <div className={`relative ${className}`}>
      {showInput && (
        <input
          ref={inputRefToUse}
          value={q}
          onChange={(e) => { setQ(e.target.value); setIsOpen(true) }}
          onKeyDown={handleKeyDown}
          onFocus={() => q.trim() && setIsOpen(true)}
          placeholder={placeholder}
          className="w-full bg-[#1e2130] border border-[#2a2d3e] rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-[#3b82f6] transition-colors"
          autoComplete="off"
          spellCheck={false}
        />
      )}

      {dropdownVisible && allResults.length > 0 && (
        <div
          ref={dropdownRef}
          className="absolute z-50 w-full mt-1 bg-[#1a1d2e] border border-[#2a2d3e] rounded-lg shadow-2xl overflow-hidden max-h-[360px] overflow-y-auto"
        >
          {/* Holdings section */}
          {holdingResults.length > 0 && (
            <>
              <div className="px-3 pt-2.5 pb-1">
                <span className="text-[10px] text-[#8b8d97] uppercase tracking-wider font-semibold">
                  Your Holdings
                </span>
              </div>
              {holdingResults.map((stock, idx) => {
                const row = renderRow(stock, idx, globalIdx)
                globalIdx++
                return row
              })}
            </>
          )}

          {/* All Stocks section */}
          {otherLocalResults.length > 0 && (
            <>
              <div className="px-3 pt-2.5 pb-1">
                <span className="text-[10px] text-[#8b8d97] uppercase tracking-wider font-semibold">
                  All Stocks
                </span>
              </div>
              {otherLocalResults.map((stock, idx) => {
                const row = renderRow(stock, idx, globalIdx)
                globalIdx++
                return row
              })}
            </>
          )}

          {/* Yahoo results section */}
          {yahooResults.length > 0 && (
            <>
              <div className="px-3 pt-2.5 pb-1 flex items-center gap-2">
                <span className="text-[10px] text-[#8b8d97] uppercase tracking-wider font-semibold">
                  Other Results
                </span>
              </div>
              {yahooResults.map((stock, idx) => {
                const row = renderRow(stock, idx, globalIdx)
                globalIdx++
                return row
              })}
            </>
          )}

          {/* Yahoo loading indicator */}
          {yahooLoading && localResults.length < 3 && (
            <div className="px-3 py-2 flex items-center gap-2">
              <div className="w-3 h-3 border-2 border-[#3b82f6] border-t-transparent rounded-full animate-spin" />
              <span className="text-[10px] text-[#8b8d97]">Searching more...</span>
            </div>
          )}

          {/* Footer hint */}
          <div className="px-3 py-1.5 border-t border-[#2a2d3e] flex items-center gap-3 text-[10px] text-[#8b8d97]">
            <span className="flex items-center gap-1">
              <kbd className="bg-[#0f1117] px-1 py-0.5 rounded border border-[#2a2d3e]">↑↓</kbd> navigate
            </span>
            <span className="flex items-center gap-1">
              <kbd className="bg-[#0f1117] px-1 py-0.5 rounded border border-[#2a2d3e]">↵</kbd> select
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

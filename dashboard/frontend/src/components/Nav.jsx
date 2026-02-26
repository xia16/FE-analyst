import { useState, useRef, useEffect } from 'react'

export default function Nav({ activeDomain, setActiveDomain, activeView, setActiveView, alertCount, domains, domainMeta, onSearchOpen }) {
  const [domainOpen, setDomainOpen] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const menuRef = useRef(null)

  const currentDomain = domains?.find(d => d.id === activeDomain)

  // Close mobile menu on outside click
  useEffect(() => {
    if (!mobileMenuOpen) return
    const handler = (e) => { if (menuRef.current && !menuRef.current.contains(e.target)) setMobileMenuOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [mobileMenuOpen])

  // Domain sub-tabs (only shown when a research domain is active and user is in a research view)
  const domainTabs = activeDomain ? [
    { id: 'watchlist', label: 'Watchlist' },
    { id: 'universe', label: domainMeta?.tabLabel || 'Universe' },
    { id: 'heatmap', label: domainMeta?.heatmapLabel || 'Heatmap' },
  ] : []

  // Right-side tool buttons
  const globalTools = [
    { id: 'alerts', label: 'Alerts' },
    { id: 'detail', label: 'Detail' },
    { id: 'generate', label: 'Analyze' },
    { id: 'reports', label: 'Reports' },
  ]

  const isDomainView = ['watchlist', 'universe', 'heatmap'].includes(activeView)
  const isMyPortfolio = activeView === 'myportfolio'

  return (
    <header className="sticky top-0 z-50 bg-[#0f1117]/90 backdrop-blur-md border-b border-[#2a2d3e]">
      <div className="max-w-[1600px] mx-auto px-3 md:px-6">
        {/* Main bar */}
        <div className="flex items-center justify-between h-14">
          {/* Left: Logo + My Portfolio + Domain selector */}
          <div className="flex items-center gap-2 md:gap-3 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-sm font-bold flex-shrink-0">
              FE
            </div>

            {/* My Portfolio — primary left button */}
            <button
              onClick={() => setActiveView('myportfolio')}
              className={`px-3 py-2 rounded-lg text-xs font-semibold transition-colors whitespace-nowrap ${
                isMyPortfolio
                  ? 'bg-[#3b82f6] text-white'
                  : 'text-[#8b8d97] hover:text-white hover:bg-[#1e2130]'
              }`}
            >
              My Portfolio
            </button>

            {/* Separator */}
            <div className="w-px h-5 bg-[#2a2d3e] hidden md:block" />

            {/* Domain selector with "Research:" label */}
            {domains && domains.length > 0 && (
              <div className="relative">
                <button
                  onClick={() => setDomainOpen(!domainOpen)}
                  className={`flex items-center gap-1.5 md:gap-2 px-2 md:px-3 py-2 rounded-lg text-xs font-medium transition-colors min-w-0 ${
                    isDomainView
                      ? 'bg-[#1e2130] text-white border border-[#2a2d3e]'
                      : 'text-[#8b8d97] hover:text-white hover:bg-[#1e2130]'
                  }`}
                >
                  <span className="text-[#8b8d97] font-normal hidden md:inline">Research:</span>
                  {currentDomain && (
                    <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: currentDomain.color }} />
                  )}
                  <span className="truncate max-w-[80px] md:max-w-none">{currentDomain?.name || 'Select Domain'}</span>
                  <svg className="w-3 h-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
                          setActiveView('watchlist')
                          setDomainOpen(false)
                        }}
                        className={`w-full text-left px-3 py-2.5 text-xs flex items-center gap-2 transition-colors ${
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

          {/* Right: Global tools — desktop only (≥768px) */}
          <nav className="hidden md:flex items-center gap-1">
            {/* Search icon */}
            <button
              onClick={onSearchOpen}
              className="p-2 rounded-lg text-[#8b8d97] hover:text-white hover:bg-[#1e2130] transition-colors mr-1"
              title="Search stocks (⌘K)"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </button>
            <div className="w-px h-5 bg-[#2a2d3e]" />
            {globalTools.map(tool => (
              <button
                key={tool.id}
                onClick={() => setActiveView(tool.id)}
                className={`px-3 py-2 rounded-lg text-xs font-medium transition-colors relative ${
                  activeView === tool.id && !isDomainView && !isMyPortfolio
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

          {/* Right: Search + Hamburger — mobile/tablet (<768px) */}
          <div className="md:hidden flex items-center gap-1">
            <button
              onClick={onSearchOpen}
              className="p-2 rounded-lg text-[#8b8d97] hover:text-white hover:bg-[#1e2130] transition-colors"
              title="Search stocks"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </button>
            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="p-2 rounded-lg text-[#8b8d97] hover:text-white hover:bg-[#1e2130] transition-colors relative"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  {mobileMenuOpen ? (
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  ) : (
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  )}
                </svg>
                {alertCount > 0 && !mobileMenuOpen && (
                  <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-red-500" />
                )}
              </button>
              {mobileMenuOpen && (
                <div className="absolute top-full right-0 mt-1 bg-[#1e2130] border border-[#2a2d3e] rounded-lg shadow-xl min-w-[160px] py-1 z-50">
                  {globalTools.map(tool => (
                    <button
                      key={tool.id}
                      onClick={() => { setActiveView(tool.id); setMobileMenuOpen(false) }}
                      className={`w-full text-left px-4 py-3 text-xs font-medium flex items-center justify-between transition-colors ${
                        activeView === tool.id && !isDomainView && !isMyPortfolio
                          ? 'bg-[#252940] text-white'
                          : 'text-[#8b8d97] hover:bg-[#252940] hover:text-white'
                      }`}
                    >
                      {tool.label}
                      {tool.id === 'alerts' && alertCount > 0 && (
                        <span className="w-5 h-5 rounded-full bg-red-500 text-[10px] text-white flex items-center justify-center">
                          {alertCount}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Domain sub-tabs (second row, only when domain active and in research view) */}
        {activeDomain && domainTabs.length > 0 && isDomainView && (
          <div className="flex items-center gap-1 pb-2 -mt-1 overflow-x-auto scrollbar-hide">
            {domainTabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveView(tab.id)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors whitespace-nowrap ${
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

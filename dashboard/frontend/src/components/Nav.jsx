import { useState } from 'react'

export default function Nav({ activeDomain, setActiveDomain, activeView, setActiveView, alertCount, domains, domainMeta }) {
  const [domainOpen, setDomainOpen] = useState(false)

  const currentDomain = domains?.find(d => d.id === activeDomain)

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
      <div className="max-w-[1600px] mx-auto px-4 sm:px-6">
        {/* Main bar */}
        <div className="flex items-center justify-between h-14">
          {/* Left: Logo + My Portfolio + Domain selector */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-sm font-bold">
              FE
            </div>

            {/* My Portfolio — primary left button */}
            <button
              onClick={() => setActiveView('myportfolio')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                isMyPortfolio
                  ? 'bg-[#3b82f6] text-white'
                  : 'text-[#8b8d97] hover:text-white hover:bg-[#1e2130]'
              }`}
            >
              My Portfolio
            </button>

            {/* Separator */}
            <div className="w-px h-5 bg-[#2a2d3e]" />

            {/* Domain selector with "Research:" label */}
            {domains && domains.length > 0 && (
              <div className="relative">
                <button
                  onClick={() => setDomainOpen(!domainOpen)}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    isDomainView
                      ? 'bg-[#1e2130] text-white border border-[#2a2d3e]'
                      : 'text-[#8b8d97] hover:text-white hover:bg-[#1e2130]'
                  }`}
                >
                  <span className="text-[#8b8d97] font-normal">Research:</span>
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
                          setActiveView('watchlist')
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
        </div>

        {/* Domain sub-tabs (second row, only when domain active and in research view) */}
        {activeDomain && domainTabs.length > 0 && isDomainView && (
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

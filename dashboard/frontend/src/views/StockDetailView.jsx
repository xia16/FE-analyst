import { useState, useEffect, useCallback } from 'react'
import { useAnalysis, useThesis, useThesisStatus } from '../hooks'
import { addToSearchHistory } from '../components/SearchOverlay'
import { Card, Badge, Spinner, fmt, fmtPct, fmtCurrency, getScoreColor, RECOMMENDATION_COLORS } from '../components/shared'
import OverviewTab from './stock-detail/OverviewTab'
import TechnicalsTab from './stock-detail/TechnicalsTab'
import FundamentalsTab from './stock-detail/FundamentalsTab'
import ValuationTab from './stock-detail/ValuationTab'
import RiskTab from './stock-detail/RiskTab'
import InsiderTab from './stock-detail/InsiderTab'
import SentimentTab from './stock-detail/SentimentTab'
import ThesisTab from './stock-detail/ThesisTab'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'technicals', label: 'Technicals' },
  { id: 'fundamentals', label: 'Fundamentals' },
  { id: 'valuation', label: 'Valuation' },
  { id: 'risk', label: 'Risk' },
  { id: 'insider', label: 'Insider' },
  { id: 'sentiment', label: 'Sentiment' },
  { id: 'thesis', label: 'Thesis' },
]

export default function StockDetailView({ ticker, setTicker }) {
  const [inputVal, setInputVal] = useState(ticker || '')
  const [activeTab, setActiveTab] = useState('overview')
  const [quoteData, setQuoteData] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [polling, setPolling] = useState(false)

  const { data: analysis, loading: analysisLoading, refetch: refetchAnalysis } = useAnalysis(ticker)
  const { data: thesis, loading: thesisLoading, refetch: refetchThesis } = useThesis(ticker)
  const { data: thesisStatus } = useThesisStatus(ticker, polling)

  // Stop polling when thesis is completed/failed
  useEffect(() => {
    if (thesisStatus?.status === 'completed' || thesisStatus?.status === 'failed') {
      setPolling(false)
      setAnalyzing(false)
      refetchThesis()
    }
  }, [thesisStatus?.status, refetchThesis])

  useEffect(() => {
    if (!ticker) return
    setQuoteData(null)
    fetch(`/api/quote/${ticker}`).then(r => r.json()).then(data => {
      setQuoteData(data)
      // Save to search history
      if (data && !data.error) {
        addToSearchHistory(ticker, data.name || ticker)
      }
    })
  }, [ticker])

  useEffect(() => {
    setInputVal(ticker || '')
  }, [ticker])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (inputVal.trim()) {
      setTicker(inputVal.trim().toUpperCase())
      setActiveTab('overview')
    }
  }

  const triggerAnalysis = useCallback(async () => {
    if (!ticker) return
    setAnalyzing(true)
    setPolling(true)
    try {
      await fetch(`/api/analyze/${ticker}/thesis`, { method: 'POST' })
    } catch (e) {
      setAnalyzing(false)
      setPolling(false)
    }
  }, [ticker])

  const handleAnalyzeClick = async () => {
    // First ensure we have fresh raw metrics
    refetchAnalysis()
    await triggerAnalysis()
    setActiveTab('thesis')
  }

  return (
    <div className="space-y-6 animate-slide-in">
      {/* Search bar */}
      <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-2">
        <input
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          placeholder="Enter ticker (e.g. ATEYY, HTHIY, 8035.T)"
          className="flex-1 bg-[#1e2130] border border-[#2a2d3e] rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-[#3b82f6] transition-colors"
        />
        <button
          type="submit"
          className="px-6 py-2 bg-[#3b82f6] text-white text-sm font-medium rounded-lg hover:bg-[#2563eb] transition-colors"
        >
          Load
        </button>
      </form>

      {!ticker ? (
        <Card>
          <div className="text-center py-12 text-[#8b8d97]">
            <p className="text-lg mb-2">Search</p>
            <p>Enter a ticker symbol above or click on a company from other views.</p>
          </div>
        </Card>
      ) : (
        <>
          {/* Quote header + Analyze button */}
          {quoteData && !quoteData.error && (
            <Card>
              <div className="flex items-center justify-between flex-wrap gap-4">
                <div>
                  <div className="flex items-center gap-3">
                    <h2 className="text-xl font-bold font-mono">{quoteData.ticker}</h2>
                    <span className="text-sm text-[#8b8d97]">{quoteData.name}</span>
                    {analysis?.recommendation && (
                      <Badge color={RECOMMENDATION_COLORS[analysis.recommendation] || '#8b8d97'}>
                        {analysis.recommendation}
                      </Badge>
                    )}
                    {analysis?.composite_score != null && (
                      <span className="text-sm font-bold font-mono" style={{ color: getScoreColor(analysis.composite_score) }}>
                        {fmt(analysis.composite_score, 1)}/100
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-4 mt-1">
                    <span className="text-2xl font-bold">{quoteData.currency === 'JPY' ? '\u00a5' : '$'}{fmt(quoteData.price)}</span>
                    <span className={`text-lg font-semibold ${(quoteData.changePct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {fmtPct(quoteData.changePct)}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                    <div>
                      <div className="text-[#8b8d97]">Market Cap</div>
                      <div className="font-semibold">{fmtCurrency(quoteData.marketCap)}</div>
                    </div>
                    <div>
                      <div className="text-[#8b8d97]">P/E</div>
                      <div className="font-semibold">{fmt(quoteData.trailingPE, 1)}x</div>
                    </div>
                    <div>
                      <div className="text-[#8b8d97]">52W High</div>
                      <div className="font-semibold">{fmt(quoteData.fiftyTwoWeekHigh)}</div>
                    </div>
                    <div>
                      <div className="text-[#8b8d97]">52W Low</div>
                      <div className="font-semibold">{fmt(quoteData.fiftyTwoWeekLow)}</div>
                    </div>
                  </div>
                  <button
                    onClick={handleAnalyzeClick}
                    disabled={analyzing}
                    className="px-4 py-2 bg-gradient-to-r from-[#3b82f6] to-[#8b5cf6] text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 transition-all whitespace-nowrap"
                  >
                    {analyzing ? 'Analyzing...' : 'Analyze'}
                  </button>
                </div>
              </div>
            </Card>
          )}

          {/* Tab bar */}
          <div className="flex gap-1 overflow-x-auto pb-1 scrollbar-hide">
            {TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-3 py-2 rounded-lg text-xs font-medium transition-colors whitespace-nowrap ${
                  activeTab === tab.id
                    ? 'bg-[#3b82f6] text-white'
                    : 'bg-[#1e2130] text-[#8b8d97] hover:text-white hover:bg-[#252940]'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          {analysisLoading && activeTab !== 'technicals' && activeTab !== 'thesis' ? (
            <Spinner />
          ) : (
            <>
              {activeTab === 'overview' && <OverviewTab analysis={analysis} quote={quoteData} />}
              {activeTab === 'technicals' && <TechnicalsTab ticker={ticker} />}
              {activeTab === 'fundamentals' && <FundamentalsTab analysis={analysis} />}
              {activeTab === 'valuation' && <ValuationTab analysis={analysis} thesis={thesis} />}
              {activeTab === 'risk' && <RiskTab analysis={analysis} />}
              {activeTab === 'insider' && <InsiderTab analysis={analysis} />}
              {activeTab === 'sentiment' && <SentimentTab analysis={analysis} />}
              {activeTab === 'thesis' && (
                <ThesisTab
                  ticker={ticker}
                  thesis={thesis}
                  thesisStatus={thesisStatus}
                  onTriggerAnalysis={triggerAnalysis}
                />
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}

import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Card, Badge, Spinner, StatusBadge, RECOMMENDATION_COLORS } from '../../components/shared'

export default function ThesisTab({ ticker, thesis, thesisStatus, onTriggerAnalysis }) {
  const [polling, setPolling] = useState(false)

  const status = thesisStatus?.status || thesis?.status || 'none'
  const data = thesis?.thesis || {}
  const hasThesis = status === 'completed' && data && (data.markdown || Object.keys(data).length > 0) && !data.error

  useEffect(() => {
    if (status === 'pending' || status === 'running') {
      setPolling(true)
    } else {
      setPolling(false)
    }
  }, [status])

  const handleAnalyze = async () => {
    setPolling(true)
    await onTriggerAnalysis()
  }

  if (status === 'pending' || status === 'running') {
    return (
      <Card className="text-center py-12">
        <Spinner />
        <div className="text-sm text-[#8b8d97] mt-4">
          {status === 'pending' ? 'Analysis queued...' : 'Claude Code is analyzing...'}
        </div>
        <div className="text-[10px] text-[#8b8d97] mt-1">This may take 2-5 minutes</div>
      </Card>
    )
  }

  if (!hasThesis) {
    return (
      <Card className="text-center py-12">
        <div className="text-lg text-[#8b8d97] mb-2">No Analysis Yet</div>
        <p className="text-xs text-[#8b8d97] mb-6">
          Click "Analyze" to trigger a Claude Code session that will generate a full investment thesis.
        </p>
        <button
          onClick={handleAnalyze}
          className="px-6 py-2.5 bg-[#3b82f6] text-white text-sm font-medium rounded-lg hover:bg-[#2563eb] transition-colors"
        >
          Generate Investment Thesis
        </button>
      </Card>
    )
  }

  // Handle raw text fallback
  if (data.raw_text) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <StatusBadge status="completed" />
            {thesis?.created_at && (
              <span className="text-[10px] text-[#8b8d97]">
                {new Date(thesis.created_at).toLocaleString()}
              </span>
            )}
          </div>
          <button
            onClick={handleAnalyze}
            className="px-3 py-1 bg-[#252940] text-[#8b8d97] text-xs rounded hover:text-white transition-colors"
          >
            Re-analyze
          </button>
        </div>
        <Card>
          <div className="prose prose-invert prose-sm max-w-none whitespace-pre-wrap text-xs">
            {data.raw_text}
          </div>
        </Card>
      </div>
    )
  }

  // Detect format: new markdown vs old structured JSON
  const isMarkdown = !!data.markdown

  if (isMarkdown) {
    return (
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {data.recommendation && (
              <span className="text-lg font-bold" style={{ color: RECOMMENDATION_COLORS[data.recommendation] || '#3b82f6' }}>
                {data.recommendation}
              </span>
            )}
            {data.conviction && (
              <Badge color={data.conviction === 'HIGH' ? '#22c55e' : data.conviction === 'LOW' ? '#ef4444' : '#eab308'}>
                {data.conviction} conviction
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-3">
            {thesis?.created_at && (
              <span className="text-[10px] text-[#8b8d97]">
                {new Date(thesis.created_at).toLocaleString()}
              </span>
            )}
            <button onClick={handleAnalyze} className="px-3 py-1 bg-[#252940] text-[#8b8d97] text-xs rounded hover:text-white transition-colors">
              Re-analyze
            </button>
          </div>
        </div>

        {/* Markdown content */}
        <Card>
          <div className="prose prose-invert prose-sm max-w-none
            prose-headings:text-white prose-headings:font-semibold
            prose-h2:text-base prose-h2:mt-6 prose-h2:mb-3 prose-h2:border-b prose-h2:border-[#2a2d3e] prose-h2:pb-2
            prose-h3:text-sm prose-h3:mt-4 prose-h3:mb-2
            prose-p:text-[#c8c9ce] prose-p:text-xs prose-p:leading-relaxed
            prose-li:text-[#c8c9ce] prose-li:text-xs
            prose-strong:text-white
            prose-a:text-blue-400
            prose-table:text-xs
            prose-th:text-[#8b8d97] prose-th:font-medium prose-th:text-left prose-th:p-2 prose-th:border-b prose-th:border-[#2a2d3e]
            prose-td:text-[#c8c9ce] prose-td:p-2 prose-td:border-b prose-td:border-[#1a1d2e]
            prose-code:text-blue-300 prose-code:bg-[#1a1d2e] prose-code:px-1 prose-code:rounded
          ">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {data.markdown}
            </ReactMarkdown>
          </div>
        </Card>
      </div>
    )
  }

  // OLD structured JSON rendering (backward compatibility)
  return (
    <div className="space-y-6">
      {/* Header with status and re-analyze */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {data.recommendation && (
            <span className="text-lg font-bold" style={{ color: RECOMMENDATION_COLORS[data.recommendation] || '#3b82f6' }}>
              {data.recommendation}
            </span>
          )}
          {data.conviction && (
            <Badge color={data.conviction === 'HIGH' ? '#22c55e' : data.conviction === 'LOW' ? '#ef4444' : '#eab308'}>
              {data.conviction} conviction
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-3">
          {thesis?.created_at && (
            <span className="text-[10px] text-[#8b8d97]">
              {new Date(thesis.created_at).toLocaleString()}
            </span>
          )}
          <button
            onClick={handleAnalyze}
            className="px-3 py-1 bg-[#252940] text-[#8b8d97] text-xs rounded hover:text-white transition-colors"
          >
            Re-analyze
          </button>
        </div>
      </div>

      {/* Executive Summary */}
      {data.executive_summary && (
        <Card>
          <h3 className="text-sm font-semibold mb-2">Executive Summary</h3>
          <p className="text-xs text-[#c8c9ce] leading-relaxed">{data.executive_summary}</p>
        </Card>
      )}

      {/* Bull/Bear Cases */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {data.bull_case && (
          <Card className="border-l-4" style={{ borderLeftColor: '#22c55e' }}>
            <h3 className="text-sm font-semibold text-green-400 mb-3">Bull Case</h3>
            <ul className="space-y-2">
              {(Array.isArray(data.bull_case) ? data.bull_case : [data.bull_case]).map((point, i) => (
                <li key={i} className="flex items-start gap-2 text-xs">
                  <span className="text-green-400 mt-0.5 flex-shrink-0">{'\u25B2'}</span>
                  <span className="text-[#c8c9ce]">{point}</span>
                </li>
              ))}
            </ul>
          </Card>
        )}
        {data.bear_case && (
          <Card className="border-l-4" style={{ borderLeftColor: '#ef4444' }}>
            <h3 className="text-sm font-semibold text-red-400 mb-3">Bear Case</h3>
            <ul className="space-y-2">
              {(Array.isArray(data.bear_case) ? data.bear_case : [data.bear_case]).map((point, i) => (
                <li key={i} className="flex items-start gap-2 text-xs">
                  <span className="text-red-400 mt-0.5 flex-shrink-0">{'\u25BC'}</span>
                  <span className="text-[#c8c9ce]">{point}</span>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>

      {/* Competitive Positioning */}
      {data.competitive_positioning && (
        <Card>
          <h3 className="text-sm font-semibold mb-2">Competitive Positioning</h3>
          <p className="text-xs text-[#c8c9ce] leading-relaxed">{data.competitive_positioning}</p>
        </Card>
      )}

      {/* Valuation Assessment */}
      {data.valuation_assessment && (
        <Card>
          <h3 className="text-sm font-semibold mb-2">Valuation Assessment</h3>
          <p className="text-xs text-[#c8c9ce] leading-relaxed">{data.valuation_assessment}</p>
        </Card>
      )}

      {/* Fair Value Range */}
      {data.fair_value_range && (
        <Card>
          <h3 className="text-sm font-semibold mb-3">Fair Value Range</h3>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div className="p-3 rounded-lg bg-[#ef444410] border border-[#ef444430]">
              <div className="text-[10px] text-[#8b8d97] mb-1">BEAR</div>
              <div className="text-lg font-bold font-mono text-red-400">
                ${typeof data.fair_value_range.bear === 'object' ? data.fair_value_range.bear.price : data.fair_value_range.bear}
              </div>
            </div>
            <div className="p-3 rounded-lg bg-[#3b82f610] border border-[#3b82f630]">
              <div className="text-[10px] text-[#8b8d97] mb-1">BASE</div>
              <div className="text-lg font-bold font-mono text-blue-400">
                ${typeof data.fair_value_range.base === 'object' ? data.fair_value_range.base.price : data.fair_value_range.base}
              </div>
            </div>
            <div className="p-3 rounded-lg bg-[#22c55e10] border border-[#22c55e30]">
              <div className="text-[10px] text-[#8b8d97] mb-1">BULL</div>
              <div className="text-lg font-bold font-mono text-green-400">
                ${typeof data.fair_value_range.bull === 'object' ? data.fair_value_range.bull.price : data.fair_value_range.bull}
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Market Mispricing */}
      {data.market_mispricing && (
        <Card className="border-l-4" style={{ borderLeftColor: '#a855f7' }}>
          <h3 className="text-sm font-semibold text-purple-400 mb-2">Why the Market Is Wrong</h3>
          <p className="text-xs text-[#c8c9ce] leading-relaxed">{data.market_mispricing}</p>
        </Card>
      )}

      {/* Position Sizing + Institutional Signal */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {data.position_sizing && (
          <Card>
            <h3 className="text-sm font-semibold mb-3">Position Sizing</h3>
            <div className="text-center mb-3">
              <Badge color={data.position_sizing === 'FULL' ? '#22c55e' : data.position_sizing === 'MEDIUM' ? '#eab308' : '#3b82f6'}>
                {data.position_sizing}
              </Badge>
            </div>
            {data.position_sizing_rationale && (
              <p className="text-xs text-[#8b8d97] leading-relaxed">{data.position_sizing_rationale}</p>
            )}
          </Card>
        )}
        {data.institutional_signal && (
          <Card>
            <h3 className="text-sm font-semibold mb-2">Institutional Signal</h3>
            <p className="text-xs text-[#c8c9ce] leading-relaxed">{data.institutional_signal}</p>
          </Card>
        )}
      </div>

      {/* Risk Factors */}
      {data.risk_factors && (
        <Card>
          <h3 className="text-sm font-semibold mb-3">Key Risk Factors</h3>
          <div className="space-y-2">
            {(Array.isArray(data.risk_factors) ? data.risk_factors : []).map((rf, i) => (
              <div key={i} className="p-2 rounded-lg bg-[#0f1117] flex items-start gap-3">
                <span className="text-red-400 font-bold text-xs mt-0.5">{i + 1}</span>
                <div className="flex-1">
                  <div className="text-xs font-semibold">{typeof rf === 'string' ? rf : rf.risk}</div>
                  {typeof rf === 'object' && (
                    <>
                      <div className="flex gap-3 mt-1 text-[10px] text-[#8b8d97]">
                        {rf.probability && <span>Probability: <strong>{rf.probability}</strong></span>}
                        {rf.impact && <span>Impact: <strong>{rf.impact}</strong></span>}
                      </div>
                      {rf.mitigation && (
                        <div className="mt-1 text-[10px] text-[#8b8d97]">
                          Mitigation: <span className="text-[#c8c9ce]">{rf.mitigation}</span>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Catalyst Timeline */}
      {data.catalyst_timeline && (
        <Card>
          <h3 className="text-sm font-semibold mb-3">Catalyst Timeline</h3>
          <div className="space-y-2">
            {(Array.isArray(data.catalyst_timeline) ? data.catalyst_timeline : []).map((c, i) => (
              <div key={i} className="flex items-start gap-3 text-xs p-2 rounded-lg bg-[#0f1117]">
                <div className="w-1.5 h-1.5 rounded-full bg-blue-400 flex-shrink-0 mt-1.5" />
                <div className="flex-1">
                  {typeof c === 'string' ? (
                    <span className="text-[#c8c9ce]">{c}</span>
                  ) : (
                    <>
                      <div className="flex items-center gap-2">
                        {c.date && <span className="text-blue-400 font-mono text-[10px]">{c.date}</span>}
                        <span className="text-[#c8c9ce] font-medium">{c.event}</span>
                      </div>
                      {c.expected_impact && (
                        <div className="text-[10px] text-[#8b8d97] mt-0.5">Impact: {c.expected_impact}</div>
                      )}
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Key Metrics to Watch */}
      {data.key_metrics_to_watch && (
        <Card>
          <h3 className="text-sm font-semibold mb-3">Key Metrics to Watch</h3>
          <div className="space-y-1.5">
            {(Array.isArray(data.key_metrics_to_watch) ? data.key_metrics_to_watch : [data.key_metrics_to_watch]).map((m, i) => (
              <div key={i} className="flex items-start gap-2 text-xs">
                <span className="text-yellow-400 mt-0.5 flex-shrink-0">&#9679;</span>
                <span className="text-[#c8c9ce]">{typeof m === 'string' ? m : m.metric || JSON.stringify(m)}</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

import { Card, Badge, ScoreBar, fmt, fmtPct, fmtCurrency, getScoreColor, SIGNAL_COLORS, RECOMMENDATION_COLORS } from '../../components/shared'

function ConvictionBadge({ conviction }) {
  if (!conviction || conviction.score == null) return null
  const color = conviction.level === 'HIGH' ? '#22c55e' : conviction.level === 'MEDIUM' ? '#eab308' : '#ef4444'
  return (
    <div className="flex flex-col items-center">
      <div className="relative w-16 h-16 flex items-center justify-center">
        <svg className="absolute inset-0" viewBox="0 0 64 64">
          <circle cx="32" cy="32" r="28" fill="none" stroke="#2a2d3e" strokeWidth="3" />
          <circle cx="32" cy="32" r="28" fill="none" stroke={color} strokeWidth="3"
            strokeDasharray={`${conviction.score * 1.76} 176`}
            strokeLinecap="round"
            transform="rotate(-90 32 32)" />
        </svg>
        <span className="text-lg font-bold font-mono" style={{ color }}>{Math.round(conviction.score)}</span>
      </div>
      <Badge color={color}>{conviction.level}</Badge>
    </div>
  )
}

export default function OverviewTab({ analysis, quote }) {
  if (!analysis) return <div className="text-[#8b8d97] text-center py-8">No analysis data. Click "Analyze" to run.</div>
  if (analysis.error) return <div className="text-red-400 text-center py-8">Error: {analysis.error}</div>

  const scores = analysis.component_scores || {}
  const rec = analysis.recommendation
  const composite = analysis.composite_score
  const conviction = analysis.conviction || {}

  const moat = analysis.moat || {}
  const insider = analysis.insider_congress || {}
  const profile = analysis.profile || {}
  const moatScore = moat.composite_moat_score ?? moat.score
  const moatType = moat.moat_classification || moat.moat_type
  const moatDimensions = moat.dimension_scores || moat.dimensions

  // Quick summary from key scores
  const dcfData = analysis.details?.valuation?.dcf || {}
  const piotroski = analysis.details?.fundamental?.piotroski || {}
  const earningsQuality = analysis.details?.fundamental?.earnings_quality || {}

  return (
    <div className="space-y-6">
      {/* Score + Recommendation + Conviction header */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="text-center">
          <div className="text-[#8b8d97] text-xs mb-1">Composite Score</div>
          <div className="text-4xl font-bold font-mono" style={{ color: getScoreColor(composite) }}>
            {fmt(composite, 1)}
          </div>
          <div className="text-xs text-[#8b8d97]">/ 100</div>
        </Card>
        <Card className="text-center">
          <div className="text-[#8b8d97] text-xs mb-1">Recommendation</div>
          <div className="text-2xl font-bold" style={{ color: RECOMMENDATION_COLORS[rec] || '#8b8d97' }}>
            {rec || 'N/A'}
          </div>
        </Card>
        <Card className="text-center">
          <div className="text-[#8b8d97] text-xs mb-1">Insider Signal</div>
          <div className="text-2xl font-bold" style={{ color: SIGNAL_COLORS[insider.signal] || '#8b8d97' }}>
            {insider.signal || 'N/A'}
          </div>
          <div className="text-[10px] text-[#8b8d97] mt-1">
            {insider.total_buys || 0} buys / {insider.total_sells || 0} sells
          </div>
        </Card>
        {/* Conviction Meta-Score */}
        <Card className="flex flex-col items-center justify-center">
          <div className="text-[#8b8d97] text-xs mb-2">Conviction</div>
          <ConvictionBadge conviction={conviction} />
          {conviction.bullish_dimensions != null && (
            <div className="text-[10px] text-[#8b8d97] mt-2">
              {conviction.bullish_dimensions} bullish / {conviction.bearish_dimensions} bearish
            </div>
          )}
        </Card>
      </div>

      {/* Conviction Boosters */}
      {conviction.boosters && conviction.boosters.length > 0 && (
        <Card>
          <h3 className="text-sm font-semibold mb-2">Conviction Boosters</h3>
          <div className="flex flex-wrap gap-2">
            {conviction.boosters.map((b, i) => (
              <div key={i} className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full bg-[#22c55e10] border border-[#22c55e30]">
                <span className="text-green-400">{'\u2191'}</span>
                <span>{b}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Quick Key Metrics Summary */}
      <Card>
        <h3 className="text-sm font-semibold mb-3">Key Metrics at a Glance</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          {dcfData.margin_of_safety_pct != null && (
            <div>
              <div className="text-[#8b8d97]">DCF Margin of Safety</div>
              <div className={`font-bold font-mono text-lg ${dcfData.margin_of_safety_pct > 0 ? 'text-green-400' : 'text-red-400'}`}>
                {fmt(dcfData.margin_of_safety_pct, 1)}%
              </div>
            </div>
          )}
          {piotroski.score != null && (
            <div>
              <div className="text-[#8b8d97]">Piotroski F-Score</div>
              <div className="font-bold font-mono text-lg" style={{ color: getScoreColor(piotroski.score / 9 * 100) }}>
                {piotroski.score}/9
              </div>
              {piotroski.signal && (
                <Badge color={piotroski.signal === 'STRONG' ? '#22c55e' : piotroski.signal === 'MODERATE' ? '#eab308' : '#ef4444'}>
                  {piotroski.signal}
                </Badge>
              )}
            </div>
          )}
          {earningsQuality.assessment && earningsQuality.assessment !== 'N/A' && (
            <div>
              <div className="text-[#8b8d97]">Earnings Quality</div>
              <div className="font-bold text-sm mt-1">
                <Badge color={earningsQuality.score >= 2 ? '#22c55e' : earningsQuality.score >= 1 ? '#eab308' : '#ef4444'}>
                  {earningsQuality.score}/{earningsQuality.max_score}
                </Badge>
              </div>
              {earningsQuality.fcf_ni_ratio != null && (
                <div className="text-[10px] text-[#8b8d97] mt-1">FCF/NI: {fmt(earningsQuality.fcf_ni_ratio, 2)}x</div>
              )}
            </div>
          )}
          {dcfData.risk_reward_ratio != null && (
            <div>
              <div className="text-[#8b8d97]">Risk/Reward</div>
              <div className={`font-bold font-mono text-lg ${dcfData.risk_reward_ratio > 1.5 ? 'text-green-400' : dcfData.risk_reward_ratio > 1 ? 'text-yellow-400' : 'text-red-400'}`}>
                {fmt(dcfData.risk_reward_ratio, 2)}x
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Component scores */}
      <Card>
        <h3 className="text-sm font-semibold mb-4">Component Scores</h3>
        <div className="space-y-3">
          <ScoreBar label="Fundamental (30%)" score={scores.fundamental || 0} />
          <ScoreBar label="Valuation (25%)" score={scores.valuation || 0} />
          <ScoreBar label="Technical (20%)" score={scores.technical || 0} />
          <ScoreBar label="Risk (15%)" score={scores.risk || 0} />
          <ScoreBar label="Sentiment (10%)" score={scores.sentiment || 0} />
        </div>
      </Card>

      {/* Moat + Profile grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {moat && !moat.error && moatScore != null && (
          <Card>
            <h3 className="text-sm font-semibold mb-3">Moat Analysis</h3>
            <div className="flex items-center gap-3 mb-3">
              <div className="text-2xl font-bold font-mono" style={{ color: getScoreColor(moatScore) }}>
                {fmt(moatScore, 0)}
              </div>
              <div className="text-xs text-[#8b8d97]">/ 100</div>
              {moatType && <Badge color={getScoreColor(moatScore)}>{moatType}</Badge>}
            </div>
            {moatDimensions && (
              <div className="space-y-1.5">
                {Object.entries(moatDimensions).map(([k, v]) => (
                  <div key={k} className="flex items-center gap-2">
                    <span className="text-[10px] text-[#8b8d97] w-32 truncate">{k.replace(/_/g, ' ')}</span>
                    <div className="flex-1 h-1.5 bg-[#0f1117] rounded-full overflow-hidden">
                      <div className="h-full rounded-full" style={{
                        width: `${v}%`, background: getScoreColor(v)
                      }} />
                    </div>
                    <span className="text-[10px] font-mono w-6 text-right">{v}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}

        {profile && !profile.error && (
          <Card>
            <h3 className="text-sm font-semibold mb-3">Company Profile</h3>
            <div className="space-y-2 text-xs">
              {profile.sector && (
                <div className="flex justify-between">
                  <span className="text-[#8b8d97]">Sector</span>
                  <span>{profile.sector}</span>
                </div>
              )}
              {profile.industry && (
                <div className="flex justify-between">
                  <span className="text-[#8b8d97]">Industry</span>
                  <span>{profile.industry}</span>
                </div>
              )}
              {profile.country && (
                <div className="flex justify-between">
                  <span className="text-[#8b8d97]">Country</span>
                  <span>{profile.country}</span>
                </div>
              )}
              {profile.market_cap && (
                <div className="flex justify-between">
                  <span className="text-[#8b8d97]">Market Cap</span>
                  <span>{fmtCurrency(profile.market_cap)}</span>
                </div>
              )}
              {profile.employees && (
                <div className="flex justify-between">
                  <span className="text-[#8b8d97]">Employees</span>
                  <span>{Number(profile.employees).toLocaleString()}</span>
                </div>
              )}
              {profile.exchange && (
                <div className="flex justify-between">
                  <span className="text-[#8b8d97]">Exchange</span>
                  <span>{profile.exchange}</span>
                </div>
              )}
              {profile.currency && (
                <div className="flex justify-between">
                  <span className="text-[#8b8d97]">Currency</span>
                  <span>{profile.currency}</span>
                </div>
              )}
              {/* ADR Premium / International */}
              {profile.is_adr && (
                <div className="mt-2 p-2 rounded bg-[#3b82f610] border border-[#3b82f630] space-y-1">
                  <div className="text-[10px] text-blue-400 font-semibold uppercase tracking-wider">ADR Information</div>
                  {profile.adr_premium != null && (
                    <div className="flex justify-between">
                      <span className="text-[#8b8d97]">ADR Premium</span>
                      <span className={`font-mono ${profile.adr_premium > 5 ? 'text-red-400' : profile.adr_premium < -5 ? 'text-green-400' : ''}`}>
                        {fmt(profile.adr_premium, 1)}%
                      </span>
                    </div>
                  )}
                  {profile.underlying_ticker && (
                    <div className="flex justify-between">
                      <span className="text-[#8b8d97]">Underlying</span>
                      <span>{profile.underlying_ticker}</span>
                    </div>
                  )}
                  {profile.adr_ratio && (
                    <div className="flex justify-between">
                      <span className="text-[#8b8d97]">ADR Ratio</span>
                      <span>{profile.adr_ratio}</span>
                    </div>
                  )}
                </div>
              )}
              {profile.description && (
                <p className="text-[10px] text-[#8b8d97] mt-2 line-clamp-4">{profile.description}</p>
              )}
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}

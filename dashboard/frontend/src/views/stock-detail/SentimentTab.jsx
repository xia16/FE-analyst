import { Card, Badge, fmt, getScoreColor } from '../../components/shared'

export default function SentimentTab({ analysis }) {
  const sent = analysis?.details?.sentiment
  if (!sent) return <div className="text-[#8b8d97] text-center py-8">No sentiment data available.</div>

  const score = analysis?.component_scores?.sentiment || 50
  const overall = sent.overall_score || 0
  const label = sent.overall_label || (overall > 0.1 ? 'BULLISH' : overall < -0.1 ? 'BEARISH' : 'NEUTRAL')
  const raw = sent.raw_data || {}
  const news = raw.news || sent.news_items || sent.headlines || []
  const analystRecs = raw.analyst_recommendations || []
  const sourceCounts = sent.source_counts || {}

  // Compute analyst consensus from most recent period
  const latestRec = analystRecs.length > 0 ? analystRecs[0] : null
  let analystLabel = null
  if (latestRec) {
    const { strongBuy = 0, buy = 0, hold = 0, sell = 0, strongSell = 0 } = latestRec
    const total = strongBuy + buy + hold + sell + strongSell
    if (total > 0) {
      if (strongBuy + buy > total * 0.6) analystLabel = 'BUY'
      else if (sell + strongSell > total * 0.4) analystLabel = 'SELL'
      else analystLabel = 'HOLD'
    }
  }

  return (
    <div className="space-y-6">
      {/* Sentiment overview */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <Card className="text-center">
          <div className="text-[#8b8d97] text-xs mb-1">Sentiment Score</div>
          <div className="text-3xl font-bold font-mono" style={{ color: getScoreColor(score) }}>
            {fmt(score, 1)}
          </div>
          <div className="text-[10px] text-[#8b8d97]">/ 100</div>
        </Card>
        <Card className="text-center">
          <div className="text-[#8b8d97] text-xs mb-1">Overall Sentiment</div>
          <div className={`text-2xl font-bold ${overall > 0 ? 'text-green-400' : overall < 0 ? 'text-red-400' : 'text-yellow-400'}`}>
            {label}
          </div>
          <div className="text-[10px] text-[#8b8d97]">score: {fmt(overall, 3)}</div>
        </Card>
        {latestRec && (
          <Card className="text-center">
            <div className="text-[#8b8d97] text-xs mb-1">Analyst Consensus</div>
            <div className="text-2xl font-bold">{analystLabel || '\u2014'}</div>
            <div className="text-[10px] text-[#8b8d97] mt-1">
              {latestRec.strongBuy + latestRec.buy}B / {latestRec.hold}H / {latestRec.sell + latestRec.strongSell}S
            </div>
          </Card>
        )}
      </div>

      {/* Analyst recommendations breakdown */}
      {analystRecs.length > 0 && (
        <Card>
          <h3 className="text-sm font-semibold mb-3">Analyst Recommendations</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-[#a0a2ab] border-b border-[#2a2d3e] text-[10px] uppercase tracking-wider">
                  <th className="text-left py-2 pr-2 font-semibold">Period</th>
                  <th className="text-center py-2 pr-2 font-semibold text-green-400">Strong Buy</th>
                  <th className="text-center py-2 pr-2 font-semibold text-green-300">Buy</th>
                  <th className="text-center py-2 pr-2 font-semibold text-yellow-400">Hold</th>
                  <th className="text-center py-2 pr-2 font-semibold text-red-300">Sell</th>
                  <th className="text-center py-2 font-semibold text-red-400">Strong Sell</th>
                </tr>
              </thead>
              <tbody>
                {analystRecs.map((r, i) => (
                  <tr key={i} className="border-b border-[#2a2d3e]/30">
                    <td className="py-1.5 pr-2 text-[#8b8d97]">{r.period || `Period ${i}`}</td>
                    <td className="py-1.5 pr-2 text-center font-mono text-green-400">{r.strongBuy || 0}</td>
                    <td className="py-1.5 pr-2 text-center font-mono text-green-300">{r.buy || 0}</td>
                    <td className="py-1.5 pr-2 text-center font-mono text-yellow-400">{r.hold || 0}</td>
                    <td className="py-1.5 pr-2 text-center font-mono text-red-300">{r.sell || 0}</td>
                    <td className="py-1.5 text-center font-mono text-red-400">{r.strongSell || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Source counts */}
      {Object.keys(sourceCounts).length > 0 && (
        <Card>
          <h3 className="text-sm font-semibold mb-3">Data Sources</h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {Object.entries(sourceCounts).map(([source, count]) => (
              <div key={source} className="p-3 rounded-lg bg-[#0f1117] text-center">
                <div className="text-lg font-bold font-mono">{count}</div>
                <div className="text-[10px] text-[#8b8d97]">{source.replace(/_/g, ' ')}</div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* News / Headlines */}
      {news.length > 0 && (
        <Card>
          <h3 className="text-sm font-semibold mb-3">Recent Headlines ({news.length})</h3>
          <div className="space-y-2">
            {news.slice(0, 15).map((item, i) => {
              const headline = typeof item === 'string' ? item : item.headline || item.title || ''
              const summary = typeof item === 'object' ? item.summary : null
              return (
                <div key={i} className="p-2 rounded-lg bg-[#0f1117]">
                  <div className="text-xs font-medium">{headline}</div>
                  {summary && <div className="text-[10px] text-[#8b8d97] mt-1 line-clamp-2">{summary}</div>}
                </div>
              )
            })}
          </div>
        </Card>
      )}
    </div>
  )
}

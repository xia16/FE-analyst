import { Card, Badge, ScoreBar, fmt, fmtPct, getScoreColor } from '../../components/shared'

export default function RiskTab({ analysis }) {
  const risk = analysis?.details?.risk
  if (!risk) return <div className="text-[#8b8d97] text-center py-8">No risk data available.</div>

  const riskScore = analysis?.component_scores?.risk || 50

  return (
    <div className="space-y-6">
      {/* Risk overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="text-center">
          <div className="text-[#8b8d97] text-xs mb-1">Risk Score</div>
          <div className="text-3xl font-bold font-mono" style={{ color: getScoreColor(riskScore) }}>
            {fmt(riskScore, 1)}
          </div>
          <div className="text-[10px] text-[#8b8d97]">higher = less risky</div>
        </Card>
        <Card className="text-center">
          <div className="text-[#8b8d97] text-xs mb-1">Volatility</div>
          <div className={`text-2xl font-bold font-mono ${(risk.volatility || 0) > 0.4 ? 'text-red-400' : (risk.volatility || 0) > 0.25 ? 'text-yellow-400' : 'text-green-400'}`}>
            {fmt((risk.volatility || 0) * 100, 1)}%
          </div>
          <div className="text-[10px] text-[#8b8d97]">annualized</div>
        </Card>
        <Card className="text-center">
          <div className="text-[#8b8d97] text-xs mb-1">Beta</div>
          <div className={`text-2xl font-bold font-mono ${(risk.beta || 1) > 1.3 ? 'text-red-400' : (risk.beta || 1) < 0.7 ? 'text-blue-400' : 'text-white'}`}>
            {fmt(risk.beta, 2)}
          </div>
          <div className="text-[10px] text-[#8b8d97]">vs S&P 500</div>
        </Card>
        <Card className="text-center">
          <div className="text-[#8b8d97] text-xs mb-1">Max Drawdown</div>
          <div className="text-2xl font-bold font-mono text-red-400">
            {fmt((risk.max_drawdown || 0) * 100, 1)}%
          </div>
        </Card>
      </div>

      {/* Detailed metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <h3 className="text-sm font-semibold mb-3">Return Metrics</h3>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-[#2a2d3e]/30">
              <span className="text-[#8b8d97]">Sharpe Ratio</span>
              <span className={`font-bold font-mono ${(risk.sharpe_ratio || 0) > 1 ? 'text-green-400' : (risk.sharpe_ratio || 0) > 0 ? 'text-yellow-400' : 'text-red-400'}`}>
                {fmt(risk.sharpe_ratio, 2)}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#2a2d3e]/30">
              <span className="text-[#8b8d97]">Sortino Ratio</span>
              <span className={`font-bold font-mono ${(risk.sortino_ratio || 0) > 1.5 ? 'text-green-400' : (risk.sortino_ratio || 0) > 0 ? 'text-yellow-400' : 'text-red-400'}`}>
                {fmt(risk.sortino_ratio, 2)}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#2a2d3e]/30">
              <span className="text-[#8b8d97]">Information Ratio</span>
              <span className="font-bold font-mono">{fmt(risk.information_ratio, 2)}</span>
            </div>
          </div>
        </Card>

        <Card>
          <h3 className="text-sm font-semibold mb-3">Value at Risk</h3>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-[#2a2d3e]/30">
              <span className="text-[#8b8d97]">VaR (95%)</span>
              <span className="font-bold font-mono text-red-400">{fmt((risk.var_95 || 0) * 100, 2)}%</span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#2a2d3e]/30">
              <span className="text-[#8b8d97]">CVaR (95%)</span>
              <span className="font-bold font-mono text-red-400">{fmt((risk.cvar_95 || 0) * 100, 2)}%</span>
            </div>
            <div className="mt-2 text-[10px] text-[#8b8d97]">
              VaR: Maximum expected daily loss with 95% confidence.
              CVaR: Average loss when VaR threshold is breached.
            </div>
          </div>
        </Card>
      </div>

      {/* Risk level interpretation */}
      <Card>
        <h3 className="text-sm font-semibold mb-3">Risk Assessment</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-3 rounded-lg bg-[#0f1117]">
            <div className="text-xs text-[#8b8d97] mb-1">Volatility Level</div>
            <Badge color={(risk.volatility || 0) > 0.4 ? '#ef4444' : (risk.volatility || 0) > 0.25 ? '#eab308' : '#22c55e'}>
              {(risk.volatility || 0) > 0.4 ? 'HIGH' : (risk.volatility || 0) > 0.25 ? 'MEDIUM' : 'LOW'}
            </Badge>
          </div>
          <div className="p-3 rounded-lg bg-[#0f1117]">
            <div className="text-xs text-[#8b8d97] mb-1">Market Sensitivity</div>
            <Badge color={(risk.beta || 1) > 1.3 ? '#ef4444' : (risk.beta || 1) > 0.7 ? '#eab308' : '#3b82f6'}>
              {(risk.beta || 1) > 1.3 ? 'HIGH BETA' : (risk.beta || 1) > 0.7 ? 'MARKET-LIKE' : 'DEFENSIVE'}
            </Badge>
          </div>
          <div className="p-3 rounded-lg bg-[#0f1117]">
            <div className="text-xs text-[#8b8d97] mb-1">Risk-Adj Return</div>
            <Badge color={(risk.sharpe_ratio || 0) > 1 ? '#22c55e' : (risk.sharpe_ratio || 0) > 0 ? '#eab308' : '#ef4444'}>
              {(risk.sharpe_ratio || 0) > 1 ? 'GOOD' : (risk.sharpe_ratio || 0) > 0 ? 'FAIR' : 'POOR'}
            </Badge>
          </div>
        </div>
      </Card>
    </div>
  )
}

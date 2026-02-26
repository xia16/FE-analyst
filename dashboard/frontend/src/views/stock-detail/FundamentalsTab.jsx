import { Card, ScoreBar, Badge, fmt, fmtPct, fmtCurrency, getScoreColor } from '../../components/shared'

function MetricRow({ label, value, suffix = '', color }) {
  if (value == null || value === '') return null
  return (
    <div className="flex justify-between text-xs py-1 border-b border-[#2a2d3e]/30">
      <span className="text-[#8b8d97]">{label}</span>
      <span className="font-mono" style={color ? { color } : undefined}>
        {typeof value === 'number' ? fmt(value, 2) : value}{suffix}
      </span>
    </div>
  )
}

function CheckItem({ label, passed }) {
  return (
    <div className={`flex items-center gap-2 text-xs py-1 px-2 rounded ${passed ? 'bg-[#22c55e08]' : 'bg-[#ef444408]'}`}>
      <span className={passed ? 'text-green-400' : 'text-red-400'}>
        {passed ? '\u2713' : '\u2717'}
      </span>
      <span className={passed ? '' : 'text-[#8b8d97]'}>{label}</span>
    </div>
  )
}

const PIOTROSKI_LABELS = {
  F1: 'Net Income > 0',
  F2: 'ROA improving',
  F3: 'Operating Cash Flow > 0',
  F4: 'OCF > Net Income (quality)',
  F5: 'Long-term debt decreased',
  F6: 'Current ratio improved',
  F7: 'No share dilution',
  F8: 'Gross margin improved',
  F9: 'Asset turnover improved',
}

export default function FundamentalsTab({ analysis }) {
  const fund = analysis?.details?.fundamental
  const ratios = analysis?.ratios || fund?.ratios || {}

  if (!fund) return <div className="text-[#8b8d97] text-center py-8">No fundamental data available.</div>

  const health = fund.health || {}
  const growth = fund.growth || {}
  const valuation = fund.valuation || {}
  const roic = fund.roic || {}
  const piotroski = fund.piotroski || {}
  const dupont = fund.dupont || {}
  const earningsQuality = fund.earnings_quality || {}
  const ccc = fund.cash_conversion_cycle || {}
  const capitalAlloc = fund.capital_allocation || {}
  const quarterlyTrends = fund.quarterly_trends || {}
  const sgaEff = fund.sga_efficiency || {}
  const valueCreation = fund.value_creation || {}
  const extraVal = fund.extra_valuation || {}
  const earningsStability = fund.earnings_stability || {}
  const redFlags = fund.red_flags || {}
  const conflicts = analysis?.conflicts || {}

  const dupont3 = dupont.three_way || {}
  const dupont5 = dupont.five_way || {}

  return (
    <div className="space-y-6">
      {/* Red Flags Banner */}
      {redFlags.count > 0 && (
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <span className="text-lg">{redFlags.has_critical ? '\u26A0\uFE0F' : '\u2139\uFE0F'}</span>
            <h3 className={`text-sm font-semibold ${redFlags.has_critical ? 'text-red-400' : 'text-yellow-400'}`}>
              {redFlags.count} Red Flag{redFlags.count > 1 ? 's' : ''} Detected
              {redFlags.high_severity_count > 0 && ` (${redFlags.high_severity_count} critical)`}
            </h3>
          </div>
          <div className="space-y-2">
            {(redFlags.flags || []).map((f, i) => (
              <div key={i} className={`flex items-start gap-2 text-xs p-2 rounded ${f.severity === 'HIGH' ? 'bg-red-500/10 border border-red-500/20' : f.severity === 'MEDIUM' ? 'bg-yellow-500/10 border border-yellow-500/20' : 'bg-[#0f1117]'}`}>
                <Badge color={f.severity === 'HIGH' ? '#ef4444' : f.severity === 'MEDIUM' ? '#eab308' : '#6b7280'}>{f.severity}</Badge>
                <div>
                  <span className="font-medium">{f.flag}</span>
                  <span className="text-[#8b8d97] ml-1">{f.detail}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Cross-Analyzer Conflicts */}
      {conflicts.count > 0 && (
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <span className="text-lg">{'\u26A1'}</span>
            <h3 className="text-sm font-semibold text-orange-400">
              {conflicts.count} Signal Conflict{conflicts.count > 1 ? 's' : ''}
            </h3>
          </div>
          <div className="space-y-2">
            {(conflicts.conflicts || []).map((c, i) => (
              <div key={i} className="flex items-start gap-2 text-xs p-2 rounded bg-orange-500/10 border border-orange-500/20">
                <Badge color={c.severity === 'HIGH' ? '#f97316' : '#eab308'}>{c.severity}</Badge>
                <span className="text-[#c8c9ce]">{c.detail}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Value Creation + Extra Metrics Row */}
      {(valueCreation.spread != null || extraVal.fcf_yield != null || earningsStability.cv != null) && (
        <Card>
          <h3 className="text-sm font-semibold mb-3">Key Quality Metrics</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
            {valueCreation.spread != null && (
              <div>
                <div className="text-[#8b8d97]">ROIC - WACC Spread</div>
                <div className={`font-bold font-mono text-lg ${valueCreation.creating_value ? 'text-green-400' : 'text-red-400'}`}>
                  {(valueCreation.spread * 100).toFixed(1)}%
                </div>
                <div className="text-[9px] text-[#8b8d97] mt-1">{valueCreation.assessment}</div>
              </div>
            )}
            {extraVal.fcf_yield != null && (
              <div>
                <div className="text-[#8b8d97]">FCF Yield</div>
                <div className={`font-bold font-mono text-lg ${extraVal.fcf_yield > 0.05 ? 'text-green-400' : extraVal.fcf_yield > 0.02 ? 'text-yellow-400' : 'text-red-400'}`}>
                  {(extraVal.fcf_yield * 100).toFixed(1)}%
                </div>
              </div>
            )}
            {extraVal.ev_fcf != null && (
              <div>
                <div className="text-[#8b8d97]">EV/FCF</div>
                <div className="font-bold font-mono text-lg">{extraVal.ev_fcf.toFixed(1)}x</div>
              </div>
            )}
            {earningsStability.cv != null && (
              <div>
                <div className="text-[#8b8d97]">Earnings Stability</div>
                <div className={`font-bold font-mono text-lg ${earningsStability.score >= 2 ? 'text-green-400' : earningsStability.score >= 1 ? 'text-yellow-400' : 'text-red-400'}`}>
                  {earningsStability.score}/{earningsStability.max_score}
                </div>
                <div className="text-[9px] text-[#8b8d97] mt-1">{earningsStability.stability}</div>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Subscores */}
      <Card>
        <h3 className="text-sm font-semibold mb-4">Fundamental Subscores</h3>
        <div className="space-y-3">
          {health.score != null && health.max_score && (
            <ScoreBar label={`Health (${health.score}/${health.max_score})`} score={(health.score / health.max_score) * 100} />
          )}
          {growth.score != null && growth.max_score && (
            <ScoreBar label={`Growth (${growth.score}/${growth.max_score})`} score={(growth.score / growth.max_score) * 100} />
          )}
          {valuation.score != null && valuation.max_score && (
            <ScoreBar label={`Valuation (${valuation.score}/${valuation.max_score})`} score={(valuation.score / valuation.max_score) * 100} />
          )}
          {roic.score != null && roic.max_score && (
            <ScoreBar label={`ROIC (${roic.score}/${roic.max_score})`} score={(roic.score / roic.max_score) * 100} />
          )}
          {piotroski.score != null && (
            <ScoreBar label={`Piotroski F-Score (${piotroski.score}/9)`} score={(piotroski.score / 9) * 100} />
          )}
          {earningsQuality.score != null && earningsQuality.max_score && (
            <ScoreBar label={`Earnings Quality (${earningsQuality.score}/${earningsQuality.max_score})`} score={(earningsQuality.score / earningsQuality.max_score) * 100} />
          )}
          {capitalAlloc.score != null && capitalAlloc.max_score && (
            <ScoreBar label={`Capital Allocation (${capitalAlloc.score}/${capitalAlloc.max_score})`} score={(capitalAlloc.score / capitalAlloc.max_score) * 100} />
          )}
        </div>
      </Card>

      {/* ROIC Card */}
      {roic.value != null && (
        <Card>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold">Return on Invested Capital (ROIC)</h3>
            <Badge color={roic.value > 0.15 ? '#22c55e' : roic.value > 0.08 ? '#eab308' : '#ef4444'}>
              {fmt(roic.value * 100, 1)}%
            </Badge>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
            <div>
              <div className="text-[#8b8d97]">NOPAT</div>
              <div className="font-bold font-mono">{fmtCurrency(roic.nopat)}</div>
            </div>
            <div>
              <div className="text-[#8b8d97]">Invested Capital</div>
              <div className="font-bold font-mono">{fmtCurrency(roic.invested_capital)}</div>
            </div>
            <div>
              <div className="text-[#8b8d97]">ROIC</div>
              <div className="font-bold font-mono text-lg" style={{ color: getScoreColor(roic.value * 100 * 3) }}>
                {fmt(roic.value * 100, 2)}%
              </div>
            </div>
          </div>
          <div className="mt-2 text-[10px] text-[#8b8d97]">
            ROIC = NOPAT / (Equity + Debt - Cash). Above 15% = excellent capital efficiency.
          </div>
        </Card>
      )}

      {/* Piotroski F-Score */}
      {piotroski.score != null && piotroski.breakdown && (
        <Card>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold">Piotroski F-Score</h3>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold font-mono" style={{ color: getScoreColor(piotroski.score / 9 * 100) }}>
                {piotroski.score}
              </span>
              <span className="text-[#8b8d97] text-xs">/ 9</span>
              {piotroski.signal && (
                <Badge color={piotroski.signal === 'STRONG' ? '#22c55e' : piotroski.signal === 'MODERATE' ? '#eab308' : '#ef4444'}>
                  {piotroski.signal}
                </Badge>
              )}
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            {/* Profitability (F1-F4) */}
            <div>
              <div className="text-[10px] text-[#8b8d97] uppercase tracking-wider mb-1.5">Profitability</div>
              {['F1', 'F2', 'F3', 'F4'].map(k => (
                <CheckItem key={k} label={`${k}: ${PIOTROSKI_LABELS[k]}`} passed={piotroski.breakdown[k]} />
              ))}
            </div>
            {/* Leverage (F5-F7) */}
            <div>
              <div className="text-[10px] text-[#8b8d97] uppercase tracking-wider mb-1.5">Leverage & Liquidity</div>
              {['F5', 'F6', 'F7'].map(k => (
                <CheckItem key={k} label={`${k}: ${PIOTROSKI_LABELS[k]}`} passed={piotroski.breakdown[k]} />
              ))}
            </div>
            {/* Efficiency (F8-F9) */}
            <div>
              <div className="text-[10px] text-[#8b8d97] uppercase tracking-wider mb-1.5">Operating Efficiency</div>
              {['F8', 'F9'].map(k => (
                <CheckItem key={k} label={`${k}: ${PIOTROSKI_LABELS[k]}`} passed={piotroski.breakdown[k]} />
              ))}
            </div>
          </div>
        </Card>
      )}

      {/* DuPont Decomposition */}
      {(dupont3.roe != null || dupont5.roe != null) && (
        <Card>
          <h3 className="text-sm font-semibold mb-3">DuPont Decomposition</h3>
          {/* 3-Way */}
          {dupont3.roe != null && (
            <div className="mb-4">
              <div className="text-[10px] text-[#8b8d97] uppercase tracking-wider mb-2">3-Way: ROE = Margin x Turnover x Leverage</div>
              <div className="flex flex-col sm:flex-row items-center gap-2 text-xs font-mono">
                <div className="p-2 rounded bg-[#0f1117] text-center flex-1 w-full sm:w-auto">
                  <div className="text-[10px] text-[#8b8d97]">Profit Margin</div>
                  <div className="font-bold">{fmt(dupont3.profit_margin * 100, 1)}%</div>
                </div>
                <span className="text-[#8b8d97] hidden sm:block">{'\u00D7'}</span>
                <div className="p-2 rounded bg-[#0f1117] text-center flex-1 w-full sm:w-auto">
                  <div className="text-[10px] text-[#8b8d97]">Asset Turnover</div>
                  <div className="font-bold">{fmt(dupont3.asset_turnover, 2)}x</div>
                </div>
                <span className="text-[#8b8d97] hidden sm:block">{'\u00D7'}</span>
                <div className="p-2 rounded bg-[#0f1117] text-center flex-1 w-full sm:w-auto">
                  <div className="text-[10px] text-[#8b8d97]">Equity Multiplier</div>
                  <div className="font-bold">{fmt(dupont3.equity_multiplier, 2)}x</div>
                </div>
                <span className="text-[#8b8d97] hidden sm:block">=</span>
                <div className="p-2 rounded bg-blue-500/10 text-center flex-1 w-full sm:w-auto border border-blue-500/20">
                  <div className="text-[10px] text-blue-400">ROE</div>
                  <div className="font-bold text-blue-400">{fmt(dupont3.roe * 100, 1)}%</div>
                </div>
              </div>
            </div>
          )}
          {/* 5-Way (if available and different from 3-way) */}
          {dupont5.roe != null && dupont5.tax_burden != null && (
            <div>
              <div className="text-[10px] text-[#8b8d97] uppercase tracking-wider mb-2">5-Way Decomposition</div>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2 text-xs">
                <div className="p-2 rounded bg-[#0f1117] text-center">
                  <div className="text-[10px] text-[#8b8d97]">Tax Burden</div>
                  <div className="font-bold font-mono">{fmt(dupont5.tax_burden * 100, 1)}%</div>
                </div>
                <div className="p-2 rounded bg-[#0f1117] text-center">
                  <div className="text-[10px] text-[#8b8d97]">Interest Burden</div>
                  <div className="font-bold font-mono">{fmt(dupont5.interest_burden * 100, 1)}%</div>
                </div>
                <div className="p-2 rounded bg-[#0f1117] text-center">
                  <div className="text-[10px] text-[#8b8d97]">EBIT Margin</div>
                  <div className="font-bold font-mono">{fmt(dupont5.ebit_margin * 100, 1)}%</div>
                </div>
                <div className="p-2 rounded bg-[#0f1117] text-center">
                  <div className="text-[10px] text-[#8b8d97]">Asset Turnover</div>
                  <div className="font-bold font-mono">{fmt(dupont5.asset_turnover, 2)}x</div>
                </div>
                <div className="p-2 rounded bg-[#0f1117] text-center">
                  <div className="text-[10px] text-[#8b8d97]">Eq. Multiplier</div>
                  <div className="font-bold font-mono">{fmt(dupont5.equity_multiplier, 2)}x</div>
                </div>
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Cash Conversion Cycle + Earnings Quality side by side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Cash Conversion Cycle */}
        {ccc.ccc != null && (
          <Card>
            <h3 className="text-sm font-semibold mb-3">Cash Conversion Cycle</h3>
            <div className="flex items-center gap-2 mb-3">
              <div className="text-2xl font-bold font-mono" style={{ color: ccc.ccc < 0 ? '#22c55e' : ccc.ccc < 30 ? '#4ade80' : ccc.ccc < 90 ? '#eab308' : '#ef4444' }}>
                {fmt(ccc.ccc, 0)}
              </div>
              <span className="text-xs text-[#8b8d97]">days</span>
            </div>
            <div className="space-y-1 text-xs">
              {ccc.dso != null && (
                <div className="flex justify-between py-1 border-b border-[#2a2d3e]/30">
                  <span className="text-[#8b8d97]">Days Sales Outstanding (DSO)</span>
                  <span className="font-mono">{fmt(ccc.dso, 1)} days</span>
                </div>
              )}
              {ccc.dio != null && (
                <div className="flex justify-between py-1 border-b border-[#2a2d3e]/30">
                  <span className="text-[#8b8d97]">Days Inventory Outstanding (DIO)</span>
                  <span className="font-mono">{fmt(ccc.dio, 1)} days</span>
                </div>
              )}
              {ccc.dpo != null && (
                <div className="flex justify-between py-1 border-b border-[#2a2d3e]/30">
                  <span className="text-[#8b8d97]">Days Payables Outstanding (DPO)</span>
                  <span className="font-mono">{fmt(ccc.dpo, 1)} days</span>
                </div>
              )}
            </div>
            {ccc.assessment && ccc.assessment !== 'N/A' && (
              <div className="mt-2 text-[10px] text-[#8b8d97] bg-[#0f1117] rounded p-2">{ccc.assessment}</div>
            )}
          </Card>
        )}

        {/* Earnings Quality */}
        {(earningsQuality.accruals_ratio != null || earningsQuality.fcf_ni_ratio != null) && (
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold">Earnings Quality</h3>
              {earningsQuality.score != null && (
                <Badge color={earningsQuality.score >= 2 ? '#22c55e' : earningsQuality.score >= 1 ? '#eab308' : '#ef4444'}>
                  {earningsQuality.score}/{earningsQuality.max_score}
                </Badge>
              )}
            </div>
            <div className="space-y-2 text-xs">
              {earningsQuality.accruals_ratio != null && (
                <div className="flex justify-between py-1 border-b border-[#2a2d3e]/30">
                  <span className="text-[#8b8d97]">Accruals Ratio</span>
                  <span className={`font-mono ${earningsQuality.accruals_ratio < 0 ? 'text-green-400' : earningsQuality.accruals_ratio > 0.05 ? 'text-red-400' : ''}`}>
                    {fmt(earningsQuality.accruals_ratio * 100, 2)}%
                  </span>
                </div>
              )}
              {earningsQuality.fcf_ni_ratio != null && (
                <div className="flex justify-between py-1 border-b border-[#2a2d3e]/30">
                  <span className="text-[#8b8d97]">FCF / Net Income</span>
                  <span className={`font-mono ${earningsQuality.fcf_ni_ratio > 1 ? 'text-green-400' : earningsQuality.fcf_ni_ratio < 0.5 ? 'text-red-400' : ''}`}>
                    {fmt(earningsQuality.fcf_ni_ratio, 2)}x
                  </span>
                </div>
              )}
            </div>
            {earningsQuality.assessment && earningsQuality.assessment !== 'N/A' && (
              <div className="mt-2 text-[10px] text-[#8b8d97] bg-[#0f1117] rounded p-2">{earningsQuality.assessment}</div>
            )}
          </Card>
        )}
      </div>

      {/* Capital Allocation */}
      {capitalAlloc.score != null && (
        <Card>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold">Capital Allocation</h3>
            <Badge color={capitalAlloc.score >= 3 ? '#22c55e' : capitalAlloc.score >= 2 ? '#eab308' : '#ef4444'}>
              {capitalAlloc.score}/{capitalAlloc.max_score}
            </Badge>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
            {capitalAlloc.rd_intensity != null && (
              <div>
                <div className="text-[#8b8d97]">R&D Intensity</div>
                <div className="font-bold font-mono">{fmt(capitalAlloc.rd_intensity * 100, 1)}%</div>
                <div className="text-[9px] text-[#8b8d97]">of revenue</div>
              </div>
            )}
            {capitalAlloc.capex_depr_ratio != null && (
              <div>
                <div className="text-[#8b8d97]">CapEx / Depreciation</div>
                <div className={`font-bold font-mono ${capitalAlloc.capex_depr_ratio > 1 ? 'text-green-400' : ''}`}>
                  {fmt(capitalAlloc.capex_depr_ratio, 2)}x
                </div>
                <div className="text-[9px] text-[#8b8d97]">{capitalAlloc.capex_depr_ratio > 1 ? 'investing > maintaining' : 'under-investing'}</div>
              </div>
            )}
            {capitalAlloc.buyback_yield != null && (
              <div>
                <div className="text-[#8b8d97]">Buyback Yield</div>
                <div className={`font-bold font-mono ${capitalAlloc.buyback_yield > 0.01 ? 'text-green-400' : ''}`}>
                  {fmt(capitalAlloc.buyback_yield * 100, 2)}%
                </div>
              </div>
            )}
            {capitalAlloc.net_debt_change != null && (
              <div>
                <div className="text-[#8b8d97]">Net Debt Change</div>
                <div className={`font-bold font-mono ${capitalAlloc.net_debt_change < 0 ? 'text-green-400' : capitalAlloc.net_debt_change > 0 ? 'text-red-400' : ''}`}>
                  {fmtCurrency(capitalAlloc.net_debt_change)}
                </div>
                <div className="text-[9px] text-[#8b8d97]">{capitalAlloc.net_debt_change < 0 ? 'paying down debt' : capitalAlloc.net_debt_change > 0 ? 'increasing debt' : 'no change'}</div>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Quarterly Trends */}
      {quarterlyTrends.quarters && quarterlyTrends.quarters.length > 0 && (
        <Card>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold">Quarterly Trends</h3>
            <div className="flex gap-3 text-[10px]">
              {quarterlyTrends.revenue_trend && quarterlyTrends.revenue_trend !== 'N/A' && (
                <span>
                  Rev: <Badge color={quarterlyTrends.revenue_trend === 'Expanding' ? '#22c55e' : quarterlyTrends.revenue_trend === 'Contracting' ? '#ef4444' : '#eab308'}>
                    {quarterlyTrends.revenue_trend}
                  </Badge>
                </span>
              )}
              {quarterlyTrends.margin_trend && quarterlyTrends.margin_trend !== 'N/A' && (
                <span>
                  Margin: <Badge color={quarterlyTrends.margin_trend === 'Expanding' ? '#22c55e' : quarterlyTrends.margin_trend === 'Contracting' ? '#ef4444' : '#eab308'}>
                    {quarterlyTrends.margin_trend}
                  </Badge>
                </span>
              )}
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[10px] font-mono">
              <thead>
                <tr className="text-[#a0a2ab] border-b border-[#2a2d3e] uppercase tracking-wider">
                  <th className="text-left p-1.5 font-semibold">Quarter</th>
                  <th className="text-right p-1.5 font-semibold">Revenue</th>
                  <th className="text-right p-1.5 font-semibold">Gross Margin</th>
                  <th className="text-right p-1.5 font-semibold">Op Margin</th>
                  <th className="text-right p-1.5 font-semibold">Net Income</th>
                </tr>
              </thead>
              <tbody>
                {quarterlyTrends.quarters.map((q, i) => (
                  <tr key={i} className="border-b border-[#2a2d3e]/30">
                    <td className="p-1.5 text-[#8b8d97]">{q.period}</td>
                    <td className="p-1.5 text-right">{q.revenue != null ? fmtCurrency(q.revenue) : '\u2014'}</td>
                    <td className="p-1.5 text-right">{q.gross_margin != null ? fmt(q.gross_margin * 100, 1) + '%' : '\u2014'}</td>
                    <td className="p-1.5 text-right">{q.operating_margin != null ? fmt(q.operating_margin * 100, 1) + '%' : '\u2014'}</td>
                    <td className="p-1.5 text-right">{q.net_income != null ? fmtCurrency(q.net_income) : '\u2014'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Health + Growth + Ratios Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* Health reasons */}
        {health.reasons?.length > 0 && (
          <Card>
            <h3 className="text-sm font-semibold mb-3">Financial Health</h3>
            <div className="space-y-1.5">
              {health.reasons.map((reason, i) => (
                <div key={i} className="flex items-center gap-2 text-xs p-1.5 rounded bg-[#22c55e08]">
                  <span className="text-green-400">{'\u2713'}</span>
                  <span>{reason}</span>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Growth reasons */}
        {growth.reasons?.length > 0 && (
          <Card>
            <h3 className="text-sm font-semibold mb-3">Growth</h3>
            <div className="space-y-1.5">
              {growth.reasons.map((reason, i) => (
                <div key={i} className="flex items-center gap-2 text-xs p-1.5 rounded bg-[#22c55e08]">
                  <span className="text-green-400">{'\u2713'}</span>
                  <span>{reason}</span>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Key ratios */}
        {Object.keys(ratios).length > 1 && (
          <Card>
            <h3 className="text-sm font-semibold mb-3">Key Ratios</h3>
            <div className="space-y-0.5">
              <MetricRow label="Revenue Growth" value={ratios.revenue_growth != null ? ratios.revenue_growth * 100 : null} suffix="%" />
              <MetricRow label="Earnings Growth" value={ratios.earnings_growth != null ? ratios.earnings_growth * 100 : null} suffix="%" />
              <MetricRow label="Profit Margin" value={ratios.profit_margin != null ? ratios.profit_margin * 100 : null} suffix="%" />
              <MetricRow label="Operating Margin" value={ratios.operating_margin != null ? ratios.operating_margin * 100 : null} suffix="%" />
              <MetricRow label="ROE" value={ratios.roe != null ? ratios.roe * 100 : null} suffix="%" />
              <MetricRow label="ROA" value={ratios.roa != null ? ratios.roa * 100 : null} suffix="%" />
              <MetricRow label="Current Ratio" value={ratios.current_ratio} />
              <MetricRow label="Quick Ratio" value={ratios.quick_ratio} />
              <MetricRow label="Debt/Equity" value={ratios.debt_to_equity} />
              <MetricRow label="P/E (Trailing)" value={ratios.pe_trailing} />
              <MetricRow label="P/E (Forward)" value={ratios.pe_forward} />
              <MetricRow label="P/B Ratio" value={ratios.pb_ratio} />
              <MetricRow label="P/S Ratio" value={ratios.ps_ratio} />
              <MetricRow label="EV/EBITDA" value={ratios.ev_ebitda} />
              <MetricRow label="Dividend Yield" value={ratios.dividend_yield != null ? ratios.dividend_yield * 100 : null} suffix="%" />
              <MetricRow label="Payout Ratio" value={ratios.payout_ratio != null ? ratios.payout_ratio * 100 : null} suffix="%" />
            </div>
          </Card>
        )}
      </div>

      {/* SG&A Efficiency */}
      {sgaEff.sga_revenue_ratio != null && (
        <Card>
          <h3 className="text-sm font-semibold mb-3">SG&A Efficiency</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
            <div>
              <div className="text-[#8b8d97]">SG&A / Revenue</div>
              <div className="font-bold font-mono">{fmt(sgaEff.sga_revenue_ratio * 100, 1)}%</div>
            </div>
            {sgaEff.trend && sgaEff.trend !== 'N/A' && (
              <div>
                <div className="text-[#8b8d97]">Trend</div>
                <Badge color={sgaEff.trend === 'Improving' ? '#22c55e' : sgaEff.trend === 'Deteriorating' ? '#ef4444' : '#eab308'}>
                  {sgaEff.trend}
                </Badge>
              </div>
            )}
            {sgaEff.operating_leverage != null && (
              <div>
                <div className="text-[#8b8d97]">Operating Leverage</div>
                <Badge color={sgaEff.operating_leverage ? '#22c55e' : '#ef4444'}>
                  {sgaEff.operating_leverage ? 'Yes' : 'No'}
                </Badge>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Valuation reasons */}
      {valuation.reasons?.length > 0 && (
        <Card>
          <h3 className="text-sm font-semibold mb-3">Valuation Notes</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {valuation.reasons.map((reason, i) => (
              <div key={i} className="flex items-center gap-2 text-xs p-1.5 rounded bg-[#0f1117]">
                <span className="text-[#8b8d97]">{'\u2022'}</span>
                <span>{reason}</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

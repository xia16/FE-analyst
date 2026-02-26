import { Card, Badge, fmt, fmtCurrency, getScoreColor } from '../../components/shared'

function MetricCell({ label, value, suffix = '', color }) {
  if (value == null) return null
  return (
    <div>
      <div className="text-[#8b8d97] text-[10px]">{label}</div>
      <div className="font-bold font-mono" style={color ? { color } : undefined}>
        {typeof value === 'number' ? fmt(value, 2) : value}{suffix}
      </div>
    </div>
  )
}

export default function ValuationTab({ analysis, thesis }) {
  const val = analysis?.details?.valuation
  if (!val) return <div className="text-[#8b8d97] text-center py-8">No valuation data available.</div>

  const dcf = val.dcf || {}
  const comps = val.comparables || {}
  const sensitivity = dcf.sensitivity || {}
  const mechanicalScenarios = dcf.scenarios || {}
  const wacc = dcf.wacc_breakdown || {}
  const projection = dcf.two_stage_projection || []
  const tvMethods = dcf.terminal_value_methods || {}
  const reverseDcf = dcf.reverse_dcf || {}
  const analyst = dcf.analyst_targets || {}
  const valueBreakdown = dcf.value_breakdown || {}
  const composite = dcf.composite || {}
  const methodFVs = composite.method_fair_values || {}
  const methodWeights = composite.method_weights || {}

  // LLM-validated scenarios take priority over mechanical
  const llmScenarios = thesis?.data?.llm_scenarios
  const hasLLMScenarios = llmScenarios?.source === 'llm_validated' && llmScenarios?.scenarios
  const scenarios = hasLLMScenarios ? llmScenarios.scenarios : mechanicalScenarios
  const probWeighted = hasLLMScenarios ? llmScenarios.probability_weighted : dcf.probability_weighted_fair_value
  const riskReward = hasLLMScenarios ? llmScenarios.risk_reward : dcf.risk_reward_ratio
  const scenarioPrice = hasLLMScenarios ? llmScenarios.current_price : dcf.current_price

  // Use composite fair value as primary if available, else fall back to DCF
  const primaryFV = composite.composite_fair_value || dcf.intrinsic_per_share || dcf.fair_value_per_share
  const primaryVerdict = composite.verdict || dcf.verdict
  const primaryMOS = composite.margin_of_safety_pct ?? dcf.margin_of_safety_pct

  const METHOD_LABELS = {
    fcf_dcf: { label: 'FCF DCF', color: '#3b82f6' },
    owner_earnings_dcf: { label: 'Owner Earnings', color: '#8b5cf6' },
    epv: { label: 'Earnings Power', color: '#f59e0b' },
    analyst_consensus: { label: 'Analyst Target', color: '#06b6d4' },
  }

  return (
    <div className="space-y-6">
      {/* Composite Fair Value Summary */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card className="text-center">
          <div className="text-[#8b8d97] text-xs mb-1">
            {composite.composite_fair_value ? 'Composite Fair Value' : 'DCF Fair Value'}
          </div>
          <div className="text-2xl font-bold font-mono text-blue-400">
            ${fmt(primaryFV, 2)}
          </div>
          {primaryVerdict && (
            <Badge color={primaryVerdict === 'UNDERVALUED' ? '#22c55e' : primaryVerdict === 'OVERVALUED' ? '#ef4444' : '#eab308'}>
              {primaryVerdict}
            </Badge>
          )}
        </Card>
        <Card className="text-center">
          <div className="text-[#8b8d97] text-xs mb-1">Current Price</div>
          <div className="text-2xl font-bold font-mono">
            ${fmt(composite.current_price || dcf.current_price, 2)}
          </div>
        </Card>
        <Card className="text-center">
          <div className="text-[#8b8d97] text-xs mb-1">Margin of Safety</div>
          <div className={`text-2xl font-bold font-mono ${(primaryMOS || 0) > 0 ? 'text-green-400' : 'text-red-400'}`}>
            {fmt(primaryMOS, 1)}%
          </div>
        </Card>
        <Card className="text-center">
          <div className="text-[#8b8d97] text-xs mb-1">Prob-Weighted FV</div>
          <div className="text-2xl font-bold font-mono text-purple-400">
            {probWeighted != null ? `$${fmt(probWeighted, 2)}` : '\u2014'}
          </div>
        </Card>
        <Card className="text-center">
          <div className="text-[#8b8d97] text-xs mb-1">Risk / Reward</div>
          <div className={`text-2xl font-bold font-mono ${(riskReward || 0) > 1.5 ? 'text-green-400' : (riskReward || 0) > 1 ? 'text-yellow-400' : 'text-red-400'}`}>
            {riskReward != null ? `${fmt(riskReward, 2)}x` : '\u2014'}
          </div>
        </Card>
      </div>

      {/* Multi-Method Fair Value Breakdown */}
      {Object.keys(methodFVs).length > 1 && (
        <Card>
          <h3 className="text-sm font-semibold mb-3">Multi-Method Fair Value</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(methodFVs).map(([method, fv]) => {
              const meta = METHOD_LABELS[method] || { label: method.replace(/_/g, ' '), color: '#8b8d97' }
              const weight = methodWeights[method]
              return (
                <div key={method} className="p-3 rounded-lg border border-[#2a2d3e] bg-[#0f1117]">
                  <div className="flex items-center justify-between mb-1">
                    <div className="text-[10px] font-medium" style={{ color: meta.color }}>{meta.label}</div>
                    {weight != null && (
                      <div className="text-[9px] text-[#8b8d97]">{(weight * 100).toFixed(0)}% wt</div>
                    )}
                  </div>
                  <div className="text-lg font-bold font-mono" style={{ color: meta.color }}>
                    ${fmt(fv, 2)}
                  </div>
                  {(composite.current_price || dcf.current_price) && (
                    <div className={`text-[10px] font-mono mt-1 ${fv > (composite.current_price || dcf.current_price) ? 'text-green-400' : 'text-red-400'}`}>
                      {fv > (composite.current_price || dcf.current_price) ? '+' : ''}
                      {fmt(((fv - (composite.current_price || dcf.current_price)) / (composite.current_price || dcf.current_price)) * 100, 1)}%
                    </div>
                  )}
                </div>
              )
            })}
          </div>
          {/* Owner Earnings breakdown if available */}
          {composite.methods?.owner_earnings_dcf?.owner_earnings_breakdown && (() => {
            const oe = composite.methods.owner_earnings_dcf.owner_earnings_breakdown
            return (
              <div className="mt-3 border-t border-[#2a2d3e] pt-3">
                <div className="text-[10px] text-[#8b8d97] mb-2">Owner Earnings Breakdown</div>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 text-[10px]">
                  <div>
                    <div className="text-[#8b8d97]">Operating CF</div>
                    <div className="font-bold font-mono text-green-400">{fmtCurrency(oe.operating_cash_flow)}</div>
                  </div>
                  <div>
                    <div className="text-[#8b8d97]">Total CapEx</div>
                    <div className="font-bold font-mono text-red-400">-{fmtCurrency(oe.total_capex)}</div>
                  </div>
                  <div>
                    <div className="text-[#8b8d97]">Maintenance</div>
                    <div className="font-bold font-mono text-yellow-400">-{fmtCurrency(oe.maintenance_capex)}</div>
                  </div>
                  <div>
                    <div className="text-[#8b8d97]">Growth CapEx</div>
                    <div className="font-bold font-mono text-purple-400">{fmtCurrency(oe.growth_capex)}</div>
                  </div>
                  <div>
                    <div className="text-[#8b8d97]">Raw FCF</div>
                    <div className="font-bold font-mono">{fmtCurrency(oe.raw_fcf)}</div>
                  </div>
                  <div>
                    <div className="text-[#8b8d97]">Owner Earnings</div>
                    <div className="font-bold font-mono text-blue-400">{fmtCurrency(oe.owner_earnings)}</div>
                  </div>
                </div>
                {oe.growth_capex_ratio > 0.3 && (
                  <div className="mt-2 text-[9px] text-purple-400 bg-purple-500/5 rounded p-1.5">
                    {(oe.growth_capex_ratio * 100).toFixed(0)}% of capex is growth investment — Owner Earnings DCF is more appropriate than FCF DCF
                  </div>
                )}
              </div>
            )
          })()}
          {composite.notes && composite.notes.length > 0 && (
            <div className="mt-2 space-y-0.5">
              {composite.notes.map((n, i) => (
                <div key={i} className="text-[9px] text-[#8b8d97]">{n}</div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Score Breakdown */}
      <Card>
        <h3 className="text-sm font-semibold mb-3">Valuation Score Breakdown</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-[#8b8d97] text-xs mb-1">DCF Score (60%)</div>
            <div className="text-xl font-bold font-mono" style={{ color: getScoreColor(val.dcf_score || 50) }}>
              {fmt(val.dcf_score, 1)}
            </div>
          </div>
          <div>
            <div className="text-[#8b8d97] text-xs mb-1">Comps Score (25%)</div>
            <div className="text-xl font-bold font-mono" style={{ color: getScoreColor(val.comps_score || 50) }}>
              {fmt(val.comps_score, 1)}
            </div>
          </div>
          <div>
            <div className="text-[#8b8d97] text-xs mb-1">Quality Score (15%)</div>
            <div className="text-xl font-bold font-mono" style={{ color: getScoreColor(val.quality_score || 50) }}>
              {fmt(val.quality_score, 1)}
            </div>
          </div>
        </div>
      </Card>

      {/* WACC Breakdown */}
      {Object.keys(wacc).length > 0 && (
        <Card>
          <h3 className="text-sm font-semibold mb-3">WACC Breakdown</h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-xs">
            <div>
              <div className="text-[#8b8d97]">WACC</div>
              <div className="font-bold text-lg font-mono text-blue-400">{fmt((wacc.wacc || dcf.discount_rate || 0) * 100, 2)}%</div>
            </div>
            {wacc.cost_of_equity != null && (
              <MetricCell label="Cost of Equity (Ke)" value={wacc.cost_of_equity * 100} suffix="%" />
            )}
            {wacc.cost_of_debt != null && wacc.debt_weight > 0 && (
              <MetricCell label="Cost of Debt (Kd)" value={wacc.cost_of_debt * 100} suffix="%" />
            )}
            {wacc.tax_rate != null && wacc.debt_weight > 0 && (
              <MetricCell label="Effective Tax Rate" value={wacc.tax_rate * 100} suffix="%" />
            )}
            {wacc.beta != null && (
              <MetricCell label="Beta" value={wacc.beta} />
            )}
          </div>
          {(wacc.equity_weight != null || wacc.debt_weight != null) && (
            <div className="mt-3 grid grid-cols-2 md:grid-cols-5 gap-4 text-xs">
              {wacc.equity_weight != null && (
                <MetricCell label="Equity Weight" value={wacc.equity_weight * 100} suffix="%" />
              )}
              {wacc.debt_weight != null && (
                <MetricCell label="Debt Weight" value={wacc.debt_weight * 100} suffix="%" />
              )}
              {wacc.risk_free_rate != null && (
                <MetricCell label="Risk-Free Rate" value={wacc.risk_free_rate * 100} suffix="%" />
              )}
              {wacc.equity_risk_premium != null && (
                <MetricCell label="Equity Risk Premium" value={wacc.equity_risk_premium * 100} suffix="%" />
              )}
              {wacc.country_premium != null && (
                <MetricCell label="Country Premium" value={wacc.country_premium * 100} suffix="%" />
              )}
            </div>
          )}
        </Card>
      )}

      {/* Two-Stage FCF Projection Table */}
      {projection.length > 0 && (
        <Card>
          <h3 className="text-sm font-semibold mb-3">Two-Stage FCF Projection</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-[10px] font-mono">
              <thead>
                <tr className="text-[#a0a2ab] border-b border-[#2a2d3e] uppercase tracking-wider">
                  <th className="text-left p-1.5 font-semibold">Year</th>
                  <th className="text-center p-1.5 font-semibold">Stage</th>
                  <th className="text-right p-1.5 font-semibold">Growth</th>
                  <th className="text-right p-1.5 font-semibold">FCF</th>
                </tr>
              </thead>
              <tbody>
                {projection.map((p) => (
                  <tr key={p.year} className="border-b border-[#2a2d3e]/30">
                    <td className="p-1.5 text-[#8b8d97]">Yr {p.year}</td>
                    <td className="p-1.5 text-center">
                      <Badge color={p.stage === 1 ? '#3b82f6' : '#a855f7'}>
                        {p.stage === 1 ? 'High Growth' : 'Fade'}
                      </Badge>
                    </td>
                    <td className="p-1.5 text-right">{fmt(p.growth_rate * 100, 1)}%</td>
                    <td className="p-1.5 text-right">{fmtCurrency(p.fcf)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Value breakdown summary */}
          {(valueBreakdown.pv_fcfs != null || valueBreakdown.pv_terminal != null) && (
            <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
              <div>
                <div className="text-[#8b8d97] text-[10px]">PV of FCFs</div>
                <div className="font-bold font-mono">{fmtCurrency(valueBreakdown.pv_fcfs)}</div>
              </div>
              <div>
                <div className="text-[#8b8d97] text-[10px]">PV of Terminal Value</div>
                <div className="font-bold font-mono">{fmtCurrency(valueBreakdown.pv_terminal)}</div>
              </div>
              <div>
                <div className="text-[#8b8d97] text-[10px]">TV % of Total</div>
                <div className={`font-bold font-mono ${(valueBreakdown.tv_pct_of_total || 0) > 0.75 ? 'text-yellow-400' : ''}`}>
                  {fmt((valueBreakdown.tv_pct_of_total || 0) * 100, 1)}%
                </div>
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Terminal Value Methods */}
      {(tvMethods.gordon_growth != null || tvMethods.exit_multiple != null) && (
        <Card>
          <h3 className="text-sm font-semibold mb-3">Terminal Value Methods</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div className="p-3 rounded-lg border border-[#2a2d3e] bg-[#0f1117]">
              <div className="text-[#8b8d97] text-[10px] mb-1">Gordon Growth Model</div>
              <div className="font-bold font-mono text-lg">{fmtCurrency(tvMethods.gordon_growth)}</div>
              <div className="text-[9px] text-[#8b8d97] mt-1">TV = FCF(n+1) / (WACC - g)</div>
            </div>
            {tvMethods.exit_multiple != null && (
              <div className="p-3 rounded-lg border border-[#2a2d3e] bg-[#0f1117]">
                <div className="text-[#8b8d97] text-[10px] mb-1">Exit Multiple Method</div>
                <div className="font-bold font-mono text-lg">{fmtCurrency(tvMethods.exit_multiple)}</div>
                <div className="text-[9px] text-[#8b8d97] mt-1">
                  Exit EV/EBITDA: {fmt(tvMethods.exit_multiple_used, 1)}x
                </div>
              </div>
            )}
            <div className="p-3 rounded-lg border border-blue-500/20 bg-blue-500/5">
              <div className="text-[#8b8d97] text-[10px] mb-1">Averaged Terminal Value</div>
              <div className="font-bold font-mono text-lg text-blue-400">{fmtCurrency(tvMethods.averaged)}</div>
              <div className="text-[9px] text-[#8b8d97] mt-1">Blended (GGM + Exit Multiple) / 2</div>
            </div>
          </div>
        </Card>
      )}

      {/* DCF Model Details */}
      <Card>
        <h3 className="text-sm font-semibold mb-3">DCF Model Inputs</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <div>
            <div className="text-[#8b8d97]">Growth Rate</div>
            <div className="font-bold font-mono">{fmt((dcf.growth_rate || 0) * 100, 2)}%</div>
            {dcf.growth_source && <div className="text-[9px] text-[#8b8d97]">{dcf.growth_source}</div>}
          </div>
          <div>
            <div className="text-[#8b8d97]">Terminal Growth</div>
            <div className="font-bold font-mono">{fmt((dcf.terminal_growth || 0) * 100, 2)}%</div>
          </div>
          <div>
            <div className="text-[#8b8d97]">Enterprise Value</div>
            <div className="font-bold font-mono">{fmtCurrency(dcf.enterprise_value)}</div>
          </div>
          {dcf.net_debt != null && (
            <div>
              <div className="text-[#8b8d97]">Net Debt</div>
              <div className="font-bold font-mono">{fmtCurrency(dcf.net_debt)}</div>
            </div>
          )}
          {dcf.equity_value != null && (
            <div>
              <div className="text-[#8b8d97]">Equity Value</div>
              <div className="font-bold font-mono">{fmtCurrency(dcf.equity_value)}</div>
            </div>
          )}
          {dcf.shares_diluted != null && (
            <div>
              <div className="text-[#8b8d97]">Shares (Diluted)</div>
              <div className="font-bold font-mono">{(dcf.shares_diluted / 1e6).toFixed(1)}M</div>
            </div>
          )}
          {dcf.current_fcf != null && (
            <div>
              <div className="text-[#8b8d97]">Current FCF</div>
              <div className="font-bold font-mono">{fmtCurrency(dcf.current_fcf)}</div>
            </div>
          )}
        </div>
        {/* Growth sources */}
        {dcf.growth_sources && Object.keys(dcf.growth_sources).length > 0 && (
          <div className="mt-3 border-t border-[#2a2d3e] pt-2">
            <div className="text-[10px] text-[#8b8d97] mb-1">Growth Rate Sources</div>
            <div className="flex flex-wrap gap-3 text-[10px]">
              {Object.entries(dcf.growth_sources).map(([src, val]) => (
                <span key={src} className="font-mono">
                  <span className="text-[#8b8d97]">{src.replace(/_/g, ' ')}:</span>{' '}
                  <span className="text-[#c8c9ce]">{fmt(val * 100, 1)}%</span>
                </span>
              ))}
            </div>
          </div>
        )}
        {dcf.warnings && dcf.warnings.length > 0 && (
          <div className="mt-3 space-y-1">
            {dcf.warnings.map((w, i) => (
              <div key={i} className="text-[10px] text-yellow-400 flex items-center gap-1">
                <span>!</span> {w}
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Reverse DCF */}
      {reverseDcf && !reverseDcf.error && reverseDcf.implied_growth_rate != null && (
        <Card>
          <h3 className="text-sm font-semibold mb-3">Reverse DCF (Implied Growth Rate)</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
            <div>
              <div className="text-[#8b8d97]">Implied Growth</div>
              <div className="font-bold font-mono text-lg">{fmt(reverseDcf.implied_growth_rate * 100, 2)}%</div>
            </div>
            {reverseDcf.estimated_growth_rate != null && (
              <div>
                <div className="text-[#8b8d97]">Estimated Growth</div>
                <div className="font-bold font-mono text-lg">{fmt(reverseDcf.estimated_growth_rate * 100, 2)}%</div>
              </div>
            )}
            {reverseDcf.gap != null && (
              <div>
                <div className="text-[#8b8d97]">Gap</div>
                <div className={`font-bold font-mono text-lg ${reverseDcf.gap > 0.03 ? 'text-red-400' : reverseDcf.gap < -0.03 ? 'text-green-400' : 'text-yellow-400'}`}>
                  {fmt(reverseDcf.gap * 100, 2)}%
                </div>
              </div>
            )}
          </div>
          {reverseDcf.verdict && (
            <div className="mt-2 text-xs text-[#8b8d97] bg-[#0f1117] rounded-lg p-2">
              {reverseDcf.verdict}
            </div>
          )}
        </Card>
      )}
      {/* Reverse DCF error/note */}
      {reverseDcf && reverseDcf.error && (
        <Card>
          <h3 className="text-sm font-semibold mb-2">Reverse DCF</h3>
          <div className="text-xs text-[#8b8d97]">{reverseDcf.error}</div>
        </Card>
      )}
      {reverseDcf && !reverseDcf.error && reverseDcf.implied_growth_rate == null && reverseDcf.verdict && (
        <Card>
          <h3 className="text-sm font-semibold mb-2">Reverse DCF</h3>
          <div className="text-xs text-[#8b8d97]">{reverseDcf.verdict}</div>
        </Card>
      )}

      {/* Sensitivity Matrix */}
      {sensitivity.matrix && (
        <Card>
          <h3 className="text-sm font-semibold mb-3">DCF Sensitivity Matrix (Fair Value per Share)</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-[10px] font-mono">
              <thead>
                <tr className="text-[#8b8d97]">
                  <th className="p-1.5 text-left">WACC \ TG</th>
                  {(sensitivity.terminal_growth_range || sensitivity.terminal_growth_rates || []).map((tg, i) => (
                    <th key={i} className={`p-1.5 text-center ${i === (sensitivity.base_tg_idx ?? 2) ? 'bg-blue-500/10 text-blue-400' : ''}`}>
                      {fmt(tg * 100, 1)}%
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(sensitivity.matrix || []).map((row, ri) => {
                  const isBaseWacc = ri === (sensitivity.base_wacc_idx ?? 2)
                  return (
                    <tr key={ri} className={`border-t border-[#2a2d3e]/30 ${isBaseWacc ? 'bg-blue-500/5' : ''}`}>
                      <td className={`p-1.5 ${isBaseWacc ? 'text-blue-400 font-bold' : 'text-[#8b8d97]'}`}>
                        {fmt((sensitivity.wacc_range || sensitivity.wacc_rates || [])[ri] * 100, 1)}%
                      </td>
                      {row.map((val, ci) => {
                        if (val == null) return <td key={ci} className="p-1.5 text-center text-[#8b8d97]">{'\u2014'}</td>
                        const mos = dcf.current_price ? ((val - dcf.current_price) / dcf.current_price) * 100 : 0
                        const isBase = ri === (sensitivity.base_wacc_idx ?? 2) && ci === (sensitivity.base_tg_idx ?? 2)
                        return (
                          <td key={ci} className={`p-1.5 text-center ${isBase ? 'ring-1 ring-blue-500 rounded' : ''}`} style={{
                            color: mos > 20 ? '#22c55e' : mos > 0 ? '#4ade80' : mos > -10 ? '#eab308' : '#ef4444',
                            background: mos > 20 ? '#22c55e08' : mos < -10 ? '#ef444408' : 'transparent',
                          }}>
                            ${fmt(val, 0)}
                          </td>
                        )
                      })}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="flex gap-4 mt-2 text-[9px] text-[#8b8d97]">
            <span><span className="text-green-400">Green</span> = undervalued (MoS &gt; 20%)</span>
            <span><span className="text-yellow-400">Yellow</span> = fairly valued</span>
            <span><span className="text-red-400">Red</span> = overvalued</span>
            <span><span className="text-blue-400">Blue</span> = base case</span>
          </div>
        </Card>
      )}

      {/* Probability-Weighted Scenarios */}
      {Object.keys(scenarios).length > 0 && (
        <Card>
          <div className="flex items-center gap-3 mb-3">
            <h3 className="text-sm font-semibold">Probability-Weighted Scenarios</h3>
            <Badge color={hasLLMScenarios ? '#3b82f6' : '#6b7280'}>
              {hasLLMScenarios ? 'LLM-Validated' : 'Mechanical'}
            </Badge>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {['bear', 'base', 'bull'].map(s => {
              const sc = scenarios[s]
              if (!sc) return null
              const color = s === 'bull' ? '#22c55e' : s === 'bear' ? '#ef4444' : '#3b82f6'
              const icon = s === 'bull' ? '\uD83D\uDCC8' : s === 'bear' ? '\uD83D\uDCC9' : '\u2696\uFE0F'
              const prob = sc.probability != null ? `${(sc.probability * 100).toFixed(0)}%` : ''
              const refPrice = scenarioPrice || dcf.current_price
              return (
                <div key={s} className="p-4 rounded-lg border" style={{ borderColor: `${color}30`, background: `${color}08` }}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm">{icon}</span>
                    <Badge color={color}>{s.toUpperCase()}</Badge>
                    {prob && <span className="text-[10px] text-[#8b8d97]">({prob} weight)</span>}
                  </div>
                  <div className="flex items-baseline gap-2 mb-2">
                    <div className="text-xl font-bold font-mono" style={{ color }}>
                      ${fmt(sc.intrinsic_per_share ?? sc.fair_value_per_share, 2)}
                    </div>
                    {refPrice && sc.intrinsic_per_share != null && (
                      <div className="text-xs font-mono" style={{ color }}>
                        {sc.intrinsic_per_share > refPrice ? '+' : ''}
                        {fmt(((sc.intrinsic_per_share - refPrice) / refPrice) * 100, 1)}%
                      </div>
                    )}
                  </div>
                  {/* LLM Narrative */}
                  {sc.narrative && (
                    <div className="text-[11px] text-[#c8c9ce] italic mb-3 leading-relaxed border-l-2 pl-2" style={{ borderColor: `${color}40` }}>
                      {sc.narrative}
                    </div>
                  )}
                  <div className="space-y-1 text-[10px] text-[#8b8d97]">
                    <div>Growth: {fmt((sc.growth_rate || 0) * 100, 1)}%</div>
                    <div>WACC: {fmt((sc.wacc || sc.discount_rate || 0) * 100, 1)}%</div>
                    <div>Terminal: {fmt((sc.terminal_growth || 0) * 100, 1)}%</div>
                    {sc.enterprise_value != null && <div>EV: {fmtCurrency(sc.enterprise_value)}</div>}
                  </div>
                  {/* Key Drivers */}
                  {sc.key_drivers && sc.key_drivers.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-3">
                      {sc.key_drivers.map((d, i) => (
                        <span key={i} className="text-[9px] px-1.5 py-0.5 rounded-full border" style={{ borderColor: `${color}30`, color: `${color}cc`, background: `${color}10` }}>
                          {d}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
          {/* Probability-weighted summary */}
          {probWeighted != null && (
            <div className="mt-3 flex flex-wrap items-center gap-3 sm:gap-4 bg-[#0f1117] rounded-lg p-3">
              <div className="text-xs text-[#8b8d97]">Probability-Weighted Fair Value:</div>
              <div className="text-lg font-bold font-mono text-purple-400">${fmt(probWeighted, 2)}</div>
              {(scenarioPrice || dcf.current_price) && (
                <div className={`text-xs font-mono ${probWeighted > (scenarioPrice || dcf.current_price) ? 'text-green-400' : 'text-red-400'}`}>
                  ({probWeighted > (scenarioPrice || dcf.current_price) ? '+' : ''}{fmt(((probWeighted - (scenarioPrice || dcf.current_price)) / (scenarioPrice || dcf.current_price)) * 100, 1)}%)
                </div>
              )}
              {riskReward != null && (
                <div className="ml-auto text-xs">
                  <span className="text-[#8b8d97]">Risk/Reward: </span>
                  <span className={`font-bold font-mono ${riskReward > 1.5 ? 'text-green-400' : riskReward > 1 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {fmt(riskReward, 2)}x
                  </span>
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      {/* Analyst Price Targets */}
      {analyst && analyst.available && (
        <Card>
          <h3 className="text-sm font-semibold mb-3">Analyst Price Targets</h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-xs">
            <div>
              <div className="text-[#8b8d97]">Low</div>
              <div className="font-bold font-mono text-red-400">${fmt(analyst.low, 2)}</div>
            </div>
            <div>
              <div className="text-[#8b8d97]">Mean</div>
              <div className="font-bold font-mono">${fmt(analyst.mean, 2)}</div>
            </div>
            <div>
              <div className="text-[#8b8d97]">Median</div>
              <div className="font-bold font-mono text-blue-400">${fmt(analyst.median, 2)}</div>
            </div>
            <div>
              <div className="text-[#8b8d97]">High</div>
              <div className="font-bold font-mono text-green-400">${fmt(analyst.high, 2)}</div>
            </div>
            <div>
              <div className="text-[#8b8d97]">Analysts</div>
              <div className="font-bold font-mono">{analyst.count}</div>
              {analyst.recommendation && (
                <div className="text-[9px] text-[#8b8d97] capitalize">{analyst.recommendation}</div>
              )}
            </div>
          </div>
          {/* Visual range bar */}
          {dcf.current_price && analyst.low != null && analyst.high != null && (
            <div className="mt-3">
              <div className="relative h-4 bg-[#0f1117] rounded-full overflow-hidden">
                {(() => {
                  const lo = analyst.low, hi = analyst.high, cur = dcf.current_price
                  const range = hi - lo
                  if (range <= 0) return null
                  const curPct = Math.max(0, Math.min(100, ((cur - lo) / range) * 100))
                  const meanPct = analyst.mean ? Math.max(0, Math.min(100, ((analyst.mean - lo) / range) * 100)) : null
                  return (
                    <>
                      <div className="absolute h-full bg-gradient-to-r from-red-500/20 via-yellow-500/20 to-green-500/20 w-full" />
                      <div className="absolute top-0 bottom-0 w-0.5 bg-white" style={{ left: `${curPct}%` }} title={`Current: $${cur}`} />
                      {meanPct != null && (
                        <div className="absolute top-0 bottom-0 w-0.5 bg-blue-400 opacity-50" style={{ left: `${meanPct}%` }} title={`Mean: $${analyst.mean}`} />
                      )}
                    </>
                  )
                })()}
              </div>
              <div className="flex justify-between text-[9px] text-[#8b8d97] mt-1">
                <span>${fmt(analyst.low, 0)}</span>
                <span>Current: ${fmt(dcf.current_price, 2)}</span>
                <span>${fmt(analyst.high, 0)}</span>
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Comparables */}
      {comps.comparison && Object.keys(comps.comparison).length > 0 && (
        <Card>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold">Comparable Valuation</h3>
            {comps.peers && comps.peers.length > 0 && (
              <div className="text-[10px] text-[#8b8d97]">
                Peers: {comps.peers.join(', ')}
              </div>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-[#a0a2ab] border-b border-[#2a2d3e] text-[10px] uppercase tracking-wider">
                  <th className="text-left py-2 pr-2 font-semibold">Metric</th>
                  <th className="text-right py-2 pr-2 font-semibold">Stock</th>
                  <th className="text-right py-2 pr-2 font-semibold">Peer Median</th>
                  <th className="text-right py-2 font-semibold">Premium</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(comps.comparison).map(([metric, vals]) => (
                  <tr key={metric} className="border-b border-[#2a2d3e]/30">
                    <td className="py-1.5 pr-2 text-[#8b8d97]">{metric.replace(/_/g, ' ').toUpperCase()}</td>
                    <td className="py-1.5 pr-2 text-right font-mono">{fmt(vals.company ?? vals.stock, 2)}</td>
                    <td className="py-1.5 pr-2 text-right font-mono">{fmt(vals.peer_median ?? vals.peer_avg, 2)}</td>
                    <td className={`py-1.5 text-right font-mono ${(vals.premium_pct || 0) > 0 ? 'text-red-400' : 'text-green-400'}`}>
                      {vals.premium_pct != null ? `${(vals.premium_pct > 0 ? '+' : '')}${fmt(vals.premium_pct, 1)}%` : '\u2014'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}

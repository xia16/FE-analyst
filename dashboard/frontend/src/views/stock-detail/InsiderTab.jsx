import { Card, Badge, SIGNAL_COLORS, fmt, fmtCurrency } from '../../components/shared'

export default function InsiderTab({ analysis }) {
  const insider = analysis?.insider_congress
  if (!insider) return <div className="text-[#8b8d97] text-center py-8">No insider/congressional data available.</div>
  if (insider.error) return <div className="text-red-400 text-center py-8">Error: {insider.error}</div>

  const signal = insider.signal || 'NEUTRAL'
  const insiderTrades = insider.insider_trades || []
  const congressTrades = insider.congressional_trades || []
  const whaleData = insider.whale_tracking || insider.institutional || null
  const shortInterest = insider.short_interest || null

  return (
    <div className="space-y-6">
      {/* Signal summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="text-center">
          <div className="text-[#8b8d97] text-xs mb-1">Combined Signal</div>
          <div className="text-2xl font-bold" style={{ color: SIGNAL_COLORS[signal] || '#8b8d97' }}>
            {signal}
          </div>
        </Card>
        <Card className="text-center">
          <div className="text-[#8b8d97] text-xs mb-1">Total Buys</div>
          <div className="text-2xl font-bold text-green-400">{insider.total_buys || 0}</div>
        </Card>
        <Card className="text-center">
          <div className="text-[#8b8d97] text-xs mb-1">Total Sells</div>
          <div className="text-2xl font-bold text-red-400">{insider.total_sells || 0}</div>
        </Card>
        <Card className="text-center">
          <div className="text-[#8b8d97] text-xs mb-1">Buy/Sell Ratio</div>
          <div className="text-2xl font-bold font-mono">
            {insider.total_sells ? fmt(insider.total_buys / insider.total_sells, 2) : '\u221E'}
          </div>
        </Card>
      </div>

      {/* Short Interest */}
      {shortInterest && !shortInterest.error && (
        <Card>
          <h3 className="text-sm font-semibold mb-3">Short Interest</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
            {shortInterest.short_pct_float != null && (
              <div>
                <div className="text-[#8b8d97]">Short % of Float</div>
                <div className={`font-bold font-mono text-lg ${shortInterest.short_pct_float > 20 ? 'text-red-400' : shortInterest.short_pct_float > 10 ? 'text-yellow-400' : 'text-green-400'}`}>
                  {fmt(shortInterest.short_pct_float, 1)}%
                </div>
              </div>
            )}
            {shortInterest.short_ratio != null && (
              <div>
                <div className="text-[#8b8d97]">Days to Cover</div>
                <div className={`font-bold font-mono text-lg ${shortInterest.short_ratio > 5 ? 'text-red-400' : shortInterest.short_ratio > 3 ? 'text-yellow-400' : ''}`}>
                  {fmt(shortInterest.short_ratio, 1)}
                </div>
              </div>
            )}
            {shortInterest.shares_short != null && (
              <div>
                <div className="text-[#8b8d97]">Shares Short</div>
                <div className="font-bold font-mono">{(shortInterest.shares_short / 1e6).toFixed(1)}M</div>
              </div>
            )}
            {shortInterest.short_change_pct != null && (
              <div>
                <div className="text-[#8b8d97]">Short Change (MoM)</div>
                <div className={`font-bold font-mono ${shortInterest.short_change_pct > 0 ? 'text-red-400' : 'text-green-400'}`}>
                  {shortInterest.short_change_pct > 0 ? '+' : ''}{fmt(shortInterest.short_change_pct, 1)}%
                </div>
              </div>
            )}
          </div>
          {shortInterest.as_of && (
            <div className="mt-2 text-[9px] text-[#8b8d97]">As of: {shortInterest.as_of}</div>
          )}
        </Card>
      )}

      {/* Whale / Institutional Tracking */}
      {whaleData && !whaleData.error && (
        <Card>
          <h3 className="text-sm font-semibold mb-3">Institutional / Whale Tracking</h3>
          {/* Summary metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs mb-4">
            {whaleData.institutional_pct != null && (
              <div>
                <div className="text-[#8b8d97]">Institutional Ownership</div>
                <div className="font-bold font-mono text-lg">{fmt(whaleData.institutional_pct, 1)}%</div>
              </div>
            )}
            {whaleData.insider_pct != null && (
              <div>
                <div className="text-[#8b8d97]">Insider Ownership</div>
                <div className="font-bold font-mono text-lg">{fmt(whaleData.insider_pct, 1)}%</div>
              </div>
            )}
            {whaleData.num_institutions != null && (
              <div>
                <div className="text-[#8b8d97]"># Institutions</div>
                <div className="font-bold font-mono text-lg">{whaleData.num_institutions.toLocaleString()}</div>
              </div>
            )}
            {whaleData.net_institutional_change != null && (
              <div>
                <div className="text-[#8b8d97]">Net Change (QoQ)</div>
                <div className={`font-bold font-mono text-lg ${whaleData.net_institutional_change > 0 ? 'text-green-400' : whaleData.net_institutional_change < 0 ? 'text-red-400' : ''}`}>
                  {whaleData.net_institutional_change > 0 ? '+' : ''}{fmt(whaleData.net_institutional_change, 1)}%
                </div>
              </div>
            )}
          </div>
          {/* Top holders */}
          {whaleData.top_holders && whaleData.top_holders.length > 0 && (
            <div>
              <div className="text-[10px] text-[#8b8d97] uppercase tracking-wider mb-2">Top Holders</div>
              <div className="overflow-x-auto">
                <table className="w-full text-[11px]">
                  <thead>
                    <tr className="text-[#a0a2ab] border-b border-[#2a2d3e] text-[10px] uppercase tracking-wider">
                      <th className="text-left py-2 pr-2 font-semibold">Holder</th>
                      <th className="text-right py-2 pr-2 font-semibold">Shares</th>
                      <th className="text-right py-2 pr-2 font-semibold">% Held</th>
                      {whaleData.top_holders.some(h => h.value != null) && (
                        <th className="text-right py-2 font-semibold">Value</th>
                      )}
                      {whaleData.top_holders.some(h => h.change != null) && (
                        <th className="text-right py-2 font-semibold">Change</th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {whaleData.top_holders.map((h, i) => (
                      <tr key={i} className="border-b border-[#2a2d3e]/30">
                        <td className="py-1.5 pr-2 max-w-[200px] truncate">{h.name || h.holder}</td>
                        <td className="py-1.5 pr-2 text-right font-mono">
                          {h.shares != null ? (h.shares >= 1e6 ? `${(h.shares / 1e6).toFixed(1)}M` : h.shares.toLocaleString()) : '\u2014'}
                        </td>
                        <td className="py-1.5 pr-2 text-right font-mono">
                          {h.pct_held != null ? `${fmt(h.pct_held, 2)}%` : '\u2014'}
                        </td>
                        {whaleData.top_holders.some(h => h.value != null) && (
                          <td className="py-1.5 text-right font-mono">
                            {h.value != null ? fmtCurrency(h.value) : '\u2014'}
                          </td>
                        )}
                        {whaleData.top_holders.some(h => h.change != null) && (
                          <td className={`py-1.5 text-right font-mono ${(h.change || 0) > 0 ? 'text-green-400' : (h.change || 0) < 0 ? 'text-red-400' : ''}`}>
                            {h.change != null ? `${h.change > 0 ? '+' : ''}${h.change.toLocaleString()}` : '\u2014'}
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {/* Recent institutional filings */}
          {whaleData.recent_filings && whaleData.recent_filings.length > 0 && (
            <div className="mt-4">
              <div className="text-[10px] text-[#8b8d97] uppercase tracking-wider mb-2">Recent Institutional Filings</div>
              <div className="space-y-1.5">
                {whaleData.recent_filings.map((f, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs p-2 rounded bg-[#0f1117]">
                    <Badge color={(f.type || '').toLowerCase().includes('buy') || (f.action || '').toLowerCase().includes('buy') ? '#22c55e' : '#ef4444'}>
                      {f.type || f.action || 'FILING'}
                    </Badge>
                    <span className="flex-1 truncate">{f.name || f.filer}</span>
                    <span className="text-[#8b8d97] font-mono">{f.shares ? `${(f.shares / 1e6).toFixed(1)}M` : ''}</span>
                    <span className="text-[#8b8d97]">{f.date}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Insider trades table */}
      <Card>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold">Insider Trades (SEC Form 4)</h3>
          <div className="flex gap-2 text-[10px]">
            <span className="text-green-400">{insider.insider_buys || 0} buys</span>
            <span className="text-red-400">{insider.insider_sells || 0} sells</span>
          </div>
        </div>
        {insiderTrades.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="text-[#a0a2ab] border-b border-[#2a2d3e] text-[10px] uppercase tracking-wider">
                  <th className="text-left py-2 pr-2 font-semibold">Date</th>
                  <th className="text-left py-2 pr-2 font-semibold">Name</th>
                  <th className="text-center py-2 pr-2 font-semibold">Type</th>
                  <th className="text-right py-2 pr-2 font-semibold">Shares</th>
                  <th className="text-right py-2 pr-2 font-semibold">Price</th>
                  <th className="text-right py-2 font-semibold">Value</th>
                </tr>
              </thead>
              <tbody>
                {insiderTrades.map((t, i) => {
                  const isBuy = t.transaction_code === 'P'
                  return (
                    <tr key={i} className="border-b border-[#2a2d3e]/30">
                      <td className="py-1.5 pr-2 text-[#8b8d97]">{t.date}</td>
                      <td className="py-1.5 pr-2 max-w-[160px] truncate">{t.name}</td>
                      <td className="py-1.5 pr-2 text-center">
                        <Badge color={isBuy ? '#22c55e' : '#ef4444'}>
                          {isBuy ? 'BUY' : t.transaction_code === 'S' ? 'SELL' : t.transaction_code}
                        </Badge>
                      </td>
                      <td className="py-1.5 pr-2 text-right font-mono">{t.shares?.toLocaleString()}</td>
                      <td className="py-1.5 pr-2 text-right font-mono">${fmt(t.price, 2)}</td>
                      <td className="py-1.5 text-right font-mono">${t.value ? (t.value >= 1e6 ? `${(t.value/1e6).toFixed(1)}M` : t.value.toLocaleString()) : '\u2014'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-6 text-[#8b8d97] text-xs">No insider trades found</div>
        )}
      </Card>

      {/* Congressional trades table */}
      <Card>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold">Congressional Trades</h3>
          <div className="flex gap-2 text-[10px]">
            <span className="text-green-400">{insider.congress_buys || 0} buys</span>
            <span className="text-red-400">{insider.congress_sells || 0} sells</span>
          </div>
        </div>
        {congressTrades.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="text-[#a0a2ab] border-b border-[#2a2d3e] text-[10px] uppercase tracking-wider">
                  <th className="text-left py-2 pr-2 font-semibold">Date</th>
                  <th className="text-left py-2 pr-2 font-semibold">Name</th>
                  <th className="text-center py-2 pr-2 font-semibold">Chamber</th>
                  <th className="text-center py-2 pr-2 font-semibold">Type</th>
                  <th className="text-left py-2 pr-2 font-semibold">Amount</th>
                  <th className="text-left py-2 font-semibold">Description</th>
                </tr>
              </thead>
              <tbody>
                {congressTrades.map((t, i) => {
                  const isBuy = (t.type || '').toLowerCase().includes('purchase') || (t.type || '').toLowerCase().includes('buy')
                  return (
                    <tr key={i} className="border-b border-[#2a2d3e]/30">
                      <td className="py-1.5 pr-2 text-[#8b8d97]">{t.date}</td>
                      <td className="py-1.5 pr-2 max-w-[140px] truncate">{t.name}</td>
                      <td className="py-1.5 pr-2 text-center">
                        <Badge color={t.chamber === 'Senate' ? '#a855f7' : '#3b82f6'}>{t.chamber}</Badge>
                      </td>
                      <td className="py-1.5 pr-2 text-center">
                        <Badge color={isBuy ? '#22c55e' : '#ef4444'}>{t.type}</Badge>
                      </td>
                      <td className="py-1.5 pr-2 text-[#8b8d97]">{t.amount_range}</td>
                      <td className="py-1.5 text-[#8b8d97] max-w-[200px] truncate">{t.description}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-6 text-[#8b8d97] text-xs">No congressional trades found</div>
        )}
      </Card>
    </div>
  )
}

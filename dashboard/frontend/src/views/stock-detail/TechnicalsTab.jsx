import { useState } from 'react'
import { useTechnicals, useHistory } from '../../hooks'
import { Card, Spinner, fmt, fmtPct } from '../../components/shared'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'

export default function TechnicalsTab({ ticker }) {
  const [period, setPeriod] = useState('6mo')
  const { data: techData, loading: techLoading } = useTechnicals(ticker)
  const { data: histData, loading: histLoading } = useHistory(ticker, period)

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold">Price History</h3>
          <div className="flex gap-1">
            {['1mo', '3mo', '6mo', '1y', '2y'].map(p => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-2 py-1 rounded text-[10px] font-medium transition-colors ${
                  period === p ? 'bg-[#3b82f6] text-white' : 'text-[#8b8d97] hover:text-white hover:bg-[#252940]'
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>
        {histLoading ? <Spinner /> : histData?.data ? (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={histData.data}>
              <defs>
                <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3e" />
              <XAxis
                dataKey="date"
                tick={{ fill: '#8b8d97', fontSize: 9 }}
                tickFormatter={d => new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                minTickGap={40}
              />
              <YAxis tick={{ fill: '#8b8d97', fontSize: 10 }} domain={['auto', 'auto']} />
              <Tooltip
                contentStyle={{ background: '#1a1d2e', border: '1px solid rgba(59,130,246,0.3)', borderRadius: 8, fontSize: 11, boxShadow: '0 4px 12px rgba(0,0,0,0.4)' }}
                labelFormatter={d => new Date(d).toLocaleDateString()}
                formatter={(v) => [fmt(v), 'Close']}
              />
              <Area type="monotone" dataKey="close" stroke="#3b82f6" fill="url(#colorPrice)" strokeWidth={1.5} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        ) : <div className="text-[#8b8d97] text-center py-8">No chart data</div>}
      </Card>

      {techLoading ? <Spinner /> : techData && !techData.error && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <h3 className="text-sm font-semibold mb-4">Technical Indicators</h3>
            <div className="space-y-3">
              <div>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-[#8b8d97]">RSI (14)</span>
                  <span className={`font-bold ${
                    techData.rsi < 30 ? 'text-green-400' : techData.rsi > 70 ? 'text-red-400' : 'text-white'
                  }`}>{fmt(techData.rsi, 1)}</span>
                </div>
                <div className="h-2 bg-[#0f1117] rounded-full overflow-hidden relative">
                  <div className="absolute inset-0 flex">
                    <div className="w-[30%] bg-green-500/20" />
                    <div className="w-[40%] bg-gray-500/10" />
                    <div className="w-[30%] bg-red-500/20" />
                  </div>
                  <div
                    className="absolute top-0 h-full w-1 bg-white rounded-full"
                    style={{ left: `${Math.min(100, Math.max(0, techData.rsi))}%` }}
                  />
                </div>
                <div className="flex justify-between text-[9px] text-[#8b8d97] mt-0.5">
                  <span>Oversold</span><span>Neutral</span><span>Overbought</span>
                </div>
              </div>

              <div className="flex items-center justify-between text-xs">
                <span className="text-[#8b8d97]">MACD Histogram</span>
                <span className={`font-bold ${(techData.macd || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {fmt(techData.macd, 4)}
                </span>
              </div>

              <div>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-[#8b8d97]">Bollinger Band Position</span>
                  <span className="font-bold">{fmt((techData.bbPosition || 0) * 100, 0)}%</span>
                </div>
                <div className="h-2 bg-[#0f1117] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 rounded-full transition-all"
                    style={{ width: `${(techData.bbPosition || 0) * 100}%` }}
                  />
                </div>
                <div className="flex justify-between text-[9px] text-[#8b8d97] mt-0.5">
                  <span>Lower Band</span><span>Upper Band</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="text-xs">
                  <span className="text-[#8b8d97]">SMA 50</span>
                  <div className="font-mono font-bold">{fmt(techData.sma50)}</div>
                </div>
                <div className="text-xs">
                  <span className="text-[#8b8d97]">SMA 200</span>
                  <div className="font-mono font-bold">{techData.sma200 ? fmt(techData.sma200) : '\u2014'}</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="text-xs">
                  <span className="text-[#8b8d97]">From 52W High</span>
                  <div className={`font-mono font-bold ${(techData.distFromHigh || 0) < -20 ? 'text-yellow-400' : ''}`}>
                    {fmtPct(techData.distFromHigh)}
                  </div>
                </div>
                <div className="text-xs">
                  <span className="text-[#8b8d97]">From 52W Low</span>
                  <div className="font-mono font-bold text-green-400">{fmtPct(techData.distFromLow)}</div>
                </div>
              </div>
            </div>
          </Card>

          <Card>
            <h3 className="text-sm font-semibold mb-4">Active Signals</h3>
            {techData.signals?.length > 0 ? (
              <div className="space-y-2">
                {techData.signals.map((s, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 p-2 rounded-lg"
                    style={{ background: s.bullish ? '#22c55e10' : '#ef444410' }}
                  >
                    <span className={`text-lg ${s.bullish ? 'text-green-400' : 'text-red-400'}`}>
                      {s.bullish ? '\u25B2' : '\u25BC'}
                    </span>
                    <div>
                      <div className="text-xs font-semibold" style={{ color: s.bullish ? '#22c55e' : '#ef4444' }}>
                        {s.type.replace(/_/g, ' ')}
                      </div>
                      <div className="text-[10px] text-[#8b8d97]">{s.message}</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-[#8b8d97] text-xs">
                No active technical signals
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  )
}

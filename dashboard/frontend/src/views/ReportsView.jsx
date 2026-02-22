import React, { useState, useEffect } from 'react'
import { useReports, useReport, useProfiles } from '../hooks'
import { Card, Spinner } from '../components/shared'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// ─── Report Type Metadata ────────────────────────────────

const REPORT_TYPE_META = {
  research:   { label: 'Research',   color: '#a855f7' },
  quick:      { label: 'Quick',      color: '#22c55e' },
  comparison: { label: 'Comparison', color: '#3b82f6' },
  screening:  { label: 'Screening',  color: '#f59e0b' },
  analysis:   { label: 'Analysis',   color: '#8b8d97' },
}

const REPORT_TYPE_ORDER = ['research', 'quick', 'comparison', 'screening', 'analysis']

const PROFILE_COLORS = {
  quick: '#22c55e',
  full: '#3b82f6',
  deep_dive: '#a855f7',
  comparison: '#f59e0b',
  screening: '#ec4899',
}

// ─── Reports View ────────────────────────────────────────

export function ReportsView({ initialPath }) {
  const { data, loading, error, refetch } = useReports()
  const [selectedPath, setSelectedPath] = useState(initialPath || null)
  const [typeFilter, setTypeFilter] = useState(null)
  const [archiving, setArchiving] = useState(null)
  const { data: reportData, loading: reportLoading } = useReport(selectedPath)

  // Consume initialPath when it changes (from Generate → View Report flow)
  useEffect(() => {
    if (initialPath) setSelectedPath(initialPath)
  }, [initialPath])

  const handleArchive = async (e, path) => {
    e.stopPropagation()
    setArchiving(path)
    try {
      await fetch(`/api/reports/archive?path=${encodeURIComponent(path)}`, { method: 'POST' })
      if (selectedPath === path) setSelectedPath(null)
      refetch()
    } finally {
      setArchiving(null)
    }
  }

  if (loading) return <Spinner />
  if (error) return <div className="text-red-400 p-4">Error: {error}</div>

  const allReports = data?.reports || []
  const filtered = typeFilter ? allReports.filter(r => r.type === typeFilter) : allReports

  const grouped = {}
  for (const r of filtered) {
    const t = r.type || 'analysis'
    if (!grouped[t]) grouped[t] = []
    grouped[t].push(r)
  }

  const typeCounts = {}
  for (const r of allReports) {
    typeCounts[r.type] = (typeCounts[r.type] || 0) + 1
  }

  return (
    <div className="space-y-4 animate-slide-in">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">Analysis Reports</h2>
        <span className="text-xs text-[#8b8d97]">{allReports.length} reports</span>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => setTypeFilter(null)}
          className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
            !typeFilter ? 'bg-[#3b82f6] text-white' : 'bg-[#1e2130] text-[#8b8d97] hover:text-white'
          }`}
        >
          All ({allReports.length})
        </button>
        {REPORT_TYPE_ORDER.filter(t => typeCounts[t]).map(t => {
          const meta = REPORT_TYPE_META[t]
          return (
            <button
              key={t}
              onClick={() => setTypeFilter(typeFilter === t ? null : t)}
              className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors flex items-center gap-1.5 ${
                typeFilter === t ? 'text-white' : 'bg-[#1e2130] text-[#8b8d97] hover:text-white'
              }`}
              style={typeFilter === t ? { background: meta.color } : {}}
            >
              <div className="w-1.5 h-1.5 rounded-full" style={{ background: meta.color }} />
              {meta.label} ({typeCounts[t]})
            </button>
          )
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-4 space-y-3 max-h-[78vh] overflow-y-auto pr-1">
          {allReports.length === 0 ? (
            <Card>
              <div className="text-center py-8 text-[#8b8d97] text-xs">
                <p>No reports yet.</p>
                <p className="mt-1">Go to Analyze tab to generate one.</p>
              </div>
            </Card>
          ) : REPORT_TYPE_ORDER.filter(t => grouped[t]).map(t => {
            const meta = REPORT_TYPE_META[t]
            const reports = grouped[t]
            return (
              <div key={t}>
                <div className="flex items-center gap-2 mb-1.5 px-1">
                  <div className="w-2 h-2 rounded-full" style={{ background: meta.color }} />
                  <span className="text-[11px] font-semibold" style={{ color: meta.color }}>{meta.label}</span>
                  <span className="text-[10px] text-[#8b8d97]">({reports.length})</span>
                </div>
                <div className="space-y-1">
                  {reports.map(r => (
                    <div
                      key={r.path}
                      onClick={() => setSelectedPath(r.path)}
                      className={`group p-2.5 rounded-lg cursor-pointer transition-colors border ${
                        selectedPath === r.path
                          ? 'bg-[#252940] border-[#3b82f6]'
                          : 'bg-[#1e2130] border-[#2a2d3e] hover:bg-[#252940]'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="text-xs font-semibold truncate">{r.title}</div>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-[10px] text-[#8b8d97]">
                              {new Date(r.modified).toLocaleDateString()}
                            </span>
                            <span className="text-[10px] text-[#8b8d97]">
                              {r.size >= 1024 ? `${(r.size / 1024).toFixed(0)} KB` : `${r.size} B`}
                            </span>
                          </div>
                          {r.tickers?.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-1.5">
                              {r.tickers.map(tk => (
                                <span key={tk} className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-[#0f1117] text-[#8b8d97]">
                                  {tk}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        <button
                          onClick={(e) => handleArchive(e, r.path)}
                          className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-[#0f1117] transition-all text-[#8b8d97] hover:text-red-400 flex-shrink-0"
                          title="Archive report"
                        >
                          {archiving === r.path ? (
                            <div className="w-3 h-3 border border-[#8b8d97] border-t-transparent rounded-full animate-spin" />
                          ) : (
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
                            </svg>
                          )}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>

        <Card className="lg:col-span-8 max-h-[78vh] overflow-y-auto">
          {!selectedPath ? (
            <div className="text-center py-12 text-[#8b8d97]">
              <p>Select a report from the list to view it.</p>
            </div>
          ) : reportLoading ? (
            <Spinner />
          ) : reportData?.content ? (
            <div className="markdown-report">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {reportData.content}
              </ReactMarkdown>
            </div>
          ) : (
            <div className="text-center py-12 text-[#8b8d97]">Failed to load report.</div>
          )}
        </Card>
      </div>
    </div>
  )
}

// ─── Generate Report View ────────────────────────────────

export function GenerateReportView({ onViewReport }) {
  const { data: profileData, loading: profileLoading } = useProfiles()
  const [ticker, setTicker] = useState('')
  const [selectedProfile, setSelectedProfile] = useState('full')
  const [jobId, setJobId] = useState(null)
  const [jobStatus, setJobStatus] = useState(null)
  const [generating, setGenerating] = useState(false)

  useEffect(() => {
    if (!jobId) return
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/reports/job/${jobId}`)
        const job = await res.json()
        setJobStatus(job)
        if (job.status === 'completed' || job.status === 'failed') {
          clearInterval(interval)
          setGenerating(false)
        }
      } catch {
        // keep polling
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [jobId])

  const handleGenerate = async () => {
    if (!ticker.trim()) return
    setGenerating(true)
    setJobStatus(null)
    try {
      const res = await fetch(`/api/reports/generate?ticker=${encodeURIComponent(ticker.trim().toUpperCase())}&profile=${selectedProfile}`, {
        method: 'POST',
      })
      const data = await res.json()
      if (data.job_id) {
        setJobId(data.job_id)
        setJobStatus({ status: 'queued' })
      } else {
        setJobStatus({ status: 'failed', error: data.detail || 'Unknown error' })
        setGenerating(false)
      }
    } catch (err) {
      setJobStatus({ status: 'failed', error: err.message })
      setGenerating(false)
    }
  }

  const profiles = profileData?.profiles || {}

  return (
    <div className="space-y-6 animate-slide-in">
      <div>
        <h2 className="text-lg font-bold">Generate Analysis Report</h2>
        <p className="text-xs text-[#8b8d97]">
          Enter a ticker and select an analysis profile. The pipeline runs locally using your Python analysis engine.
        </p>
      </div>

      <Card>
        <label className="text-xs text-[#8b8d97] mb-2 block">Ticker Symbol</label>
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="e.g. ASML, HTHIY, TSM, 8035.T"
          className="w-full bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-4 py-2.5 text-sm font-mono focus:outline-none focus:border-[#3b82f6] transition-colors"
          onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
        />
      </Card>

      <div>
        <h3 className="text-sm font-semibold mb-3">Analysis Profile</h3>
        {profileLoading ? <Spinner /> : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
            {Object.entries(profiles).map(([key, p]) => (
              <div
                key={key}
                onClick={() => setSelectedProfile(key)}
                className={`p-3 rounded-lg cursor-pointer transition-all border-2 ${
                  selectedProfile === key
                    ? 'border-[#3b82f6] bg-[#252940]'
                    : 'border-[#2a2d3e] bg-[#1e2130] hover:border-[#3b82f6]/50'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ background: PROFILE_COLORS[key] || '#3b82f6' }} />
                  <span className="text-xs font-semibold capitalize">{key.replace(/_/g, ' ')}</span>
                </div>
                <p className="text-[10px] text-[#8b8d97] line-clamp-2">{p.description}</p>
                <div className="flex flex-wrap gap-1 mt-2">
                  {(p.analyzers === 'all' ? ['all analyzers'] : p.analyzers || []).map(a => (
                    <span key={a} className="px-1.5 py-0.5 rounded text-[9px] bg-[#0f1117] text-[#8b8d97]">{a}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <button
        onClick={handleGenerate}
        disabled={generating || !ticker.trim()}
        className="px-6 py-3 bg-[#3b82f6] text-white text-sm font-medium rounded-lg hover:bg-[#2563eb] disabled:opacity-50 transition-colors"
      >
        {generating ? 'Generating...' : 'Generate Report'}
      </button>

      {jobStatus && (
        <Card>
          {jobStatus.status === 'queued' || jobStatus.status === 'running' ? (
            <div className="flex items-center gap-3">
              <div className="w-5 h-5 border-2 border-[#3b82f6] border-t-transparent rounded-full animate-spin" />
              <div>
                <div className="text-sm font-semibold">
                  {jobStatus.status === 'queued' ? 'Queued...' : 'Running analysis pipeline...'}
                </div>
                <div className="text-[10px] text-[#8b8d97]">
                  This may take 30-120 seconds depending on the profile.
                </div>
              </div>
            </div>
          ) : jobStatus.status === 'completed' ? (
            <div>
              <div className="text-sm font-semibold text-green-400 mb-2">Report generated!</div>
              <button
                onClick={() => onViewReport(jobStatus.report_path)}
                className="px-4 py-2 bg-[#22c55e] text-white text-xs font-medium rounded-lg hover:bg-[#16a34a] transition-colors"
              >
                View Report
              </button>
            </div>
          ) : jobStatus.status === 'failed' ? (
            <div>
              <div className="text-sm font-semibold text-red-400 mb-1">Generation failed</div>
              <pre className="text-[10px] text-[#8b8d97] whitespace-pre-wrap max-h-40 overflow-y-auto bg-[#0f1117] rounded p-2">
                {jobStatus.error}
              </pre>
            </div>
          ) : null}
        </Card>
      )}
    </div>
  )
}

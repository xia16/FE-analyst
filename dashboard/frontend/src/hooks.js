import { useState, useEffect, useCallback, useRef } from 'react'

const API = '/api'

export function useFetch(path, options = {}) {
  const { refreshInterval, enabled = true } = options
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const intervalRef = useRef(null)

  const fetchData = useCallback(async () => {
    if (!enabled) return
    try {
      const res = await fetch(`${API}${path}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      setData(json)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [path, enabled])

  useEffect(() => {
    setLoading(true)
    fetchData()
    if (refreshInterval) {
      intervalRef.current = setInterval(fetchData, refreshInterval)
      return () => clearInterval(intervalRef.current)
    }
  }, [fetchData, refreshInterval])

  return { data, loading, error, refetch: fetchData }
}

// ─── Domain hooks ─────────────────────────────────────────

export function useDomains() {
  return useFetch('/domains')
}

export function useDomainMeta(domainId) {
  return useFetch(`/domains/${domainId}`, { enabled: !!domainId })
}

export function useDomainPortfolio(domainId) {
  return useFetch(`/domains/${domainId}/portfolio`, { enabled: !!domainId, refreshInterval: 60000 })
}

export function useDomainUniverse(domainId) {
  return useFetch(`/domains/${domainId}/universe`, { enabled: !!domainId })
}

export function useDomainHeatmap(domainId) {
  return useFetch(`/domains/${domainId}/heatmap`, { enabled: !!domainId })
}

// ─── Global hooks ─────────────────────────────────────────

export function useAlerts() {
  return useFetch('/alerts', { refreshInterval: 30000 })
}

export function useTechnicals(ticker) {
  return useFetch(`/technicals/${ticker}`, { enabled: !!ticker })
}

export function useHistory(ticker, period = '6mo') {
  return useFetch(`/history/${ticker}?period=${period}`, { enabled: !!ticker })
}

export function useReports() {
  return useFetch('/reports')
}

export function useReport(path) {
  return useFetch(`/reports/${path}`, { enabled: !!path })
}

export function useProfiles() {
  return useFetch('/profiles')
}

// ─── Holdings hooks ──────────────────────────────────────

export function useHoldings() {
  return useFetch('/holdings', { refreshInterval: 30000 })
}

export function useTradeHistory(limit = 50) {
  return useFetch(`/trades?limit=${limit}`)
}

export function useAllocation() {
  return useFetch('/holdings/allocation', { refreshInterval: 60000 })
}

export function usePerformance(period = '3mo') {
  return useFetch(`/holdings/performance?period=${period}`)
}

export function useBenchmark(period = '3mo', benchmark = 'SPY') {
  return useFetch(`/holdings/benchmark?period=${period}&benchmark=${benchmark}`)
}

export function useMovers() {
  return useFetch('/holdings/movers', { refreshInterval: 30000 })
}

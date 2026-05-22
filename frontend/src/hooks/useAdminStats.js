import { useState, useEffect, useCallback } from 'react'
import { getHealth, getStats, getCorpusHealth } from '../api/admin'

export function useAdminStats(refreshInterval = 30000) {
  const [health, setHealth] = useState(null)
  const [stats, setStats] = useState(null)
  const [corpusHealth, setCorpusHealth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const [h, s, c] = await Promise.all([
        getHealth(),
        getStats(),
        getCorpusHealth()
      ])
      setHealth(h)
      setStats(s)
      setCorpusHealth(c)
      setLastUpdated(new Date())
    } catch (err) {
      console.error('Failed to fetch admin stats:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, refreshInterval)
    return () => clearInterval(interval)
  }, [refresh, refreshInterval])

  return { health, stats, corpusHealth, loading, lastUpdated, refresh }
}

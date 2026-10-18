import { useEffect, useState, useCallback } from 'react'
import { api, ApiError } from '../services/api'
import type { MapLayers, StudyArea } from '../types'

export function useMapLayers(targetArea?: StudyArea | null) {
  const [layers, setLayers] = useState<MapLayers | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchLayers = useCallback(async (area?: StudyArea | null) => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.mapLayers(area || targetArea)
      setLayers(data)
      return data
    } catch (e: any) {
      const msg = e instanceof ApiError ? e.message : 'Failed to load map layers.'
      setError(msg)
      return null
    } finally {
      setLoading(false)
    }
  }, [targetArea])

  useEffect(() => {
    fetchLayers(targetArea)
  }, [fetchLayers, targetArea])

  useEffect(() => {
    const handleAreaChange = (e: any) => {
      if (e.detail) {
        fetchLayers(e.detail)
      } else {
        fetchLayers()
      }
    }
    window.addEventListener('study-area-changed', handleAreaChange)
    return () => window.removeEventListener('study-area-changed', handleAreaChange)
  }, [fetchLayers])

  return { layers, loading, error, refetch: fetchLayers }
}

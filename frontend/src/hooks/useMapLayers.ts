import { useEffect, useState } from 'react'
import { api, ApiError } from '../services/api'
import type { MapLayers } from '../types'

export function useMapLayers() {
  const [layers, setLayers] = useState<MapLayers | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.mapLayers()
      .then(setLayers)
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Failed to load map layers.'))
      .finally(() => setLoading(false))
  }, [])

  return { layers, loading, error }
}

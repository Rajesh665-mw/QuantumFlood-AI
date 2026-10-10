import { useState, useEffect } from 'react'
import { api } from '../services/api'
import type { StudyArea, LocationSearchResult } from '../types'

interface LocationSelectorProps {
  currentArea: StudyArea | null
  onAreaChanged: (newArea: StudyArea) => void
}

const PRESETS = [
  { name: 'Vijayawada Corridor (Default)', query: 'Vijayawada, Andhra Pradesh, India', desc: 'Real local gauge data & Krishna river geometry (Project Benchmark)' },
  { name: 'Cologne / Rhine River', query: 'Cologne, Germany', desc: 'Dense European river basin corridor' },
  { name: 'Tokyo / Sumida River', query: 'Tokyo, Japan', desc: 'Metropolitan coastal delta network' },
  { name: 'London / Thames River', query: 'London, United Kingdom', desc: 'Tidal estuary and flood barrier corridor' },
  { name: 'New Orleans / Mississippi', query: 'New Orleans, Louisiana, USA', desc: 'Sub-sea-level delta and hurricane surge zone' },
]

export default function LocationSelector({ currentArea, onAreaChanged }: LocationSelectorProps) {
  const [query, setQuery] = useState('')
  const [suggestions, setSuggestions] = useState<LocationSearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [searching, setSearching] = useState(false)
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' | 'info' } | null>(null)
  const [manualMode, setManualMode] = useState(false)
  const [manualLat, setManualLat] = useState('')
  const [manualLon, setManualLon] = useState('')
  const [halfSizeDeg, setHalfSizeDeg] = useState(0.06)

  // Live autocomplete search with debounce
  useEffect(() => {
    if (!query || query.trim().length < 3) {
      setSuggestions([])
      return
    }

    const timer = setTimeout(async () => {
      setSearching(true)
      try {
        const res = await api.searchLocations(query.trim(), 4)
        setSuggestions(res.results || [])
      } catch {
        setSuggestions([])
      } finally {
        setSearching(false)
      }
    }, 450)

    return () => clearTimeout(timer)
  }, [query])

  const handleSelectLocation = async (locationQuery: string) => {
    setLoading(true)
    setMessage(null)
    setSuggestions([])
    try {
      const res = await api.selectArea({
        location_query: locationQuery,
        half_size_deg: halfSizeDeg,
      })
      if (res.status === 'OK' && res.study_area) {
        onAreaChanged(res.study_area)
        window.dispatchEvent(new CustomEvent('study-area-changed', { detail: res.study_area }))
        setMessage({
          text: `Active study area successfully configured: ${res.location_name}. Downstream quantum & classical modules updated.`,
          type: 'success',
        })
        setQuery('')
      } else {
        setMessage({ text: 'Could not resolve location. Please try a different query.', type: 'error' })
      }
    } catch (err: any) {
      setMessage({ text: err?.message || 'Error configuring study area.', type: 'error' })
    } finally {
      setLoading(false)
    }
  }

  const handleSelectCoords = async (lat: number, lon: number) => {
    setLoading(true)
    setMessage(null)
    setSuggestions([])
    try {
      const res = await api.selectArea({
        latitude: lat,
        longitude: lon,
        half_size_deg: halfSizeDeg,
      })
      if (res.status === 'OK' && res.study_area) {
        onAreaChanged(res.study_area)
        window.dispatchEvent(new CustomEvent('study-area-changed', { detail: res.study_area }))
        setMessage({
          text: `Active study area configured at coordinates (${lat.toFixed(4)}, ${lon.toFixed(4)}).`,
          type: 'success',
        })
        setManualLat('')
        setManualLon('')
      }
    } catch (err: any) {
      setMessage({ text: err?.message || 'Failed to select coordinate area.', type: 'error' })
    } finally {
      setLoading(false)
    }
  }

  const handleResetToDefault = async () => {
    setLoading(true)
    setMessage(null)
    try {
      const res = await api.resetArea()
      if (res.status === 'OK') {
        onAreaChanged(res.study_area)
        window.dispatchEvent(new CustomEvent('study-area-changed', { detail: res.study_area }))
        setMessage({
          text: 'Reverted to default Vijayawada–Krishna River Corridor benchmark.',
          type: 'info',
        })
      }
    } catch (err: any) {
      setMessage({ text: err?.message || 'Failed to reset study area.', type: 'error' })
    } finally {
      setLoading(false)
    }
  }

  const isDefault = !currentArea || currentArea.name.includes('Vijayawada')

  return (
    <div className="panel p-6 border border-base-600/80 bg-base-900/90 rounded-lg shadow-xl">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-base-700">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-signal-teal shadow-[0_0_8px_rgba(45,212,191,0.6)]" />
            <h3 className="font-display text-lg text-ink-100 font-semibold tracking-tight">
              Study Area &amp; Geographic Domain
            </h3>
            {isDefault ? (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                BENCHMARK CORRIDOR
              </span>
            ) : (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
                CUSTOM DYNAMIC AREA
              </span>
            )}
          </div>
          <p className="text-xs text-ink-400 mt-1">
            Configure any global river corridor or coastal flood zone. The mathematical pipeline, QUBO formulation, QAOA quantum circuits, and risk attenuation automatically adapt to the chosen domain.
          </p>
        </div>

        <button
          type="button"
          onClick={handleResetToDefault}
          disabled={loading || isDefault}
          className={`shrink-0 text-xs font-mono px-3.5 py-2 rounded transition-all flex items-center gap-1.5 ${
            isDefault
              ? 'opacity-40 cursor-not-allowed border border-base-700 text-ink-500'
              : 'border border-signal-teal/40 bg-signal-teal/10 text-signal-teal hover:bg-signal-teal/20 shadow-sm'
          }`}
        >
          <span>↺</span> Revert to Vijayawada Benchmark
        </button>
      </div>

      {/* Location Search Bar */}
      <div className="mt-5 space-y-4">
        <div className="relative">
          <label className="block text-xs font-mono uppercase tracking-wider text-ink-400 mb-1.5">
            Search Global Location or River Basin
          </label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Type any city, river, or region (e.g., Tokyo, Cologne, London, Houston)..."
                disabled={loading}
                className="w-full bg-base-950 border border-base-600 rounded px-3.5 py-2.5 text-sm text-ink-100 placeholder-ink-600 focus:outline-none focus:border-signal-teal transition-colors"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && query.trim()) {
                    handleSelectLocation(query.trim())
                  }
                }}
              />
              {searching && (
                <div className="absolute right-3 top-3 text-xs text-signal-teal animate-spin">
                  ⟳
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={() => query.trim() && handleSelectLocation(query.trim())}
              disabled={loading || !query.trim()}
              className="bg-signal-teal text-base-950 font-medium px-4 py-2.5 rounded text-xs hover:bg-signal-teal/90 disabled:opacity-40 transition-colors shadow"
            >
              {loading ? 'Configuring...' : 'Set Active Area'}
            </button>
          </div>

          {/* Autocomplete Dropdown */}
          {suggestions.length > 0 && (
            <div className="absolute z-30 left-0 right-0 mt-1 bg-base-950 border border-base-600 rounded shadow-2xl overflow-hidden divide-y divide-base-800">
              {suggestions.map((s, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSelectCoords(s.latitude, s.longitude)}
                  className="w-full text-left px-3.5 py-2.5 text-xs hover:bg-base-800 transition-colors flex items-center justify-between group"
                >
                  <div className="min-w-0 pr-2">
                    <span className="font-semibold text-ink-100 group-hover:text-signal-teal transition-colors">
                      {s.city || s.display_name.split(',')[0]}
                    </span>
                    <span className="text-ink-500 truncate block text-[11px]">
                      {s.display_name}
                    </span>
                  </div>
                  <span className="font-mono text-[10px] text-ink-600 shrink-0">
                    {s.latitude.toFixed(2)}°, {s.longitude.toFixed(2)}°
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Quick Presets */}
        <div>
          <span className="text-[11px] font-mono text-ink-500 uppercase tracking-wider block mb-2">
            Standard Reference Scenarios &amp; Benchmarks
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {PRESETS.map((p) => (
              <button
                key={p.name}
                type="button"
                onClick={() => handleSelectLocation(p.query)}
                disabled={loading}
                className="text-left p-2.5 rounded bg-base-950/70 border border-base-750 hover:border-signal-teal/40 hover:bg-base-800/80 transition-all group"
              >
                <div className="font-medium text-xs text-ink-200 group-hover:text-signal-teal transition-colors">
                  {p.name}
                </div>
                <div className="text-[11px] text-ink-500 truncate mt-0.5">
                  {p.desc}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Manual Coordinates Toggle */}
        <div className="pt-2">
          <button
            type="button"
            onClick={() => setManualMode(!manualMode)}
            className="text-xs font-mono text-signal-teal hover:underline flex items-center gap-1"
          >
            <span>{manualMode ? '▾ Hide' : '▸ Custom'}</span> Direct Lat/Lon &amp; Span Calibration
          </button>

          {manualMode && (
            <div className="mt-3 p-3.5 rounded bg-base-950 border border-base-700 grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
              <div>
                <label className="block text-[11px] font-mono text-ink-400 mb-1">Center Latitude</label>
                <input
                  type="number"
                  step="0.0001"
                  value={manualLat}
                  onChange={(e) => setManualLat(e.target.value)}
                  placeholder="e.g. 16.5061"
                  className="w-full bg-base-900 border border-base-600 rounded px-2.5 py-1.5 text-xs text-ink-100"
                />
              </div>
              <div>
                <label className="block text-[11px] font-mono text-ink-400 mb-1">Center Longitude</label>
                <input
                  type="number"
                  step="0.0001"
                  value={manualLon}
                  onChange={(e) => setManualLon(e.target.value)}
                  placeholder="e.g. 80.6050"
                  className="w-full bg-base-900 border border-base-600 rounded px-2.5 py-1.5 text-xs text-ink-100"
                />
              </div>
              <div>
                <label className="block text-[11px] font-mono text-ink-400 mb-1">
                  Corridor Radius ({((halfSizeDeg * 111)).toFixed(1)} km)
                </label>
                <input
                  type="range"
                  min="0.02"
                  max="0.12"
                  step="0.01"
                  value={halfSizeDeg}
                  onChange={(e) => setHalfSizeDeg(parseFloat(e.target.value))}
                  className="w-full accent-signal-teal"
                />
              </div>
              <div>
                <button
                  type="button"
                  onClick={() => {
                    const lat = parseFloat(manualLat)
                    const lon = parseFloat(manualLon)
                    if (!isNaN(lat) && !isNaN(lon)) {
                      handleSelectCoords(lat, lon)
                    }
                  }}
                  disabled={loading || !manualLat || !manualLon}
                  className="w-full bg-base-800 border border-base-600 hover:border-signal-teal text-ink-100 px-3 py-1.5 rounded text-xs transition-colors disabled:opacity-40"
                >
                  Apply Coordinates
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Feedback Alert */}
        {message && (
          <div
            className={`p-3 rounded text-xs font-mono border flex items-center justify-between ${
              message.type === 'success'
                ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
                : message.type === 'error'
                ? 'bg-rose-950/40 border-rose-500/40 text-rose-300'
                : 'bg-cyan-950/40 border-cyan-500/40 text-cyan-300'
            }`}
          >
            <span>{message.text}</span>
            <button
              type="button"
              onClick={() => setMessage(null)}
              className="text-ink-400 hover:text-ink-100 ml-2"
            >
              ✕
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

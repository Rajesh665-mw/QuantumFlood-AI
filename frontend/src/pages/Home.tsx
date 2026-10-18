import { Link, useNavigate } from 'react-router-dom'
import { useEffect, useState, useRef } from 'react'
import { api, ApiError } from '../services/api'
import type { StudyArea, LocationSearchResult } from '../types'

type FlowStep = 'search' | 'configuring' | 'sensor-setup'

const PRESETS = [
  { name: 'Vijayawada, India', query: 'Vijayawada, Andhra Pradesh, India', desc: 'Krishna River corridor — project benchmark with real gauge data' },
  { name: 'Cologne, Germany', query: 'Cologne, Germany', desc: 'Rhine river basin — dense European flood corridor' },
  { name: 'Tokyo, Japan', query: 'Tokyo, Japan', desc: 'Sumida River delta — metropolitan coastal network' },
  { name: 'London, UK', query: 'London, United Kingdom', desc: 'Thames estuary — tidal flood barrier corridor' },
  { name: 'New Orleans, USA', query: 'New Orleans, Louisiana, USA', desc: 'Mississippi delta — hurricane surge zone' },
]

const SECTIONS = [
  {
    title: 'Historical Flood Intelligence',
    desc: 'Verified historical inundation events, river gauge hydrographs, and seasonal rainfall timelines.',
    link: '/historical-intelligence',
    color: 'text-signal-cyan',
  },
  {
    title: 'Safe Shelters & Operator Dispatch',
    desc: 'Multi-criteria candidate shelter evaluation with on-ground resource request logging.',
    link: '/shelters',
    color: 'text-emerald-400',
  },
  {
    title: 'Resource Planning & Fulfillment',
    desc: 'Inventory-constrained allocation plans with shortage identification and audit trails.',
    link: '/resource-planning',
    color: 'text-amber-400',
  },
]

export default function Home() {
  const navigate = useNavigate()
  const searchRef = useRef<HTMLInputElement>(null)

  // Flow state
  const [step, setStep] = useState<FlowStep>('search')
  const [studyArea, setStudyArea] = useState<StudyArea | null>(null)

  // Search state
  const [query, setQuery] = useState('')
  const [suggestions, setSuggestions] = useState<LocationSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Sensor config state
  const [numSensors, setNumSensors] = useState(8)
  const [coverageRadius, setCoverageRadius] = useState(2.5)
  const [candidateCount, setCandidateCount] = useState<number | null>(null)
  const [loadingCandidates, setLoadingCandidates] = useState(false)

  // Load existing area on mount
  useEffect(() => {
    api.currentArea()
      .then((r) => { if (r.study_area) setStudyArea(r.study_area) })
      .catch(() => {})
  }, [])

  // Live autocomplete
  useEffect(() => {
    if (!query || query.trim().length < 3) {
      setSuggestions([])
      return
    }
    const timer = setTimeout(async () => {
      setSearching(true)
      try {
        const res = await api.searchLocations(query.trim(), 5)
        setSuggestions(res.results || [])
      } catch { setSuggestions([]) }
      finally { setSearching(false) }
    }, 400)
    return () => clearTimeout(timer)
  }, [query])

  const handleSelectLocation = async (locationQuery: string) => {
    setLoading(true)
    setError(null)
    setSuggestions([])
    setStep('configuring')
    try {
      const res = await api.selectArea({ location_query: locationQuery, half_size_deg: 0.06 })
      if (res.status === 'OK' && res.study_area) {
        setStudyArea(res.study_area)
        window.dispatchEvent(new CustomEvent('study-area-changed', { detail: res.study_area }))
        setQuery('')
        // Fetch candidate count for the selected area
        setLoadingCandidates(true)
        try {
          const cands = await api.candidates(res.study_area)
          setCandidateCount(cands.candidates?.length ?? 0)
        } catch { setCandidateCount(null) }
        finally { setLoadingCandidates(false) }
        setStep('sensor-setup')
      } else {
        setError('Could not resolve that location. Please try a different search.')
        setStep('search')
      }
    } catch (err: any) {
      setError(err instanceof ApiError ? err.message : 'Error configuring study area.')
      setStep('search')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectCoords = async (lat: number, lon: number) => {
    setLoading(true)
    setError(null)
    setSuggestions([])
    setStep('configuring')
    try {
      const res = await api.selectArea({ latitude: lat, longitude: lon, half_size_deg: 0.06 })
      if (res.status === 'OK' && res.study_area) {
        setStudyArea(res.study_area)
        window.dispatchEvent(new CustomEvent('study-area-changed', { detail: res.study_area }))
        setQuery('')
        setLoadingCandidates(true)
        try {
          const cands = await api.candidates(res.study_area)
          setCandidateCount(cands.candidates?.length ?? 0)
        } catch { setCandidateCount(null) }
        finally { setLoadingCandidates(false) }
        setStep('sensor-setup')
      } else {
        setError('Could not resolve those coordinates.')
        setStep('search')
      }
    } catch (err: any) {
      setError(err instanceof ApiError ? err.message : 'Error configuring study area.')
      setStep('search')
    } finally {
      setLoading(false)
    }
  }

  const handleLaunchOptimization = () => {
    navigate('/sensor-placement', {
      state: {
        fromSearch: true,
        targetArea: studyArea,
        autoRun: true,
        numSensors,
        coverageRadius,
        timestamp: Date.now(),
      },
    })
  }

  const handleBackToSearch = () => {
    setStep('search')
    setError(null)
    setCandidateCount(null)
  }

  const maxSensors = candidateCount != null ? Math.min(candidateCount, 24) : 24
  const sensorCountValid = numSensors >= 1 && numSensors <= maxSensors

  return (
    <div className="flex flex-col gap-10 page-enter">
      {/* ── Hero Section ── */}
      <section className="relative overflow-hidden rounded-xl border border-base-600/70 bg-gradient-to-br from-base-900 via-base-900/90 to-base-950 p-6 md:p-12 shadow-2xl">
        {/* Decorative background elements */}
        <div className="absolute top-0 right-0 w-96 h-96 bg-signal-teal/5 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-72 h-72 bg-signal-cyan/3 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute top-1/2 right-1/4 w-40 h-40 bg-purple-500/3 rounded-full blur-2xl pointer-events-none" />

        <div className="relative z-10 max-w-4xl">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-signal-teal/10 border border-signal-teal/30 text-signal-teal text-xs font-mono font-medium tracking-wide">
            <span className="w-2 h-2 rounded-full bg-signal-teal animate-ping" />
            Flood Intelligence &amp; Sensor Optimization
          </div>

          <h1 className="font-display text-3xl sm:text-5xl md:text-6xl font-bold text-ink-100 mt-4 leading-tight">
            QuantumFlood AI
          </h1>
          <h2 className="text-lg sm:text-2xl md:text-3xl font-medium text-signal-teal mt-2">
            Smarter Flood Preparedness. Safer Communities.
          </h2>

          <p className="text-ink-300 text-sm sm:text-base mt-4 max-w-3xl leading-relaxed">
            Every year, flooding displaces millions of people and causes billions in damages worldwide.
            QuantumFlood AI helps you plan smarter: select any river corridor or coastal zone, and the
            platform will identify optimal sensor placements to maximize early-warning coverage — comparing
            classical optimization against quantum-approximate methods in real time.
          </p>

          <p className="text-ink-400 text-xs sm:text-sm mt-3 max-w-3xl leading-relaxed">
            Start by searching for a geographic area below. The platform will generate candidate sensor
            locations, let you configure the sensor budget, and then run the actual optimization algorithms
            on real terrain data.
          </p>
        </div>
      </section>

      {/* ── STEP 1: Area Search (Primary CTA) ── */}
      {step === 'search' && (
        <section className="relative">
          {/* Subtle spotlight glow around the search panel */}
          <div className="absolute -inset-2 bg-signal-teal/3 rounded-2xl blur-xl pointer-events-none animate-pulse-slow" />

          <div className="relative panel p-6 sm:p-8 border-signal-teal/30 bg-base-900/95 rounded-xl shadow-[0_0_40px_rgba(45,212,191,0.06)]">
            <div className="pb-5 border-b border-base-700/60">
              <div className="flex items-center gap-2">
                <svg className="w-5 h-5 text-signal-teal" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <h2 className="font-display text-xl sm:text-2xl text-ink-100 font-semibold">
                  Where should we optimize?
                </h2>
              </div>
              <p className="text-ink-400 text-xs sm:text-sm mt-1.5 max-w-2xl">
                Search for any city, river basin, or coastal region. The platform will automatically
                identify terrain features, generate sensor candidate locations, and prepare the study area for analysis.
              </p>
            </div>

            {/* Search Bar */}
            <div className="mt-5 relative">
              <label className="block text-xs font-mono uppercase tracking-wider text-ink-400 mb-2">
                Search a flood-prone area to begin
              </label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <input
                    ref={searchRef}
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Type any city, river, or region (e.g., Tokyo, Cologne, Houston)…"
                    disabled={loading}
                    className="w-full bg-base-950 border-2 border-base-600 focus:border-signal-teal rounded-lg px-4 py-3 text-sm text-ink-100 placeholder-ink-600 focus:outline-none transition-colors shadow-inner"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && query.trim()) handleSelectLocation(query.trim())
                    }}
                    autoFocus
                  />
                  {searching && (
                    <div className="absolute right-3 top-3.5">
                      <span className="w-4 h-4 border-2 border-base-600 border-t-signal-teal rounded-full animate-spin inline-block" />
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => query.trim() && handleSelectLocation(query.trim())}
                  disabled={loading || !query.trim()}
                  className="bg-signal-teal text-base-950 font-semibold px-6 py-3 rounded-lg hover:bg-signal-teal/90 hover:shadow-[0_0_20px_rgba(45,212,191,.4)] disabled:opacity-40 transition-all duration-200 text-sm shadow-lg"
                >
                  {loading ? 'Resolving…' : 'Analyze Area'}
                </button>
              </div>

              {/* Autocomplete dropdown */}
              {suggestions.length > 0 && (
                <div className="absolute z-30 left-0 right-0 mt-1 bg-base-950 border border-base-600 rounded-lg shadow-2xl overflow-hidden divide-y divide-base-800 scale-in">
                  {suggestions.map((s, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => handleSelectCoords(s.latitude, s.longitude)}
                      className="w-full text-left px-4 py-3 text-xs hover:bg-base-800 transition-colors flex items-center justify-between group"
                    >
                      <div className="min-w-0 pr-2">
                        <span className="font-semibold text-ink-100 group-hover:text-signal-teal transition-colors">
                          {s.city || s.display_name.split(',')[0]}
                        </span>
                        <span className="text-ink-500 truncate block text-[11px]">{s.display_name}</span>
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
            <div className="mt-5">
              <span className="text-[11px] font-mono text-ink-500 uppercase tracking-wider block mb-2">
                Or choose a reference basin
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-5 gap-2">
                {PRESETS.map((p) => (
                  <button
                    key={p.name}
                    type="button"
                    onClick={() => handleSelectLocation(p.query)}
                    disabled={loading}
                    className="text-left p-3 rounded-lg bg-base-950/70 border border-base-750 hover:border-signal-teal/40 hover:bg-base-800/80 transition-all duration-200 group"
                  >
                    <div className="font-medium text-xs text-ink-200 group-hover:text-signal-teal transition-colors">
                      {p.name}
                    </div>
                    <div className="text-[10px] text-ink-600 mt-0.5 line-clamp-2">{p.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="mt-4 p-3 rounded-lg bg-rose-950/40 border border-rose-500/40 text-rose-300 text-xs flex items-center justify-between">
                <span>{error}</span>
                <button onClick={() => setError(null)} className="text-ink-400 hover:text-ink-100 ml-2">✕</button>
              </div>
            )}

            {/* Active area indicator */}
            {studyArea && (
              <div className="mt-4 flex items-center gap-2 px-3 py-2 rounded-lg bg-base-800/60 border border-base-700 text-xs text-ink-400">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <span>Currently loaded:</span>
                <strong className="text-ink-200">{studyArea.name}</strong>
                <span className="text-ink-600 font-mono">
                  ({studyArea.center.lat.toFixed(3)}°, {studyArea.center.lon.toFixed(3)}°)
                </span>
                <button
                  onClick={() => {
                    setStep('sensor-setup')
                    // Load candidates for this area
                    setLoadingCandidates(true)
                    api.candidates(studyArea)
                      .then((c) => setCandidateCount(c.candidates?.length ?? 0))
                      .catch(() => setCandidateCount(null))
                      .finally(() => setLoadingCandidates(false))
                  }}
                  className="ml-auto text-signal-teal hover:underline font-medium"
                >
                  Configure sensors →
                </button>
              </div>
            )}
          </div>
        </section>
      )}

      {/* ── STEP 1.5: Configuring (loading) ── */}
      {step === 'configuring' && (
        <section className="panel p-8 sm:p-12 flex flex-col items-center justify-center gap-4 border-signal-teal/20">
          <div className="w-10 h-10 border-3 border-base-600 border-t-signal-teal rounded-full animate-spin" />
          <div className="text-center">
            <h3 className="font-display text-lg text-ink-100 font-semibold">Resolving geographic area…</h3>
            <p className="text-ink-400 text-xs mt-1">
              Geocoding location, generating terrain contours, identifying candidate sensor positions…
            </p>
          </div>
        </section>
      )}

      {/* ── STEP 2: Sensor Configuration ── */}
      {step === 'sensor-setup' && studyArea && (
        <section className="panel p-6 sm:p-8 border-signal-teal/30 bg-base-900/95 rounded-xl shadow-[0_0_30px_rgba(45,212,191,0.05)] fade-in">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-5 border-b border-base-700/60">
            <div>
              <div className="flex items-center gap-2">
                <svg className="w-5 h-5 text-signal-teal" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                </svg>
                <h2 className="font-display text-xl sm:text-2xl text-ink-100 font-semibold">
                  Configure Sensor Placement
                </h2>
              </div>
              <p className="text-ink-400 text-xs sm:text-sm mt-1.5 max-w-2xl">
                Set how many flood-warning sensors to deploy. The optimizer will select positions from the
                generated candidate set to maximize modeled coverage of flood-risk zones, subject to the
                sensor budget constraint.
              </p>
            </div>
            <button
              onClick={handleBackToSearch}
              className="shrink-0 text-xs font-mono text-ink-400 hover:text-signal-teal transition-colors flex items-center gap-1"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Change Area
            </button>
          </div>

          {/* Selected area badge */}
          <div className="mt-4 inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-base-800 border border-emerald-500/30 text-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-ink-300">Study Area:</span>
            <strong className="text-ink-100 font-semibold">{studyArea.name}</strong>
            {studyArea.river && (
              <span className="text-ink-500 font-mono">({studyArea.river})</span>
            )}
            <span className="text-ink-600 font-mono text-[10px]">
              {studyArea.center.lat.toFixed(4)}°N, {studyArea.center.lon.toFixed(4)}°E
            </span>
          </div>

          {/* Candidate info */}
          <div className="mt-4 p-3 rounded-lg bg-base-950/80 border border-base-700 text-xs text-ink-400">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-signal-cyan shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {loadingCandidates ? (
                <span>Loading candidate positions for this area…</span>
              ) : candidateCount != null ? (
                <span>
                  <strong className="text-ink-200">{candidateCount}</strong> candidate sensor positions
                  were generated from the terrain analysis of {studyArea.name}.
                  You can deploy up to <strong className="text-ink-200">{maxSensors}</strong> sensors.
                </span>
              ) : (
                <span>Candidate positions will be generated automatically. Choose your sensor count below.</span>
              )}
            </div>
          </div>

          {/* Sensor count + coverage radius controls */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
            {/* Sensor Count */}
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-ink-200 flex items-center justify-between">
                <span>Number of Sensors</span>
                <span className="font-mono text-lg text-signal-teal font-bold">{numSensors}</span>
              </label>
              <input
                type="range"
                min={1}
                max={maxSensors}
                value={numSensors}
                onChange={(e) => setNumSensors(Number(e.target.value))}
                className="accent-signal-teal cursor-pointer h-2"
              />
              <div className="flex justify-between text-[10px] font-mono text-ink-500">
                <span>1 sensor</span>
                <span>{maxSensors} sensors</span>
              </div>
              {candidateCount != null && numSensors > candidateCount && (
                <p className="text-xs text-amber-400 mt-1">
                  ⚠ Sensor count exceeds available candidates ({candidateCount}). The optimizer will place as many as possible.
                </p>
              )}
            </div>

            {/* Coverage Radius */}
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-ink-200 flex items-center justify-between">
                <span>Coverage Radius</span>
                <span className="font-mono text-lg text-signal-teal font-bold">{coverageRadius} km</span>
              </label>
              <input
                type="range"
                min={0.5}
                max={8.0}
                step={0.1}
                value={coverageRadius}
                onChange={(e) => setCoverageRadius(Number(e.target.value))}
                className="accent-signal-teal cursor-pointer h-2"
              />
              <div className="flex justify-between text-[10px] font-mono text-ink-500">
                <span>0.5 km</span>
                <span>8.0 km</span>
              </div>
            </div>
          </div>

          {/* Explanation */}
          <div className="mt-5 p-3 rounded-lg bg-base-950/60 border border-base-700/60 text-xs text-ink-400 leading-relaxed">
            <strong className="text-ink-200">How the optimizer works:</strong> The placement algorithm evaluates
            all {candidateCount ?? 'generated'} candidate positions and selects {numSensors} to maximize
            risk-weighted zone coverage within a {coverageRadius} km sensing radius. It uses a greedy
            heuristic that achieves a guaranteed (1-1/e) approximation ratio. You can also compare against
            a QAOA quantum circuit simulation on the map page.
          </div>

          {/* Launch button */}
          <div className="mt-6 flex flex-col sm:flex-row items-center gap-4">
            <button
              onClick={handleLaunchOptimization}
              disabled={!sensorCountValid}
              className="w-full sm:w-auto bg-signal-teal text-base-950 font-bold px-8 py-3.5 rounded-lg hover:bg-signal-teal/90 hover:shadow-[0_0_30px_rgba(45,212,191,.4)] disabled:opacity-40 transition-all duration-200 text-sm shadow-lg flex items-center justify-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Run Optimization &amp; Open Map
            </button>
            <span className="text-xs text-ink-500">
              Places {numSensors} sensors with {coverageRadius} km coverage radius on {studyArea.name}
            </span>
          </div>
        </section>
      )}

      {/* ── Additional Platform Modules ── */}
      <section className="flex flex-col gap-4">
        <div>
          <span className="eyebrow">Explore More Modules</span>
          <h2 className="font-display text-xl sm:text-2xl text-ink-100 font-semibold mt-1">
            End-to-End Disaster Preparedness
          </h2>
          <p className="text-ink-400 text-xs sm:text-sm mt-0.5">
            Beyond sensor placement, explore historical intelligence, shelter assessment, and resource logistics.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {SECTIONS.map((s) => (
            <Link
              key={s.title}
              to={s.link}
              className="panel p-5 flex flex-col gap-3 hover:border-signal-teal/30 transition-all duration-200 group"
            >
              <h3 className={`font-display font-semibold text-base ${s.color} group-hover:brightness-125 transition-all`}>
                {s.title}
              </h3>
              <p className="text-ink-400 text-xs leading-relaxed flex-1">{s.desc}</p>
              <span className="text-[11px] text-signal-teal font-medium flex items-center gap-1 mt-auto">
                Explore
                <svg className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                </svg>
              </span>
            </Link>
          ))}
        </div>
      </section>

      {/* ── Transparency Note ── */}
      <section className="panel p-5 border-signal-teal/20 bg-signal-teal/3 rounded-xl">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded bg-signal-teal/15 text-signal-teal shrink-0 mt-0.5">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <h4 className="font-display text-sm font-semibold text-ink-100">
              Scientific Integrity Statement
            </h4>
            <p className="text-xs text-ink-300 mt-1 leading-relaxed">
              QuantumFlood AI evaluates sensor placement on real and dynamically generated river basins using both
              greedy classical heuristics and quantum statevector simulation (QAOA depths p=1 and p=2). All quantum
              metrics reflect rigorous local statevector linear algebra — no quantum advantage over classical
              computing is claimed. Shelter evaluations represent candidate multi-criteria feasibility assessments,
              not certified physical safety inspections.
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}

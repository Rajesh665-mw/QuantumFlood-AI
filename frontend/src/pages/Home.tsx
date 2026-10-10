import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api } from '../services/api'
import type { StudyArea } from '../types'
import LocationSelector from '../components/LocationSelector'

const PIPELINE = [
  'Hydro-meteorological data', 'Data validation & cleaning', 'Feature engineering',
  'Classical ML forecasting', 'Flood risk assessment', 'Geographic risk zones',
  'Candidate sensor sites', 'Coverage optimisation', 'Connectivity analysis', 'Response recommendations',
]

const CAPABILITIES = [
  { title: 'Classical ML Forecasting', body: 'Chronologically-split regression models (Linear, Random Forest, Gradient Boosting) forecast water level from rainfall and inflow history.' },
  { title: 'Rule-Based Risk Assessment', body: 'Documented thresholds convert forecasts into LOW / MODERATE / HIGH / CRITICAL zone classifications with a traceable explanation.' },
  { title: 'Greedy Max-Coverage Optimisation', body: 'A provably near-optimal ((1-1/e)-approximate) greedy algorithm selects sensor sites that maximise weighted flood-risk coverage under a fixed budget.' },
  { title: 'Connectivity Analysis', body: 'Great-circle distance calculations determine which sensors reach a communication node, and flag any that don’t.' },
]

export default function Home() {
  const [studyArea, setStudyArea] = useState<StudyArea | null>(null)

  useEffect(() => {
    api.currentArea()
      .then((r) => setStudyArea(r.study_area))
      .catch(() => {
        api.regions().then((r) => setStudyArea(r.regions[0] ?? null)).catch(() => setStudyArea(null))
      })
  }, [])

  return (
    <div className="flex flex-col gap-12">
      <section className="relative overflow-hidden rounded panel contour-field px-6 py-14 md:px-14 md:py-20">
        <div className="relative z-10 max-w-3xl">
          <span className="eyebrow">UC-067 · Quantum Computing / Quantum AI-ML Track</span>
          <h1 className="font-display text-4xl md:text-5xl font-semibold text-ink-100 mt-4 leading-tight">
            QuantumFlood AI
          </h1>
          <p className="text-ink-300 text-lg mt-3 max-w-xl">
            Flood forecasting &amp; smart sensor optimisation for disaster response — quantum-enhanced
            decision-support platform.
          </p>
          <p className="text-ink-500 text-sm mt-5 max-w-2xl leading-relaxed">
            A quantum-enhanced decision-support platform combining classical forecasting baselines
            with an experimental 4-qubit Variational Quantum Regressor (VQR), rule-based spatial risk
            mapping, and QAOA-based sensor placement optimisation evaluated against greedy classical heuristics.
          </p>
          <div className="flex flex-wrap gap-3 mt-8">
            <Link
              to="/command-center"
              className="bg-signal-teal text-base-950 font-medium px-5 py-2.5 rounded hover:bg-signal-teal/90 transition-colors"
            >
              Open Command Center
            </Link>
            <Link
              to="/data-analytics"
              className="border border-base-600 text-ink-100 px-5 py-2.5 rounded hover:bg-base-700 transition-colors"
            >
              View System Architecture
            </Link>
          </div>
        </div>
      </section>

      {/* Global Location & Study Area Selector */}
      <section>
        <LocationSelector
          currentArea={studyArea}
          onAreaChanged={(newArea) => setStudyArea(newArea)}
        />
      </section>

      <section>
        <span className="eyebrow">Active Study Area Status</span>
        <h2 className="font-display text-2xl text-ink-100 mt-2">{studyArea?.name ?? 'Vijayawada – Krishna River Corridor'}</h2>
        <p className="text-ink-500 text-sm mt-2 max-w-2xl">
          {studyArea?.scope_note ??
            'Study area: the Vijayawada–Krishna River corridor only — a single corridor within the broader Krishna-Godavari basin, not full-basin coverage.'}
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-6">
          {[
            { label: 'River / Waterway', value: studyArea?.river ?? 'Krishna' },
            { label: 'Reference gauge', value: studyArea?.reference_gauge ?? 'Prakasam Barrage' },
            { label: 'State / Region', value: studyArea?.state || studyArea?.region || 'Andhra Pradesh' },
            { label: 'Risk zones modelled', value: '36' },
          ].map((f) => (
            <div key={f.label} className="panel p-4">
              <span className="data-label">{f.label}</span>
              <div className="text-ink-100 font-display mt-1">{f.value}</div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <span className="eyebrow">Core Capabilities</span>
        <div className="grid md:grid-cols-2 gap-4 mt-4">
          {CAPABILITIES.map((c) => (
            <div key={c.title} className="panel p-5">
              <h3 className="font-display text-ink-100 font-medium">{c.title}</h3>
              <p className="text-ink-500 text-sm mt-2 leading-relaxed">{c.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <span className="eyebrow">System Architecture</span>
        <h2 className="font-display text-2xl text-ink-100 mt-2 mb-6">Processing Pipeline</h2>
        <div className="panel p-6 overflow-x-auto">
          <div className="flex items-stretch gap-0 min-w-[900px]">
            {PIPELINE.map((stage, i) => (
              <div key={stage} className="flex items-stretch flex-1">
                <div className="flex flex-col justify-center px-3 py-3 flex-1">
                  <span className="data-label">{String(i + 1).padStart(2, '0')}</span>
                  <span className="text-ink-100 text-sm mt-1 leading-snug">{stage}</span>
                </div>
                {i < PIPELINE.length - 1 && (
                  <div className="w-px bg-base-600 shrink-0" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="panel p-6 border-signal-tealDim/40">
        <span className="eyebrow">Quantum Computing &amp; Optimization Modules</span>
        <p className="text-ink-300 text-sm mt-2 max-w-2xl leading-relaxed">
          QuantumFlood AI features locally simulated QAOA for sensor placement optimisation and an experimental
          4-qubit Variational Quantum Regressor (VQR) with data re-uploading for hydrological forecasting, benchmarked
          against classical models. All quantum algorithms execute via deterministic NumPy statevector simulation;
          no empirical quantum advantage or physical quantum hardware execution is claimed.
        </p>
      </section>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { api, ApiError } from '../services/api'
import type { DatasetSummary, ForecastResults, DataProvenance, RealFloodEvent, ExperimentRunRecord } from '../types'
import { LoadingState, ErrorState } from '../components/LoadingState'

const STATUS_STYLE: Record<string, string> = {
  REAL_HISTORICAL: 'text-risk-low border-risk-low/40 bg-risk-lowBg',
  SIMULATED_INPUT: 'text-risk-moderate border-risk-moderate/40 bg-risk-moderateBg',
  PARTIALLY_REAL: 'text-signal-teal border-signal-tealDim/50 bg-base-700',
  PROJECT_DEFINED: 'text-risk-moderate border-risk-moderate/40 bg-risk-moderateBg',
  MODELLED_SPATIAL: 'text-signal-teal border-signal-tealDim/50 bg-base-700',
}

const CATEGORY_LABELS: Record<string, string> = {
  rainfall_mm: 'Rainfall',
  water_level_m: 'Water Level',
  inflow_ktcmd: 'Discharge / Inflow',
  historical_flood_events: 'Historical Flood Events',
  river_geometry: 'River Geometry',
  study_area_boundary: 'Study Area Boundary',
  risk_zones: 'Risk Zones',
  safe_candidate_locations: 'Safe Candidate Locations',
  road_network: 'Corridor Road Network',
}

export default function DataAnalytics() {
  const [summary, setSummary] = useState<DatasetSummary | null>(null)
  const [forecast, setForecast] = useState<ForecastResults | null>(null)
  const [provenance, setProvenance] = useState<DataProvenance | null>(null)
  const [realEvents, setRealEvents] = useState<RealFloodEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [experimentRun, setExperimentRun] = useState<ExperimentRunRecord | null>(null)
  const [runningExperiments, setRunningExperiments] = useState(false)
  const [experimentError, setExperimentError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      api.datasetSummary(),
      api.forecastResults().catch(() => null),
      api.dataProvenance(),
      api.historicalEventsReal().then((r) => r.events).catch(() => []),
    ])
      .then(([s, f, p, events]) => { setSummary(s); setForecast(f); setProvenance(p); setRealEvents(events) })
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Failed to load analytics.'))
      .finally(() => setLoading(false))
  }, [])

  const runExperiments = async () => {
    setRunningExperiments(true)
    setExperimentError(null)
    try {
      const result = await api.runExperiments({ resolution: 'default' })
      setExperimentRun(result)
    } catch (e) {
      setExperimentError(e instanceof ApiError ? e.message : 'Run a risk generation first (Flood Forecasting page) before benchmarking.')
    } finally {
      setRunningExperiments(false)
    }
  }

  if (loading) return <LoadingState label="Compiling analytics…" />
  if (error || !summary) return <ErrorState message={error ?? 'No data available.'} />

  return (
    <div className="flex flex-col gap-8">
      <div>
        <span className="eyebrow">Module 1 / Data Provenance &amp; Methodology</span>
        <h1 className="font-display text-2xl text-ink-100 mt-1">Data &amp; Analytics</h1>
        <p className="text-ink-500 text-sm mt-2 max-w-2xl">
          Dataset quality, model performance, data provenance, and classical
          optimisation benchmarking.
        </p>
      </div>

      {/* Data Provenance - Step 15 */}
      {provenance && (
        <div className="panel p-5">
          <span className="data-label">Data Provenance — Real vs. Simulated</span>
          <div className="grid sm:grid-cols-2 gap-3 mt-4">
            {Object.entries(provenance.provenance).map(([key, entry]) => (
              <div key={key} className="bg-base-700 rounded p-3.5">
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <span className="text-ink-100 text-sm font-medium">{CATEGORY_LABELS[key] ?? key}</span>
                  <span className={`font-mono text-[10px] uppercase px-1.5 py-0.5 rounded border ${STATUS_STYLE[entry.status]}`}>
                    {entry.status.replace('_', ' ')}
                  </span>
                </div>
                <p className="text-ink-500 text-xs leading-relaxed">{entry.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="panel p-5">
        <span className="data-label">Dataset Summary — {summary.data_source_label}</span>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-3">
          <Metric label="Row Count" value={summary.row_count} />
          <Metric label="Date Range" value={`${summary.date_range.start} → ${summary.date_range.end}`} />
          <Metric label="Duplicate Rows" value={summary.duplicate_rows} />
          <Metric label="Columns" value={summary.columns.length} />
        </div>
      </div>

      <div className="panel p-5">
        <span className="data-label">Data Quality — Missing Values by Column</span>
        <div className="grid sm:grid-cols-3 md:grid-cols-5 gap-3 mt-3">
          {Object.entries(summary.missing_values).map(([col, count]) => (
            <div key={col} className="bg-base-700 rounded p-3">
              <div className="font-mono text-xs text-ink-500">{col}</div>
              <div className={`font-mono text-lg mt-1 ${count > 0 ? 'text-risk-moderate' : 'text-risk-low'}`}>{count}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="panel p-5">
        <span className="data-label">Numeric Feature Statistics</span>
        <div className="overflow-x-auto mt-3">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-ink-500 border-b border-base-600">
                <th className="py-2 pr-4 font-normal">Feature</th>
                <th className="py-2 pr-4 font-normal">Min</th>
                <th className="py-2 pr-4 font-normal">Max</th>
                <th className="py-2 pr-4 font-normal">Mean</th>
                <th className="py-2 pr-4 font-normal">Std Dev</th>
              </tr>
            </thead>
            <tbody className="font-mono text-ink-300">
              {Object.entries(summary.numeric_summary).map(([col, stats]) => (
                <tr key={col} className="border-b border-base-700">
                  <td className="py-2 pr-4">{col}</td>
                  <td className="py-2 pr-4">{stats.min}</td>
                  <td className="py-2 pr-4">{stats.max}</td>
                  <td className="py-2 pr-4">{stats.mean}</td>
                  <td className="py-2 pr-4">{stats.std}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {forecast && (
        <div className="panel p-5">
          <span className="data-label">Model Performance (last training run) — incl. persistence baseline</span>
          <div className="overflow-x-auto mt-3">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-ink-500 border-b border-base-600">
                  <th className="py-2 pr-4 font-normal">Model</th>
                  <th className="py-2 pr-4 font-normal">MAE</th>
                  <th className="py-2 pr-4 font-normal">RMSE</th>
                  <th className="py-2 pr-4 font-normal">R²</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {Object.entries(forecast.metrics_by_model).map(([name, m]) => (
                  <tr key={name} className={`border-b border-base-700 ${name === forecast.best_model_name ? 'text-signal-teal' : name === 'persistence_baseline' ? 'text-ink-500 italic' : 'text-ink-300'}`}>
                    <td className="py-2 pr-4">{name === 'persistence_baseline' ? 'persistence_baseline (naive)' : name}{name === forecast.best_model_name && ' ★ best'}</td>
                    <td className="py-2 pr-4">{m.mae}</td>
                    <td className="py-2 pr-4">{m.rmse}</td>
                    <td className="py-2 pr-4">{m.r2}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-ink-700 text-xs mt-3">
            Train size: {forecast.train_size} · Test size: {forecast.test_size} · Horizon: {forecast.horizon_days} day(s) ·
            The persistence baseline ("tomorrow = today") checks whether the ML models genuinely improve on the simplest
            possible forecast, not just decoratively outperform a strawman.
          </p>
        </div>
      )}

      {realEvents.length > 0 && (
        <div className="panel p-5 border-risk-low/30">
          <span className="data-label">Historical Flood Events — REAL / SOURCED</span>
          <div className="overflow-x-auto mt-3">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-ink-500 border-b border-base-600">
                  <th className="py-2 pr-4 font-normal">Event</th>
                  <th className="py-2 pr-4 font-normal">Year</th>
                  <th className="py-2 pr-4 font-normal">Peak Discharge</th>
                  <th className="py-2 pr-4 font-normal">Note</th>
                  <th className="py-2 pr-4 font-normal">Source</th>
                </tr>
              </thead>
              <tbody className="text-ink-300">
                {realEvents.map((ev) => (
                  <tr key={ev.event_id} className="border-b border-base-700 align-top">
                    <td className="py-2 pr-4 font-mono text-xs">{ev.event_id}</td>
                    <td className="py-2 pr-4 font-mono text-xs">{ev.year}{ev.month ? ` (${ev.month})` : ''}</td>
                    <td className="py-2 pr-4 font-mono text-xs">
                      {ev.peak_discharge_cumecs ? `${ev.peak_discharge_cumecs.toLocaleString()} m³/s` : '—'}
                    </td>
                    <td className="py-2 pr-4 text-xs max-w-xs">{ev.severity_note}</td>
                    <td className="py-2 pr-4 text-xs text-ink-700 max-w-xs">{ev.citation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-ink-700 text-xs mt-3">
            A small, citable sample of well-documented events at Prakasam Barrage / Vijayawada — not a
            complete authoritative CWC flood archive. Each row's discharge and severity claim traces to
            the cited source.
          </p>
        </div>
      )}

      {/* Optimization Experiments - Steps 12-14 */}
      <div className="panel p-5">
        <span className="data-label">Classical Optimisation Experiments — Approach A vs. Approach B</span>
        <p className="text-ink-500 text-sm mt-2 max-w-2xl">
          Runs a small/medium/large sensor-budget suite comparing the greedy weighted maximum-coverage
          algorithm (Approach A) against a naive top-K-by-individual-score heuristic (Approach B) on the
          current risk map. This is the designated baseline a future quantum optimiser will be
          measured against.
        </p>
        <button
          onClick={runExperiments}
          disabled={runningExperiments}
          className="mt-4 bg-signal-teal text-base-950 font-medium px-5 py-2.5 rounded hover:bg-signal-teal/90 disabled:opacity-40 transition-colors"
        >
          {runningExperiments ? 'Running suite…' : 'Run Experiment Suite'}
        </button>
        {experimentError && <p className="text-risk-critical text-sm mt-3">{experimentError}</p>}

        {experimentRun && (
          <div className="overflow-x-auto mt-5">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-ink-500 border-b border-base-600">
                  <th className="py-2 pr-4 font-normal">Config</th>
                  <th className="py-2 pr-4 font-normal">Sensors</th>
                  <th className="py-2 pr-4 font-normal">A: Objective</th>
                  <th className="py-2 pr-4 font-normal">B: Objective</th>
                  <th className="py-2 pr-4 font-normal">A Advantage</th>
                  <th className="py-2 pr-4 font-normal">A: Coverage %</th>
                  <th className="py-2 pr-4 font-normal">A: Runtime (s)</th>
                </tr>
              </thead>
              <tbody className="font-mono text-ink-300">
                {experimentRun.experiments.map((exp) => (
                  <tr key={exp.experiment_id} className="border-b border-base-700">
                    <td className="py-2 pr-4">{exp.config.label}</td>
                    <td className="py-2 pr-4">{exp.config.num_sensors}</td>
                    <td className="py-2 pr-4 text-signal-teal">{exp.approach_a_greedy.objective_score}</td>
                    <td className="py-2 pr-4">{exp.approach_b_naive_topk.objective_score}</td>
                    <td className="py-2 pr-4">{exp.greedy_advantage_objective_score >= 0 ? '+' : ''}{exp.greedy_advantage_objective_score}</td>
                    <td className="py-2 pr-4">{exp.approach_a_greedy.coverage_percentage}%</td>
                    <td className="py-2 pr-4">{exp.approach_a_greedy.execution_time_seconds}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-ink-700 text-xs mt-3">
              Saved to <span className="font-mono">{experimentRun.saved_to}</span> under
              backend/app/data/processed/experiments/ for reproducibility.
            </p>
          </div>
        )}
      </div>

      <div className="panel p-5 border-risk-moderate/30">
        <span className="data-label">System Limitations (documented)</span>
        <ul className="text-ink-300 text-sm mt-3 space-y-2 list-disc list-inside">
          <li>All hydro-meteorological time series (rainfall, water level, inflow) are SIMULATED_INPUT: a deterministic, seeded synthetic series, not live CWC/IMD telemetry.</li>
          <li>Historical flood events are REAL_HISTORICAL but a small, citable sample - not a complete authoritative CWC flood archive.</li>
          <li>Study-area boundary is a project-defined rectangular scoping frame and risk zones use a documented grid spatial model — neither is an official administrative or hydrological polygon.</li>
          <li>River geometry is PARTIALLY_REAL: several vertices are real, sourced landmark coordinates, but the full path is not a surveyed river-network dataset (see Data Provenance above for why the authoritative government dataset couldn't be integrated in this environment).</li>
          <li>Distance-to-river is computed against the nearest point on the actual river geometry using real haversine (great-circle) distance in kilometres — an accepted spherical-earth approximation at this ~15km study-area scale, not a full projected-CRS calculation.</li>
          <li>The risk engine uses illustrative thresholds; real deployment requires calibration against CWC/KGBO official flood-stage data.</li>
          <li>The greedy maximum-coverage optimiser is a (1&minus;1/e)-approximate algorithm, not an exact ILP solution — the naive top-K baseline above exists specifically to make that advantage measurable rather than asserted.</li>
          <li>Communication connectivity assumes free-space great-circle distance only; it does not model terrain, obstruction, or real RF propagation. It also respects a hard, user-configurable communication-node budget — sensors can be left honestly disconnected if that budget is exhausted.</li>
          <li>The current implementation covers the Vijayawada&ndash;Krishna River corridor only, not the full Krishna-Godavari basin.</li>
          <li>Quantum modules (QAOA sensor placement and 4-qubit VQR forecasting) use classical statevector simulation in pure NumPy with deterministic seeds; no physical quantum hardware execution or empirical quantum advantage is claimed.</li>
        </ul>
      </div>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div className="data-label">{label}</div>
      <div className="text-ink-100 font-mono text-sm mt-1">{value}</div>
    </div>
  )
}

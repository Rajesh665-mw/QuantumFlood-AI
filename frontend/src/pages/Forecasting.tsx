import { useEffect, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { api, ApiError } from '../services/api'
import type {
  DatasetSummary,
  HydroRecord,
  ForecastTrainResult,
  ForecastPrediction,
  QmlForecastResult,
  ForecastComparisonResponse,
} from '../types'
import { LoadingState, ErrorState, EmptyState } from '../components/LoadingState'

const MODEL_LABELS: Record<string, string> = {
  persistence_baseline: 'Persistence Baseline (naive)',
  linear_regression: 'Linear Regression',
  random_forest: 'Random Forest',
  gradient_boosting: 'Gradient Boosting',
  quantum_variational_regressor: '4-Qubit Variational Quantum Regressor (VQR)',
}

export default function Forecasting() {
  const [summary, setSummary] = useState<DatasetSummary | null>(null)
  const [history, setHistory] = useState<HydroRecord[]>([])
  const [horizon, setHorizon] = useState(1)
  const [resolution, setResolution] = useState<'low' | 'default' | 'high'>('default')

  // Classical Forecasting State
  const [trainResult, setTrainResult] = useState<ForecastTrainResult | null>(null)
  const [prediction, setPrediction] = useState<ForecastPrediction | null>(null)
  const [training, setTraining] = useState(false)

  // QML Forecasting State
  const [qmlResult, setQmlResult] = useState<QmlForecastResult | null>(null)
  const [qmlPrediction, setQmlPrediction] = useState<ForecastPrediction | null>(null)
  const [qmlTraining, setQmlTraining] = useState(false)

  // Comparison State
  const [comparison, setComparison] = useState<ForecastComparisonResponse | null>(null)
  const [comparing, setComparing] = useState(false)

  // Downstream Risk Integration State
  const [activeRiskSource, setActiveRiskSource] = useState<'classical' | 'qml'>('classical')
  const [applyingRisk, setApplyingRisk] = useState(false)
  const [riskFeedback, setRiskFeedback] = useState<string | null>(null)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.datasetSummary(), api.timeseries(120)])
      .then(([s, t]) => { setSummary(s); setHistory(t.records) })
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Failed to load dataset.'))
      .finally(() => setLoading(false))
  }, [])

  // 1. Classical ML Training & Inference
  const runClassicalTraining = async () => {
    setTraining(true)
    setError(null)
    try {
      const result = await api.trainForecast(horizon)
      setTrainResult(result)
      const pred = await api.predictForecast(horizon)
      setPrediction(pred)
      setActiveRiskSource('classical')
      // Immediately turn classical forecast into downstream risk map
      await api.generateRisk({ use_latest_forecast: true, resolution, forecast_model_preference: 'classical' })
      setRiskFeedback('Classical forecast generated and synced to spatial risk map.')
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Classical training failed.')
    } finally {
      setTraining(false)
    }
  }

  // 2. QML VQR Training & Inference
  const runQmlTraining = async () => {
    setQmlTraining(true)
    setError(null)
    try {
      const qResult = await api.trainQmlForecast({ horizon_days: horizon, n_layers: 2, max_iter: 30, train_subsample: 100 })
      setQmlResult(qResult)
      const qPred = await api.predictQmlForecast(horizon)
      setQmlPrediction(qPred)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'QML training failed.')
    } finally {
      setQmlTraining(false)
    }
  }

  // 3. Tournament Comparison
  const runTournamentComparison = async () => {
    setComparing(true)
    setError(null)
    try {
      const comp = await api.compareForecasts(horizon)
      setComparison(comp)
      if (comp.classical) {
        setPrediction({
          based_on_date: new Date().toISOString().split('T')[0],
          horizon_days: comp.horizon_days,
          predicted_water_level_m: comp.classical.predicted_water_level_m ?? 0,
          last_known_rainfall_mm: 0,
          last_known_inflow_ktcmd: 0,
          last_known_water_level_m: 0,
          model_used: comp.classical.model_name,
        })
      }
      if (comp.qml && comp.qml.available) {
        setQmlPrediction({
          based_on_date: new Date().toISOString().split('T')[0],
          horizon_days: comp.horizon_days,
          predicted_water_level_m: comp.qml.predicted_water_level_m ?? 0,
          last_known_rainfall_mm: 0,
          last_known_inflow_ktcmd: 0,
          last_known_water_level_m: 0,
          model_used: comp.qml.model_name,
        })
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Comparison failed.')
    } finally {
      setComparing(false)
    }
  }

  // 4. Downstream Risk Pipeline Coupling
  const applySelectedForecastToRisk = async (source: 'classical' | 'qml') => {
    setApplyingRisk(true)
    setError(null)
    try {
      await api.generateRisk({ use_latest_forecast: true, resolution, forecast_model_preference: source })
      setActiveRiskSource(source)
      setRiskFeedback(`Spatial risk pipeline updated using ${source.toUpperCase()} forecast.`)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : `Failed to update risk map with ${source} forecast.`)
    } finally {
      setApplyingRisk(false)
    }
  }

  if (loading) return <LoadingState label="Loading hydrological dataset…" />

  return (
    <div className="flex flex-col gap-8">
      <div>
        <div className="flex items-center gap-2">
          <span className="eyebrow">Module 2 · Forecasting & QML</span>
          <span className="text-xs px-2 py-0.5 rounded bg-signal-teal/10 text-signal-teal border border-signal-teal/30 font-mono">
            Classical Baseline + 4-Qubit VQR
          </span>
        </div>
        <h1 className="font-display text-2xl text-ink-100 mt-1">Flood & Water-Level Forecasting</h1>
        <p className="text-ink-500 text-sm mt-2 max-w-3xl">
          Water-level forecasts are produced using classical machine-learning ensembles alongside an
          experimental 4-qubit Variational Quantum Regressor (VQR) with data re-uploading. Classical models
          remain the verified production baseline.
        </p>
      </div>

      {error && <ErrorState message={error} />}

      {summary && (
        <div className="panel p-5">
          <span className="data-label">Dataset — {summary.data_source_label}</span>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-3">
            <Metric label="Records" value={summary.row_count} />
            <Metric label="Date Range" value={`${summary.date_range.start} → ${summary.date_range.end}`} />
            <Metric label="Duplicate Rows" value={summary.duplicate_rows} />
            <Metric label="Missing Values" value={Object.values(summary.missing_values).reduce((a, b) => a + b, 0)} />
          </div>
        </div>
      )}

      {/* Historical Timeseries Chart */}
      <div className="panel p-5">
        <span className="data-label">Historical Rainfall / Inflow / Water Level (last 120 days)</span>
        <div className="h-72 mt-4">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={history}>
              <CartesianGrid stroke="#29343F" strokeDasharray="2 4" />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#8A96A8' }} minTickGap={40} />
              <YAxis yAxisId="left" tick={{ fontSize: 10, fill: '#8A96A8' }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10, fill: '#8A96A8' }} />
              <Tooltip contentStyle={{ background: '#1C2634', border: '1px solid #29343F', fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line yAxisId="left" type="monotone" dataKey="water_level_m" stroke="#2DD4BF" dot={false} strokeWidth={2} name="Water Level (m)" />
              <Line yAxisId="right" type="monotone" dataKey="rainfall_mm" stroke="#C99A3B" dot={false} strokeWidth={1.5} name="Rainfall (mm)" />
              <Line yAxisId="right" type="monotone" dataKey="inflow_ktcmd" stroke="#D9803E" dot={false} strokeWidth={1} strokeDasharray="3 3" name="Inflow (kTCM/d)" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Forecast Controls & Execution Bar */}
      <div className="panel p-5">
        <span className="data-label">Forecast Controls</span>
        <div className="flex flex-wrap items-end gap-4 mt-3">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-ink-500">Forecast horizon (days ahead)</span>
            <input
              type="number" min={1} max={14} value={horizon}
              onChange={(e) => setHorizon(Number(e.target.value))}
              className="bg-base-700 border border-base-600 rounded px-3 py-2 w-32 font-mono text-ink-100"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-ink-500">Risk-zone resolution</span>
            <select
              value={resolution}
              onChange={(e) => setResolution(e.target.value as 'low' | 'default' | 'high')}
              className="bg-base-700 border border-base-600 rounded px-3 py-2 w-40 font-mono text-ink-100"
            >
              <option value="low">Low (16 zones)</option>
              <option value="default">Default (36 zones)</option>
              <option value="high">High (100 zones)</option>
            </select>
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={runClassicalTraining}
              disabled={training || qmlTraining}
              className="bg-signal-teal text-base-950 font-medium px-4 py-2.5 rounded hover:bg-signal-teal/90 disabled:opacity-50 transition-colors"
            >
              {training ? 'Training Classical…' : 'Train Classical Baseline'}
            </button>
            <button
              onClick={runQmlTraining}
              disabled={training || qmlTraining}
              className="bg-signal-blue text-white font-medium px-4 py-2.5 rounded hover:bg-signal-blue/90 disabled:opacity-50 transition-colors flex items-center gap-1.5"
            >
              <span className="text-xs font-mono bg-white/20 px-1.5 py-0.5 rounded">VQR</span>
              {qmlTraining ? 'Simulating 4-Qubit Circuit…' : 'Train QML Model'}
            </button>
            <button
              onClick={runTournamentComparison}
              disabled={comparing || training || qmlTraining}
              className="bg-base-700 text-ink-200 border border-base-600 font-medium px-4 py-2.5 rounded hover:bg-base-600 disabled:opacity-50 transition-colors"
            >
              {comparing ? 'Benchmarking Models…' : 'Compare Classical vs QML'}
            </button>
          </div>
        </div>
      </div>

      {/* Downstream Risk Routing & Active Source Indicator */}
      <div className="panel p-4 flex flex-wrap items-center justify-between gap-4 bg-base-800/60 border border-base-700">
        <div className="flex items-center gap-3">
          <span className="text-xs uppercase tracking-wider text-ink-500 font-mono">Downstream Risk Feed:</span>
          <span className={`px-2.5 py-1 rounded text-xs font-mono font-medium ${
            activeRiskSource === 'classical'
              ? 'bg-signal-teal/20 text-signal-teal border border-signal-teal/40'
              : 'bg-signal-blue/20 text-signal-blue border border-signal-blue/40'
          }`}>
            {activeRiskSource === 'classical' ? '● CLASSICAL FORECAST (Production Baseline)' : '◆ QML VQR FORECAST (Experimental Simulation)'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-ink-500">Route to Spatial Risk Map:</span>
          <button
            onClick={() => applySelectedForecastToRisk('classical')}
            disabled={applyingRisk || !prediction}
            className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
              activeRiskSource === 'classical'
                ? 'bg-signal-teal/30 text-signal-teal border border-signal-teal'
                : 'bg-base-700 text-ink-400 border border-base-600 hover:text-ink-200'
            }`}
          >
            Apply Classical
          </button>
          <button
            onClick={() => applySelectedForecastToRisk('qml')}
            disabled={applyingRisk || (!qmlPrediction && (!comparison?.qml?.available))}
            className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
              activeRiskSource === 'qml'
                ? 'bg-signal-blue/30 text-signal-blue border border-signal-blue'
                : 'bg-base-700 text-ink-400 border border-base-600 hover:text-ink-200'
            }`}
          >
            Apply QML
          </button>
        </div>
      </div>

      {riskFeedback && (
        <div className="text-xs text-signal-teal bg-signal-teal/10 px-4 py-2 rounded border border-signal-teal/20 flex items-center justify-between">
          <span>✓ {riskFeedback}</span>
          <button onClick={() => setRiskFeedback(null)} className="text-ink-500 hover:text-ink-300">✕</button>
        </div>
      )}

      {/* Side-by-Side Forecast Results Grid */}
      {(prediction || qmlPrediction || comparison) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Classical Forecast Panel */}
          <div className="panel p-5 border-signal-tealDim/40 relative">
            <div className="flex items-center justify-between">
              <span className="data-label">Classical Forecast (Baseline)</span>
              <span className="text-xs px-2 py-0.5 rounded bg-signal-teal/10 text-signal-teal border border-signal-teal/20 font-mono">
                Production
              </span>
            </div>
            {prediction ? (
              <>
                <div className="flex items-baseline gap-2 mt-3">
                  <span className="font-mono text-3xl text-signal-teal">{prediction.predicted_water_level_m}</span>
                  <span className="text-ink-500">m predicted water level, {horizon} day(s) ahead</span>
                </div>
                <p className="text-ink-500 text-xs mt-2">
                  Model: <span className="text-ink-300 font-mono">{MODEL_LABELS[prediction.model_used] ?? prediction.model_used}</span>
                </p>
                {trainResult && trainResult.metrics_by_model[trainResult.best_model_name] && (
                  <div className="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-base-700/60 font-mono text-xs">
                    <div><span className="text-ink-500 block">MAE:</span> {trainResult.metrics_by_model[trainResult.best_model_name].mae}m</div>
                    <div><span className="text-ink-500 block">RMSE:</span> {trainResult.metrics_by_model[trainResult.best_model_name].rmse}m</div>
                    <div><span className="text-ink-500 block">R²:</span> {trainResult.metrics_by_model[trainResult.best_model_name].r2}</div>
                  </div>
                )}
              </>
            ) : (
              <p className="text-ink-500 text-sm mt-4">Classical forecast not yet run for horizon {horizon}.</p>
            )}
          </div>

          {/* QML VQR Forecast Panel */}
          <div className="panel p-5 border-signal-blueDim/40 relative">
            <div className="flex items-center justify-between">
              <span className="data-label">Quantum Machine Learning (VQR)</span>
              <span className="text-xs px-2 py-0.5 rounded bg-signal-blue/10 text-signal-blue border border-signal-blue/20 font-mono">
                Experimental
              </span>
            </div>
            {qmlPrediction ? (
              <>
                <div className="flex items-baseline gap-2 mt-3">
                  <span className="font-mono text-3xl text-signal-blue">{qmlPrediction.predicted_water_level_m}</span>
                  <span className="text-ink-500">m predicted water level, {horizon} day(s) ahead</span>
                </div>
                <div className="grid grid-cols-2 gap-2 mt-2 text-xs text-ink-500 font-mono">
                  <div>Qubits: <span className="text-ink-300">4</span></div>
                  <div>Circuit Depth: <span className="text-ink-300">11</span></div>
                  <div>Variational Layers: <span className="text-ink-300">2 (L=2)</span></div>
                  <div>Trainable Params: <span className="text-ink-300">16</span></div>
                </div>
                {qmlResult && (
                  <div className="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-base-700/60 font-mono text-xs">
                    <div><span className="text-ink-500 block">MAE:</span> {qmlResult.test_mae}m</div>
                    <div><span className="text-ink-500 block">RMSE:</span> {qmlResult.test_rmse}m</div>
                    <div><span className="text-ink-500 block">R²:</span> {qmlResult.test_r2}</div>
                  </div>
                )}
              </>
            ) : (
              <div className="mt-4">
                <p className="text-ink-500 text-sm">4-qubit VQR not yet simulated for horizon {horizon}.</p>
                <p className="text-xs text-ink-600 mt-2">
                  Input features: water_level_m, inflow_ktcmd, rainfall_roll3, rainfall_mm mapped to Ry angle rotations.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Model Tournament & Comparative Benchmarks */}
      {comparison && (
        <div className="panel p-5 border border-base-700">
          <div className="flex items-center justify-between">
            <span className="data-label">Tournament Comparison (Classical Baseline vs 4-Qubit VQR)</span>
            <span className="text-xs text-ink-500 font-mono">Horizon: {comparison.horizon_days} day(s)</span>
          </div>

          <div className="overflow-x-auto mt-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-ink-500 border-b border-base-600">
                  <th className="py-2 pr-4 font-normal">Model</th>
                  <th className="py-2 pr-4 font-normal">Category</th>
                  <th className="py-2 pr-4 font-normal">MAE</th>
                  <th className="py-2 pr-4 font-normal">RMSE</th>
                  <th className="py-2 pr-4 font-normal">R²</th>
                  <th className="py-2 pr-4 font-normal">Predicted (m)</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {/* Classical Models */}
                {Object.entries(comparison.classical.all_classical_models).map(([name, m]) => (
                  <tr key={name} className={`border-b border-base-700 ${name === comparison.classical.model_name ? 'text-signal-teal font-semibold' : 'text-ink-300'}`}>
                    <td className="py-2 pr-4">{MODEL_LABELS[name] ?? name} {name === comparison.classical.model_name && '★ best classical'}</td>
                    <td className="py-2 pr-4 text-xs text-ink-500">Classical ML</td>
                    <td className="py-2 pr-4">{m.mae}</td>
                    <td className="py-2 pr-4">{m.rmse}</td>
                    <td className="py-2 pr-4">{m.r2}</td>
                    <td className="py-2 pr-4">{name === comparison.classical.model_name ? comparison.classical.predicted_water_level_m : '—'}</td>
                  </tr>
                ))}
                {/* QML Regressor */}
                {comparison.qml.available && comparison.qml.metrics && (
                  <tr className="border-b border-base-700 text-signal-blue font-semibold">
                    <td className="py-2 pr-4">4-Qubit VQR (Statevector Sim)</td>
                    <td className="py-2 pr-4 text-xs text-ink-500">Quantum ML (Simulated)</td>
                    <td className="py-2 pr-4">{comparison.qml.metrics.mae}</td>
                    <td className="py-2 pr-4">{comparison.qml.metrics.rmse}</td>
                    <td className="py-2 pr-4">{comparison.qml.metrics.r2}</td>
                    <td className="py-2 pr-4">{comparison.qml.predicted_water_level_m}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {comparison.comparison && (
            <div className="mt-4 p-4 rounded bg-base-800/80 border border-base-700/60 text-xs">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-ink-200">Observation:</span>
                <span className="text-ink-300">{comparison.comparison.observation}</span>
              </div>
              <p className="text-ink-500 mt-2 leading-relaxed">
                <span className="font-semibold text-ink-400">Scientific Note: </span>
                {comparison.comparison.scientific_note}
              </p>
            </div>
          )}

          {/* Multi-Seed Statistical Robustness Evaluation (UC-067 Target B) */}
          {comparison.multiseed_evaluation && (
            <div className="mt-4 p-4 rounded bg-base-900/90 border border-base-700/80 space-y-3">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-signal-blue" />
                  <span className="font-mono text-xs uppercase tracking-wider text-ink-300 font-semibold">
                    UC-067 Target B: Multi-Seed Robustness Evaluation (4 Deterministic Seeds)
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs font-mono text-ink-300">
                  <span>Mean R²: <strong className="text-signal-blue">{comparison.multiseed_evaluation.summary.mean_r2.toFixed(4)}</strong> ± {comparison.multiseed_evaluation.summary.std_r2.toFixed(4)}</span>
                  <span>Mean MAE: <strong className="text-signal-blue">{comparison.multiseed_evaluation.summary.mean_mae.toFixed(4)}m</strong> ± {comparison.multiseed_evaluation.summary.std_mae.toFixed(4)}</span>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono border-collapse">
                  <thead>
                    <tr className="border-b border-base-700 text-ink-400 bg-base-800/40">
                      <th className="p-2">Seed</th>
                      <th className="p-2">R² Score</th>
                      <th className="p-2">MAE (m)</th>
                      <th className="p-2">RMSE (m)</th>
                      <th className="p-2">Runtime (s)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-base-800">
                    {comparison.multiseed_evaluation.runs.map((r) => (
                      <tr key={r.seed} className="hover:bg-base-800/50 text-ink-300">
                        <td className="p-2 font-semibold text-ink-200">seed = {r.seed}</td>
                        <td className="p-2">{r.r2.toFixed(4)}</td>
                        <td className="p-2">{r.mae.toFixed(4)}m</td>
                        <td className="p-2">{r.rmse.toFixed(4)}m</td>
                        <td className="p-2">{r.runtime_s.toFixed(2)}s</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <p className="text-[11px] text-ink-400 italic">
                {comparison.multiseed_evaluation.academic_conclusion}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Classical Models Table (Default display if comparison not run) */}
      {trainResult && !comparison && (
        <div className="panel p-5">
          <span className="data-label">Classical Model Evaluation (chronological hold-out test set)</span>
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
                {Object.entries(trainResult.metrics_by_model).map(([name, m]) => (
                  <tr key={name} className={`border-b border-base-700 ${name === trainResult.best_model_name ? 'text-signal-teal' : 'text-ink-300'}`}>
                    <td className="py-2 pr-4">{MODEL_LABELS[name] ?? name} {name === trainResult.best_model_name && '★ best'}</td>
                    <td className="py-2 pr-4">{m.mae}</td>
                    <td className="py-2 pr-4">{m.rmse}</td>
                    <td className="py-2 pr-4">{m.r2}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-ink-700 text-xs mt-3">
            Train size: {trainResult.train_size} · Test size: {trainResult.test_size} ·
            Selected by lowest RMSE on held-out chronological data.
          </p>
        </div>
      )}

      {!trainResult && !qmlResult && !comparison && !error && (
        <EmptyState
          title="No forecast run yet"
          description="Click 'Train Classical Baseline' or 'Train QML Model' above to train models on the current dataset and generate continuous water-level forecasts."
        />
      )}
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

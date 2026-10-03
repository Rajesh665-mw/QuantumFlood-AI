import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import MainLayout from './layouts/MainLayout'
import { LoadingState } from './components/LoadingState'

// Route-level code splitting
const Home = lazy(() => import('./pages/Home'))
const CommandCenter = lazy(() => import('./pages/CommandCenter'))
const Forecasting = lazy(() => import('./pages/Forecasting'))
const RiskMap = lazy(() => import('./pages/RiskMap'))
const SensorOptimisation = lazy(() => import('./pages/SensorOptimisation'))
const NetworkCoverage = lazy(() => import('./pages/NetworkCoverage'))
const DisasterResponse = lazy(() => import('./pages/DisasterResponse'))
const DataAnalytics = lazy(() => import('./pages/DataAnalytics'))

// 6 New Integrated Modules
const SafeLocations = lazy(() => import('./pages/SafeLocations'))
const EvacuationRouting = lazy(() => import('./pages/EvacuationRouting'))
const AdaptiveRedeployment = lazy(() => import('./pages/AdaptiveRedeployment'))
const NetworkResilience = lazy(() => import('./pages/NetworkResilience'))
const ResourceAllocation = lazy(() => import('./pages/ResourceAllocation'))
const ScenarioComparison = lazy(() => import('./pages/ScenarioComparison'))

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<LoadingState label="Loading module…" />}>
        <Routes>
          <Route element={<MainLayout />}>
            {/* Core Overview */}
            <Route path="/" element={<Home />} />
            <Route path="/command-center" element={<CommandCenter />} />

            {/* Flood Intelligence */}
            <Route path="/forecasting" element={<Forecasting />} />
            <Route path="/risk-map" element={<RiskMap />} />
            <Route path="/scenarios" element={<ScenarioComparison />} />
            <Route path="/scenario-comparison" element={<ScenarioComparison />} />

            {/* Infrastructure */}
            <Route path="/sensor-optimisation" element={<SensorOptimisation />} />
            <Route path="/adaptive-redeployment" element={<AdaptiveRedeployment />} />
            <Route path="/network-coverage" element={<NetworkCoverage />} />
            <Route path="/network-resilience" element={<NetworkResilience />} />

            {/* Emergency Response */}
            <Route path="/safe-locations" element={<SafeLocations />} />
            <Route path="/evacuation-routing" element={<EvacuationRouting />} />
            <Route path="/resource-allocation" element={<ResourceAllocation />} />
            <Route path="/disaster-response" element={<DisasterResponse />} />

            {/* Analytics */}
            <Route path="/data-analytics" element={<DataAnalytics />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

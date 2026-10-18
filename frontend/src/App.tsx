import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense, useEffect } from 'react'
import MainLayout from './layouts/MainLayout'
import { PageSkeleton } from './components/LoadingState'
import { api } from './services/api'

// Primary 5 Navigation Sections
const Home = lazy(() => import('./pages/Home'))
const SensorPlacement = lazy(() => import('./pages/SensorPlacement'))
const HistoricalIntelligence = lazy(() => import('./pages/HistoricalIntelligence'))
const SafeShelters = lazy(() => import('./pages/SafeShelters'))
const ResourcePlanning = lazy(() => import('./pages/ResourcePlanning'))

export default function App() {
  // Manage startup splash screen lifecycle
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search)
    const isTestingSplash = urlParams.get('splash') === '1' || urlParams.get('test-splash') === 'true'

    // Expose dev helper functions to test/inspect startup splash at any time
    ;(window as any).__showSplash = () => {
      const splash = document.getElementById('qf-splash')
      if (splash) {
        splash.style.display = 'flex'
        splash.style.opacity = '1'
        splash.style.pointerEvents = 'auto'
        splash.style.visibility = 'visible'
      }
    }
    ;(window as any).__dismissSplash = () => {
      const splash = document.getElementById('qf-splash')
      if (splash) {
        splash.style.transition = 'opacity 0.5s cubic-bezier(0.4, 0, 0.2, 1), visibility 0.5s ease'
        splash.style.opacity = '0'
        splash.style.pointerEvents = 'none'
        setTimeout(() => {
          splash.style.display = 'none'
        }, 550)
      }
    }

    // Genuine startup initialization: verify backend health & study area context
    const initBackend = api.currentArea().catch(() => null)
    Promise.all([
      initBackend,
      new Promise((resolve) => setTimeout(resolve, 1000)),
    ]).finally(() => {
      if (isTestingSplash) {
        console.info('[QuantumFlood AI] Startup splash held open for inspection via ?splash=1')
        return
      }
      const splash = document.getElementById('qf-splash')
      if (splash) {
        splash.style.transition = 'opacity 0.5s cubic-bezier(0.4, 0, 0.2, 1), visibility 0.5s ease'
        splash.style.opacity = '0'
        splash.style.pointerEvents = 'none'
        setTimeout(() => {
          splash.style.display = 'none'
        }, 550)
      }
    })
  }, [])

  return (
    <BrowserRouter>
      <Suspense fallback={<PageSkeleton />}>
        <Routes>
          <Route element={<MainLayout />}>
            {/* The 5 Non-Negotiable Primary Sections */}
            <Route path="/" element={<Home />} />
            <Route path="/sensor-placement" element={<SensorPlacement />} />
            <Route path="/historical-intelligence" element={<HistoricalIntelligence />} />
            <Route path="/shelters" element={<SafeShelters />} />
            <Route path="/resource-planning" element={<ResourcePlanning />} />

            {/* Seamless Redirects for Legacy / Deep URLs */}
            <Route path="/sensor-optimisation" element={<Navigate to="/sensor-placement" replace />} />
            <Route path="/adaptive-redeployment" element={<Navigate to="/sensor-placement" replace />} />
            <Route path="/network-coverage" element={<Navigate to="/sensor-placement" replace />} />
            <Route path="/network-resilience" element={<Navigate to="/sensor-placement" replace />} />

            <Route path="/forecasting" element={<Navigate to="/historical-intelligence" replace />} />
            <Route path="/risk-map" element={<Navigate to="/historical-intelligence" replace />} />
            <Route path="/scenarios" element={<Navigate to="/historical-intelligence" replace />} />
            <Route path="/scenario-comparison" element={<Navigate to="/historical-intelligence" replace />} />
            <Route path="/data-analytics" element={<Navigate to="/historical-intelligence" replace />} />

            <Route path="/safe-locations" element={<Navigate to="/shelters" replace />} />
            <Route path="/evacuation-routing" element={<Navigate to="/shelters" replace />} />

            <Route path="/resource-allocation" element={<Navigate to="/resource-planning" replace />} />
            <Route path="/disaster-response" element={<Navigate to="/resource-planning" replace />} />
            <Route path="/command-center" element={<Navigate to="/resource-planning" replace />} />

            {/* Catch-all fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

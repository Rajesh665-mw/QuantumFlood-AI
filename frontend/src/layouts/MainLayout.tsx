import { useState, useEffect } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { api } from '../services/api'

interface NavGroup {
  title: string
  items: {
    to: string
    label: string
    end?: boolean
    icon: JSX.Element
    badge?: string
  }[]
}

const NAV_GROUPS: NavGroup[] = [
  {
    title: 'Overview',
    items: [
      {
        to: '/',
        label: 'Home',
        end: true,
        icon: (
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
        ),
      },
      {
        to: '/command-center',
        label: 'Command Center',
        icon: (
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
          </svg>
        ),
      },
    ],
  },
  {
    title: 'Flood Intelligence',
    items: [
      {
        to: '/forecasting',
        label: 'Forecasting',
        icon: (
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
          </svg>
        ),
      },
      {
        to: '/risk-map',
        label: 'Risk Map',
        icon: (
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l5.447 2.724A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
          </svg>
        ),
      },
      {
        to: '/scenario-comparison',
        label: 'Scenarios & Simulator',
        icon: (
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        ),
        badge: 'NEW',
      },
    ],
  },
  {
    title: 'Infrastructure',
    items: [
      {
        to: '/sensor-optimisation',
        label: 'Sensor Placement',
        icon: (
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
          </svg>
        ),
      },
      {
        to: '/adaptive-redeployment',
        label: 'Adaptive Redeployment',
        icon: (
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        ),
        badge: 'NEW',
      },
      {
        to: '/network-coverage',
        label: 'Network Coverage',
        icon: (
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.141 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0" />
          </svg>
        ),
      },
      {
        to: '/network-resilience',
        label: 'Network Resilience',
        icon: (
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M18.364 5.636a9 9 0 010 12.728m0 0l-2.829-2.829m2.829 2.829L21 21M15.536 8.464a5 5 0 010 7.072m0 0l-2.829-2.829m-4.243 2.829a4.978 4.978 0 01-1.414-2.83m-1.414 5.658a9 9 0 01-2.167-9.238m7.824 2.167a1 1 0 111.414 1.414m-1.414-1.414L3 3m8.293 8.293l1.414 1.414" />
          </svg>
        ),
        badge: 'NEW',
      },
    ],
  },
  {
    title: 'Emergency Response',
    items: [
      {
        to: '/safe-locations',
        label: 'Safe Locations',
        icon: (
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        ),
        badge: 'NEW',
      },
      {
        to: '/evacuation-routing',
        label: 'Evacuation Routing',
        icon: (
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l5.447 2.724A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
          </svg>
        ),
        badge: 'NEW',
      },
      {
        to: '/resource-allocation',
        label: 'Resource Allocation',
        icon: (
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
        ),
        badge: 'NEW',
      },
      {
        to: '/disaster-response',
        label: 'Rule-Based Advisory',
        icon: (
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        ),
      },
    ],
  },
  {
    title: 'Analytics & Data',
    items: [
      {
        to: '/data-analytics',
        label: 'Data Provenance',
        icon: (
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
          </svg>
        ),
      },
    ],
  },
]

export default function MainLayout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [isDefaultArea, setIsDefaultArea] = useState(true)

  useEffect(() => {
    const fetchArea = () => {
      api.currentArea()
        .then((r) => {
          if (r.study_area?.name) {
            setCurrentAreaName(r.study_area.name.replace(' Study Area', ''))
          }
          setIsDefaultArea(r.is_default_location ?? true)
        })
        .catch(() => {})
    }
    fetchArea()

    const onAreaChanged = (e: any) => {
      if (e.detail?.name) {
        setCurrentAreaName(e.detail.name.replace(' Study Area', ''))
        setIsDefaultArea(e.detail.name.includes('Vijayawada'))
      } else {
        fetchArea()
      }
    }
    window.addEventListener('study-area-changed', onAreaChanged)
    return () => window.removeEventListener('study-area-changed', onAreaChanged)
  }, [])

  const handleQuickReset = async () => {
    try {
      const res = await api.resetArea()
      if (res.status === 'OK') {
        setCurrentAreaName('Vijayawada Benchmark')
        setIsDefaultArea(true)
        window.dispatchEvent(new CustomEvent('study-area-changed', { detail: res.study_area }))
      }
    } catch {
      // ignore
    }
  }

  return (
    <div className="min-h-screen flex bg-base-950 text-ink-100 selection:bg-signal-teal selection:text-base-950 overflow-x-hidden">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex flex-col w-64 shrink-0 bg-base-900 border-r border-base-600 min-h-screen sticky top-0 h-screen z-30 overflow-hidden">
        {/* Brand header */}
        <div className="p-4 border-b border-base-600/60 flex items-center justify-between">
          <NavLink to="/" className="flex items-center gap-3 group">
            <span className="w-2.5 h-2.5 rounded-full bg-signal-teal shadow-[0_0_10px_rgba(45,212,191,0.8)] group-hover:scale-125 transition-transform" />
            <div>
              <div className="font-display font-bold text-base tracking-tight text-ink-100 group-hover:text-signal-teal transition-colors">
                QuantumFlood AI
              </div>
              <div className="text-[10px] font-mono text-ink-500 uppercase tracking-wider">
                Disaster Intelligence
              </div>
            </div>
          </NavLink>
        </div>

        {/* Navigation list */}
        <nav className="flex-1 px-3 py-3 space-y-4 overflow-y-auto">
          {NAV_GROUPS.map((group) => (
            <div key={group.title} className="space-y-1">
              <div className="px-2.5 text-[10px] font-mono uppercase tracking-wider text-ink-500 font-semibold">
                {group.title}
              </div>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    `flex items-center justify-between px-2.5 py-2 rounded text-xs font-medium transition-all duration-150 ${
                      isActive
                        ? 'bg-base-700/90 text-signal-teal border-l-2 border-signal-teal shadow-sm font-semibold'
                        : 'text-ink-400 hover:text-ink-100 hover:bg-base-800/60'
                    }`
                  }
                >
                  <div className="flex items-center gap-2.5 min-w-0 truncate">
                    {item.icon}
                    <span className="truncate">{item.label}</span>
                  </div>
                  {item.badge && (
                    <span className="text-[9px] font-mono font-bold px-1.5 py-0.2 rounded bg-signal-teal/15 text-signal-teal border border-signal-teal/30">
                      {item.badge}
                    </span>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-3 border-t border-base-600/60 bg-base-950/40">
          <div className="flex items-center justify-between text-xs text-ink-500">
            <span className="flex items-center gap-1.5 min-w-0 pr-1">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shrink-0" />
              <span className="truncate">{currentAreaName} Active</span>
            </span>
            <span className="font-mono text-[10px] text-ink-700 shrink-0">v2.0</span>
          </div>
        </div>
      </aside>

      {/* Mobile Top Header */}
      <div className="lg:hidden flex flex-col w-full min-h-screen">
        <header className="bg-base-900 border-b border-base-600 px-4 py-3 flex items-center justify-between sticky top-0 z-40">
          <NavLink to="/" className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-signal-teal shadow-[0_0_8px_rgba(45,212,191,0.8)]" />
            <span className="font-display font-semibold text-ink-100 tracking-tight text-base">
              QuantumFlood AI
            </span>
          </NavLink>
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="p-2 rounded text-ink-500 hover:text-ink-100 hover:bg-base-800 transition-colors"
            aria-label="Toggle navigation menu"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              {mobileOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </header>

        {/* Mobile Navigation Dropdown */}
        {mobileOpen && (
          <div className="bg-base-900 border-b border-base-600 px-4 py-3 space-y-3 z-40 max-h-[80vh] overflow-y-auto">
            {NAV_GROUPS.map((group) => (
              <div key={group.title} className="space-y-1">
                <div className="text-[10px] font-mono uppercase tracking-wider text-ink-500 font-semibold px-1">
                  {group.title}
                </div>
                {group.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    onClick={() => setMobileOpen(false)}
                    className={({ isActive }) =>
                      `flex items-center justify-between px-3 py-2 rounded text-xs font-medium ${
                        isActive
                          ? 'bg-base-700 text-signal-teal font-semibold'
                          : 'text-ink-400 hover:text-ink-100 hover:bg-base-800'
                      }`
                    }
                  >
                    <div className="flex items-center gap-2.5">
                      {item.icon}
                      <span>{item.label}</span>
                    </div>
                    {item.badge && (
                      <span className="text-[9px] font-mono px-1 rounded bg-signal-teal/15 text-signal-teal">
                        {item.badge}
                      </span>
                    )}
                  </NavLink>
                ))}
              </div>
            ))}
          </div>
        )}

        {/* Mobile Content */}
        <main className="flex-1 px-4 py-6">
          <Outlet />
        </main>

        <footer className="border-t border-base-600 bg-base-900 px-4 py-4 text-xs text-ink-700 flex flex-col gap-1 items-center text-center">
          <span>QuantumFlood AI — {currentAreaName} Corridor</span>
          <span className="font-mono text-[10px]">DISASTER INTELLIGENCE PLATFORM</span>
        </footer>
      </div>

      {/* Desktop Main Content */}
      <div className="hidden lg:flex flex-col flex-1 min-w-0 min-h-screen overflow-y-auto">
        <main className="flex-1 p-8 max-w-[1600px] w-full mx-auto">
          <Outlet />
        </main>
        <footer className="border-t border-base-600 bg-base-900/60 px-8 py-4 flex items-center justify-between text-xs text-ink-700">
          <span>QuantumFlood AI — Disaster Intelligence Pipeline · {currentAreaName} Corridor</span>
          <span className="font-mono text-[11px] text-ink-500">FASTAPI + REACT DASHBOARD</span>
        </footer>
      </div>
    </div>
  )
}

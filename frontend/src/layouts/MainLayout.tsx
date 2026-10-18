import { useState, useEffect } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { api } from '../services/api'

interface NavItem {
  to: string
  label: string
  desc: string
  end?: boolean
  icon: JSX.Element
  badge?: string
}

const PRIMARY_SECTIONS: NavItem[] = [
  {
    to: '/',
    label: 'Home',
    desc: 'Overview & Area Search',
    end: true,
    icon: (
      <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
      </svg>
    ),
  },
  {
    to: '/sensor-placement',
    label: 'Smart Sensor Placement',
    desc: 'QAOA vs Greedy Optimizer',
    badge: 'QAOA',
    icon: (
      <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
      </svg>
    ),
  },
  {
    to: '/historical-intelligence',
    label: 'Historical Flood Intelligence',
    desc: 'Hydrology, Gauges & Flood Events',
    icon: (
      <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    to: '/shelters',
    label: 'Safe Shelters & Requests',
    desc: 'Candidate Shelters & Needs',
    icon: (
      <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
      </svg>
    ),
  },
  {
    to: '/resource-planning',
    label: 'Resource Planning & Fulfillment',
    desc: 'Inventory & Dispatch Tracking',
    icon: (
      <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
      </svg>
    ),
  },
]

export default function MainLayout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [currentAreaName, setCurrentAreaName] = useState('Vijayawada Benchmark')
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
        <nav className="flex-1 px-3 py-3 space-y-1.5 overflow-y-auto">
          <div className="px-2.5 pb-2 text-[10px] font-mono uppercase tracking-wider text-ink-500 font-semibold flex items-center justify-between">
            <span>Primary Workflow</span>
            <span className="text-[9px] text-ink-600">5 Modules</span>
          </div>

          {PRIMARY_SECTIONS.map((item, idx) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `group flex items-start gap-2.5 px-3 py-2.5 rounded-lg text-xs transition-all duration-150 relative ${
                  isActive
                    ? 'bg-base-700 text-ink-100 shadow-md border-l-2 border-signal-teal'
                    : 'text-ink-400 hover:text-ink-100 hover:bg-base-800/70'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <div className={`mt-0.5 ${isActive ? 'text-signal-teal' : 'text-ink-500 group-hover:text-ink-300'}`}>
                    {item.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-1">
                      <span className={`font-medium truncate ${isActive ? 'text-signal-teal font-semibold' : 'text-ink-200'}`}>
                        {item.label}
                      </span>
                      {item.badge && (
                        <span className="text-[9px] font-mono font-bold px-1.5 py-0.2 rounded bg-signal-teal/15 text-signal-teal border border-signal-teal/30 shrink-0">
                          {item.badge}
                        </span>
                      )}
                    </div>
                    <div className="text-[10px] text-ink-500 truncate group-hover:text-ink-400 mt-0.5">
                      {item.desc}
                    </div>
                  </div>
                  <span className="text-[9px] font-mono text-ink-600 ml-1 mt-0.5">
                    0{idx + 1}
                  </span>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-3 border-t border-base-600/60 bg-base-950/40">
          <div className="flex items-center justify-between text-xs text-ink-500">
            <span className="flex items-center gap-1.5 min-w-0 pr-1">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shrink-0" />
              <span className="truncate">{currentAreaName}</span>
            </span>
            <button
              onClick={handleQuickReset}
              className="text-[10px] font-mono text-ink-600 hover:text-signal-teal transition-colors underline shrink-0"
              title="Reset study area to Vijayawada Benchmark"
            >
              Reset
            </button>
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
          <div className="bg-base-900 border-b border-base-600 px-4 py-3 space-y-2 z-40 max-h-[80vh] overflow-y-auto">
            <div className="text-[10px] font-mono uppercase tracking-wider text-ink-500 font-semibold px-1 pb-1">
              Primary Workflow (5 Modules)
            </div>
            {PRIMARY_SECTIONS.map((item, idx) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) =>
                  `flex items-center justify-between px-3 py-2.5 rounded text-xs font-medium ${
                    isActive
                      ? 'bg-base-700 text-signal-teal font-semibold'
                      : 'text-ink-400 hover:text-ink-100 hover:bg-base-800'
                  }`
                }
              >
                <div className="flex items-center gap-2.5">
                  {item.icon}
                  <div>
                    <div className="font-medium">{item.label}</div>
                    <div className="text-[10px] text-ink-500">{item.desc}</div>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  {item.badge && (
                    <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-signal-teal/15 text-signal-teal border border-signal-teal/30">
                      {item.badge}
                    </span>
                  )}
                  <span className="text-[9px] font-mono text-ink-600">0{idx + 1}</span>
                </div>
              </NavLink>
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

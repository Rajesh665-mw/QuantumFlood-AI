/**
 * Shared dark-themed Recharts configuration for consistent chart styling
 * across the QuantumFlood AI dashboard.
 */

/** Dark-themed tooltip style matching the app design system */
export const DARK_TOOLTIP_STYLE = {
  contentStyle: {
    backgroundColor: 'rgba(15, 23, 32, 0.95)',
    border: '1px solid rgba(41, 52, 63, 0.8)',
    borderRadius: '8px',
    padding: '10px 14px',
    backdropFilter: 'blur(8px)',
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
  },
  labelStyle: {
    color: '#B7C1CE',
    fontFamily: '"IBM Plex Mono", monospace',
    fontSize: '11px',
    fontWeight: 500,
    marginBottom: '4px',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
  },
  itemStyle: {
    color: '#E8ECF1',
    fontFamily: '"Inter", sans-serif',
    fontSize: '12px',
    padding: '2px 0',
  },
  cursor: {
    stroke: 'rgba(45, 212, 191, 0.3)',
    strokeWidth: 1,
    strokeDasharray: '4 4',
  },
}

/** Dark-themed axis tick style */
export const DARK_AXIS_TICK = {
  fontSize: 10,
  fontFamily: '"IBM Plex Mono", monospace',
  fill: '#5A6779',
}

/** Grid line style for dark backgrounds */
export const DARK_GRID_STYLE = {
  strokeDasharray: '3 6',
  stroke: 'rgba(41, 52, 63, 0.6)',
}

/** Common chart color palette */
export const CHART_COLORS = {
  primary: '#2DD4BF',
  primaryDim: 'rgba(45, 212, 191, 0.3)',
  secondary: '#22D3EE',
  secondaryDim: 'rgba(34, 211, 238, 0.3)',
  warning: '#F59E0B',
  warningDim: 'rgba(245, 158, 11, 0.3)',
  danger: '#EF4444',
  dangerDim: 'rgba(239, 68, 68, 0.3)',
  muted: '#8A96A8',
  mutedDim: 'rgba(138, 150, 168, 0.2)',
}

/** Reference line style for thresholds / danger levels */
export const DARK_REFERENCE_LINE = {
  stroke: 'rgba(210, 80, 74, 0.6)',
  strokeWidth: 1.5,
  strokeDasharray: '6 4',
  label: {
    fill: '#D2504A',
    fontSize: 10,
    fontFamily: '"IBM Plex Mono", monospace',
  },
}

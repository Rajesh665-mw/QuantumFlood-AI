/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        base: {
          950: '#0B121A',
          900: '#0F1720',
          800: '#161F2C',
          700: '#1C2634',
          600: '#29343F',
          500: '#3B4857',
        },
        ink: {
          100: '#E8ECF1',
          300: '#B7C1CE',
          500: '#8A96A8',
          700: '#5A6779',
        },
        signal: {
          teal: '#2DD4BF',
          tealDim: '#1F8F82',
        },
        risk: {
          low: '#4E9A6B',
          lowBg: '#16261D',
          moderate: '#C99A3B',
          moderateBg: '#2A2313',
          high: '#D9803E',
          highBg: '#2B2013',
          critical: '#D2504A',
          criticalBg: '#2E1817',
        },
      },
      fontFamily: {
        display: ['"IBM Plex Sans"', 'sans-serif'],
        body: ['"Inter"', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      borderRadius: {
        sm: '3px',
        DEFAULT: '4px',
        md: '6px',
      },
    },
  },
  plugins: [],
}

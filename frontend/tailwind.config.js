/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './index.tsx',
    './App.tsx',
    './components/**/*.{js,ts,jsx,tsx}',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        slate: {
          850: '#1e293b',
          950: '#020617',
        },
        // Pasek informacyjny (10.2026) — te same wartości co `--tv-*` w index.html
        tv: {
          ink: 'var(--tv-ink)',
          panel: 'var(--tv-panel)',
          panel2: 'var(--tv-panel-2)',
          seam: 'var(--tv-seam)',
          paper: 'var(--tv-paper)',
          muted: 'var(--tv-muted)',
          blue: 'var(--tv-blue)',
          bluesoft: 'var(--tv-blue-soft)',
          red: 'var(--tv-red)',
          yellow: 'var(--tv-yellow)',
          green: 'var(--tv-green)',
        },
      },
      fontFamily: {
        sans: ['Archivo', 'system-ui', 'sans-serif'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'soundbar': 'soundbar 0.8s ease-in-out infinite',
      },
      keyframes: {
        soundbar: {
          '0%, 100%': { height: '20%' },
          '50%': { height: '100%' },
        },
      },
    },
  },
  plugins: [],
}

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: {
          DEFAULT: '#f7f5f0',
          canvas: '#f7f5f0',
          sheet: '#ffffff',
          subtle: '#f1ece3',
          muted: '#e7e1d5',
          border: '#ded7cb',
          darkborder: '#191715',
        },
        ink: {
          DEFAULT: '#191715',
          light: '#2e2b27',
          muted: '#686259',
          faint: '#968f84',
        },
        rust: {
          DEFAULT: '#9c3b1b',
          hover: '#b4421e',
          tint: '#faf2ee',
          border: '#e8c4b8',
        },
        badge: {
          amber: '#92400e',
          amberBg: '#fef3c7',
          amberBorder: '#fcd34d',
          green: '#166534',
          greenBg: '#dcfce7',
          greenBorder: '#86efac',
          slate: '#334155',
          slateBg: '#f1f5f9',
          slateBorder: '#cbd5e1',
          plum: '#581c87',
          plumBg: '#f3e8ff',
          plumBorder: '#d8b4fe',
        }
      },
      fontFamily: {
        serif: ['Newsreader', 'Sitka Text', 'Palatino Linotype', 'Book Antiqua', 'Georgia', 'serif'],
        sans: ['"Plus Jakarta Sans"', '"Source Sans 3"', '"Segoe UI"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"SF Mono"', 'Consolas', 'monospace'],
      },
      borderRadius: {
        none: '0px',
        sm: '2px',
        DEFAULT: '2px',
        md: '3px',
      },
      boxShadow: {
        'paper-sm': '0 1px 2px rgba(25, 23, 21, 0.05)',
        'paper': '0 1px 3px rgba(25, 23, 21, 0.08), 0 1px 2px rgba(25, 23, 21, 0.04)',
        'paper-raised': '0 4px 12px -2px rgba(25, 23, 21, 0.08)',
      },
    },
  },
  plugins: [],
}

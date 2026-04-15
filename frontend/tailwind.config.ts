import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: '#0F1F3D',
          50: '#E8EDF5',
          100: '#C5D1E8',
          900: '#0A1628',
        },
        accent: {
          DEFAULT: '#2563EB',
          50: '#EFF6FF',
          600: '#1D4ED8',
        },
      },
      fontFamily: {
        display: ['Rajdhani', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
} satisfies Config

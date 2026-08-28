/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eef4ff',
          100: '#d9e6ff',
          200: '#b7ceff',
          300: '#8caeff',
          400: '#5f87ff',
          500: '#3a63f7',
          600: '#2748db',
          700: '#2038ad',
          800: '#1f318a',
          900: '#1e2d6e',
        },
      },
    },
  },
  plugins: [],
}

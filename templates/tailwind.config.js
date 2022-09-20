const defaultTheme = require('tailwindcss/defaultTheme')
const colors = require('tailwindcss/colors')

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{html,js}'],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#E25822',
          50: '#F7D3C4',
          100: '#F5C5B2',
          200: '#F0AA8E',
          300: '#EB8F6A',
          400: '#E77346',
          500: '#E25822',
          600: '#B44418',
          700: '#833111',
          800: '#511E0B',
          900: '#1F0C04',
        },
        primary: colors.zinc,
      },
      maxWidth: {
        '8xl': '90rem',
      },
      fontFamily: {
        serif: ['Montserrat', ...defaultTheme.fontFamily.serif],
        sans: ['"Fira Sans"', ...defaultTheme.fontFamily.sans],
        mono: ['"Fira Mono"', ...defaultTheme.fontFamily.mono],
      },
    },
  },
  plugins: [],
}

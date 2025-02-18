/** @type {import('postcss-load-config').Config} */
const config = {
  plugins: {
    'postcss-import': {},
    autoprefixer: {},
    'tailwindcss/nesting': {},
    tailwindcss: {},
    cssnano: {},
  },
}

export default config

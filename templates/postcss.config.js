/** @type {import('postcss-load-config').Config} */
const config = {
  plugins: {
    '@tailwindcss/postcss': { optimize: { minify: true } },
  },
}

export default config

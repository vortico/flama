/** @type {import('prettier').Config} */
const config = {
  singleQuote: true,
  semi: false,
  printWidth: 120,
  plugins: ['@ianvs/prettier-plugin-sort-imports', 'prettier-plugin-tailwindcss'],
  importOrder: ['^react$', '', '<THIRD_PARTY_MODULES>', '', '^@/(.*)$', '', '^[.]'],
  overrides: [
    {
      files: '*.html.*',
      options: {
        parser: 'html',
      },
    },
  ],
}

export default config

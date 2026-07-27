/** @type {import("@babel/core").TransformOptions} */
const config = {
  presets: [
    [
      '@babel/preset-env',
      {
        targets: '> 0.25%, not dead',
      },
    ],
    [
      '@babel/preset-react',
      {
        runtime: 'automatic',
        development: process.env.NODE_ENV === 'development',
      },
    ],
    '@babel/preset-typescript',
  ],
  plugins: [
    ['babel-plugin-polyfill-corejs3', { method: 'usage-global', version: '3.49', proposals: true }],
    ['@babel/plugin-transform-runtime', { moduleName: '@babel/runtime' }],
    '@babel/plugin-transform-spread',
  ],
}

export default config

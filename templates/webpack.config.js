import path from 'node:path'

import HtmlBundlerPlugin from 'html-bundler-webpack-plugin'

const ROOT_PATH = path.resolve(import.meta.dirname)
const SRC_PATH = path.resolve(ROOT_PATH, 'src')
const OUTPUT_PATH = path.resolve(ROOT_PATH, '..', 'flama', 'templates')
const PAGES_PATH = path.resolve(SRC_PATH, 'pages')
const ENVIRONMENT = process.env.NODE_ENV !== undefined ? process.env.NODE_ENV : 'production'

/** @type {import('webpack-cli').ConfigOptions} */
const config = {
  mode: 'production',
  module: {
    rules: [
      {
        test: /\.(js|jsx|ts|tsx)$/,
        include: SRC_PATH,
        use: ['babel-loader'],
      },
      {
        test: /\.css$/i,
        use: ['css-loader', 'postcss-loader'],
      },
      {
        test: /\.(png|svg|jpg|jpeg|gif)$/i,
        include: SRC_PATH,
        type: 'asset/resource',
      },
      {
        test: /\.(woff|woff2|eot|ttf|otf)$/i,
        include: SRC_PATH,
        type: 'asset/resource',
      },
    ],
  },
  resolve: {
    alias: { '@': SRC_PATH },
    extensions: ['.ts', '.tsx', '.js', '.jsx'],
  },
  output: {
    path: OUTPUT_PATH,
    clean: true,
    chunkFormat: false,
  },
  plugins: [
    new HtmlBundlerPlugin({
      entry: PAGES_PATH,
      js: { inline: true },
      css: { inline: true },
      minify: 'auto',
      hotUpdate: ENVIRONMENT === 'development',
    }),
  ],
  watchOptions: {
    aggregateTimeout: 200,
    poll: 1000,
    ignored: /node_modules/,
  },
  // Enable live reload
  devServer: {
    hot: ENVIRONMENT === 'development',
    watchFiles: {
      paths: ['src/**/*.*'],
      options: {
        usePolling: true,
      },
    },
  },
  performance: false, // Disable warning max size
  devtool: ENVIRONMENT === 'development' ? 'inline-cheap-source-map' : undefined,
  optimization: {
    splitChunks: false,
  },
}

export default config

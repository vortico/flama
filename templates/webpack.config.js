const path = require('path')
const fg = require('fast-glob')
const HtmlWebpackPlugin = require('html-webpack-plugin')
const InlineChunkHtmlPlugin = require('react-dev-utils/InlineChunkHtmlPlugin')
const HTMLInlineCSSWebpackPlugin = require('html-inline-css-webpack-plugin').default
const RemovePlugin = require('remove-files-webpack-plugin')

const files = fg.sync('src/js/**/*.js?(x)', { onlyFiles: true, unique: true, absolute: false })
  .map((x) => ({
    name: x.replace('src/js/', '').replace(/\.jsx?/, ''),
    path: path.resolve(__dirname, x)
  }))

const output = path.resolve(__dirname, '..', 'flama', 'templates')

module.exports = {
  mode: process.env.NODE_ENV !== undefined ? process.env.NODE_ENV : 'production',
  entry: files.reduce((a, { name, path }) => ({ ...a, [name]: { import: path, filename: `${name}.runtime.js` } }), {}),
  module: {
    rules: [
      {
        test: /\.(js|jsx)$/,
        include: path.resolve(__dirname, 'src'),
        use: ['babel-loader'],
      },
      {
        test: /\.css$/i,
        include: path.resolve(__dirname, 'src'),
        use: ['style-loader', 'css-loader', 'postcss-loader'],
      },
    ],
  },
  resolve: {
    extensions: ['.js', '.jsx'],
  },
  output: {
    path: output,
    clean: true
  },
  plugins: [].concat(files.map(({ name }) => {
    return new HtmlWebpackPlugin({
      template: path.resolve(__dirname, 'src', 'html', 'main.html'),
      filename: `${name}.html`,
      chunks: [`${name}`],
      inject: 'body',
      scriptLoading: 'module',
      publicPath: ''
    })
  })).concat([
    new InlineChunkHtmlPlugin(HtmlWebpackPlugin, [/.*/]),
    new HTMLInlineCSSWebpackPlugin(),
    new RemovePlugin({
      after: {
        root: path.resolve(__dirname, '..'),
        test: [
          {
            folder: output,
            method: (x) => { return new RegExp(/.*\.runtime.js/).test(x) },
            recursive: true
          }
        ]
      }
    }),
  ]),
  watch: process.env.NODE_ENV === "development",
  watchOptions: {
    ignored: /node_modules/,
  },
}
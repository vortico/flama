const path = require('path');
const fg = require('fast-glob');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const InlineChunkHtmlPlugin = require('react-dev-utils/InlineChunkHtmlPlugin');
const HTMLInlineCSSWebpackPlugin =
  require('html-inline-css-webpack-plugin').default;
const RemovePlugin = require('remove-files-webpack-plugin');

const files = fg
  .sync('src/pages/**/*.ts?(x)', {
    onlyFiles: true,
    unique: true,
    absolute: false,
  })
  .map((x) => ({
    name: x.replace('src/pages/', '').replace(/\.tsx?/, ''),
    path: path.resolve(__dirname, x),
  }));

const output = path.resolve(__dirname, '..', 'flama', 'templates');

module.exports = {
  mode:
    process.env.NODE_ENV !== undefined ? process.env.NODE_ENV : 'production',
  entry: files.reduce(
    (a, { name, path }) => ({
      ...a,
      [name]: { import: path, filename: `${name}.runtime.js` },
    }),
    {}
  ),
  module: {
    rules: [
      {
        test: /\.(js|jsx|ts|tsx)$/,
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
    alias: { '@': path.resolve(__dirname, 'src') },
    extensions: ['.ts', '.tsx', '.js', '.jsx'],
  },
  output: {
    path: output,
    clean: true,
  },
  plugins: []
    .concat(
      files.map(({ name }) => {
        return new HtmlWebpackPlugin({
          template: path.resolve(__dirname, 'src', 'html', 'main.html'),
          filename: `${name}.html`,
          chunks: [`${name}`],
          inject: 'body',
          scriptLoading: 'module',
          publicPath: '',
          cache: false,
        });
      })
    )
    .concat([
      new InlineChunkHtmlPlugin(HtmlWebpackPlugin, [/.*/]),
      new HTMLInlineCSSWebpackPlugin(),
      new RemovePlugin({
        after: {
          root: path.resolve(__dirname, '..'),
          test: [
            {
              folder: output,
              method: (x) => {
                return new RegExp(/.*\.runtime.js/).test(x);
              },
              recursive: true,
            },
          ],
        },
      }),
    ]),
  watchOptions: {
    ignored: /node_modules/,
  },
};

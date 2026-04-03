import path from 'node:path'

import js from '@eslint/js'
import prettierConfig from 'eslint-config-prettier'
import importPlugin from 'eslint-plugin-import'
import reactPlugin from 'eslint-plugin-react'
import reactHooksPlugin from 'eslint-plugin-react-hooks'
import globals from 'globals'
import ts from 'typescript-eslint'

/** @type {import("eslint").Linter.Config[]} */
export default [
  {
    ignores: ['.*.js', '.*.ts', 'node_modules/', 'dist/', '.next/', 'public/', 'out/'],
  },
  {
    languageOptions: {
      globals: { ...globals.browser, ...globals.node, ...globals.serviceworker },
    },
  },
  prettierConfig,
  js.configs.recommended,
  ...ts.configs.strict,
  ...ts.configs.stylistic,
  {
    files: ['**/*.js', '**/*.jsx', '**/*.ts', '**/*.tsx'],
    ...importPlugin.flatConfigs.recommended,
    rules: {
      // turn on errors for missing imports
      'import/no-unresolved': 'error',
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^React$' }],
    },
    settings: {
      'import/parsers': {
        '@typescript-eslint/parser': ['.ts', '.tsx'],
      },
      'import/resolver': {
        typescript: {
          project: path.resolve(process.cwd(), 'tsconfig.json'),
        },
      },
    },
  },
  {
    files: ['**/*.js', '**/*.jsx', '**/*.ts', '**/*.tsx'],
    ...reactPlugin.configs.flat.recommended,
    plugins: {
      ...reactPlugin.configs.flat.recommended.plugins,
      react: reactPlugin,
      'react-hooks': reactHooksPlugin,
    },
    rules: {
      ...reactPlugin.configs.flat.recommended.rules,
      ...reactPlugin.configs['jsx-runtime'].rules,
      ...reactHooksPlugin.configs.recommended.rules,
    },
  },
]

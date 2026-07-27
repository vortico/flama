// TypeScript 7 rejects side-effect imports of modules it has no declaration for (TS2882). Stylesheets
// are handled entirely by webpack's css-loader and contribute no bindings, so declaring them empty is
// enough to satisfy the compiler without pretending they export anything.
declare module '*.css'

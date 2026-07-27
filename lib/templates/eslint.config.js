import { react } from '@vortico/config/eslint'

export default [...react, { ignores: ['*.config.js', '*.config.ts', '.husky/'] }]

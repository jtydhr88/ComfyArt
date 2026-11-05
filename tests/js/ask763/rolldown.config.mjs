import path from 'node:path'
const here = path.dirname(new URL(import.meta.url).pathname)
const stubs = { i18n: path.join(here, '../i18n_stub.ts') }
export default {
  input: path.join(here, 'main.tsx'),
  platform: 'browser',
  moduleTypes: { '.svg': 'dataurl', '.png': 'dataurl', '.webp': 'dataurl' },
  transform: { define: { 'process.env.NODE_ENV': '"development"' } },
  output: { format: 'iife', file: process.env.OUT },
  plugins: [{ name: 'stubs', resolveId(id) {
    if (id.startsWith('.') && path.basename(id) === 'i18n') return stubs.i18n
    return null
  } }],
}

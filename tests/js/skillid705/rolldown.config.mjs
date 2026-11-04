// #463: bundles the real src/skills.ts with an in-memory comfy store; fflate stays real.
import path from 'node:path'
const here = path.dirname(new URL(import.meta.url).pathname)
const stubs = { comfy: 'comfy_stub.ts', i18n: '../i18n_stub.ts', tldraw: 'tldraw_stub.ts', customMarkers: 'tldraw_stub.ts', id: 'tldraw_stub.ts' }
export default {
  input: path.join(here, 'main.ts'),
  platform: 'node',
  output: { format: 'esm', file: process.env.OUT },
  plugins: [{ name: 'skillid705-stubs', resolveId(id, importer) {
    if (!importer) return null
    const base = id.startsWith('.') ? path.basename(id).replace(/\.tsx?$/, '') : id
    if (stubs[base] && !importer.endsWith(stubs[base].replace('../', ''))) return path.join(here, stubs[base])
    return null
  } }],
}

import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'

const stylesPath = fileURLToPath(new URL('../src/styles/globals.css', import.meta.url))
const styles = readFileSync(stylesPath, 'utf8')
const apiPath = fileURLToPath(new URL('../src/utils/api.js', import.meta.url))
const apiSource = readFileSync(apiPath, 'utf8')
const contrastScriptPath = fileURLToPath(new URL('../scripts/contrast-check.mjs', import.meta.url))

test('photo-composited screen text combinations meet WCAG AA contrast', () => {
  const output = execFileSync(process.execPath, [contrastScriptPath], { encoding: 'utf8' })

  assert.match(output, /Workspace \| \*\*Screen minimum\*\*[^\n]*4\.65:1[^\n]*PASS/)
  assert.match(output, /Report \| \*\*Screen minimum\*\*[^\n]*4\.50:1[^\n]*PASS/)
  assert.match(output, /Flashcards \| \*\*Screen minimum\*\*[^\n]*5\.32:1[^\n]*PASS/)
  assert.match(output, /Knowledge \| \*\*Screen minimum\*\*[^\n]*4\.76:1[^\n]*PASS/)
  assert.doesNotMatch(output, /\| FAIL \|/)
})

test('dark glass surfaces reveal photos and contain no left accent bars', () => {
  assert.match(styles, /--page:\s*#0B1426;/)
  assert.match(styles, /--surface-glass:\s*rgba\(11,\s*20,\s*38,\s*0\.492\);/)
  assert.match(styles, /--text:\s*#F1F5F9;/)
  assert.match(styles, /--text-soft:\s*#F1F5F9;/)
  assert.match(styles, /body\s*\{[^}]*background:\s*var\(--page\)/s)
  assert.match(styles, /\.scene-image-stack\s*\{[^}]*opacity:\s*0\.35;/s)
  assert.match(styles, /--veil-start:\s*rgba\(11,\s*20,\s*38,\s*0\.20\);/)
  assert.match(styles, /--veil-end:\s*rgba\(11,\s*20,\s*38,\s*0\.35\);/)
  assert.doesNotMatch(styles, /border-left|borderLeft|border-l-|nav-active-bar|summary-point::before/)
})

test('keyboard focus rings use the specified coral outline and offset', () => {
  assert.match(styles, /:focus-visible\s*\{\s*outline:\s*2px solid var\(--coral\)\s*!important;\s*outline-offset:\s*2px\s*!important;/)
})

test('reduced motion disables the drifting scene blobs', () => {
  assert.match(styles, /@media\s*\(prefers-reduced-motion:\s*reduce\)/)
  assert.match(styles, /\.scene-blob\s*\{[^}]*animation:\s*none\s*!important;/s)
})

test('API configuration does not hardcode a localhost backend', () => {
  assert.match(apiSource, /VITE_API_URL/)
  assert.match(apiSource, /:\s*'\/api'/)
  assert.doesNotMatch(apiSource, /localhost|127\.0\.0\.1/)
})

test('health checks validate the Flask health response and use a bounded timeout', () => {
  assert.match(apiSource, /api\.get\('\/health',\s*\{\s*timeout:\s*HEALTH_CHECK_TIMEOUT_MS\s*\}\)/)
  assert.match(apiSource, /HEALTH_CHECK_TIMEOUT_MS\s*=\s*5000/)
  assert.match(apiSource, /response\?\.data\?\.status\s*===\s*'ok'/)
  assert.match(apiSource, /throw new Error\('Backend health check returned an unexpected response'\)/)
})

test('sidebar only reports online after the health check succeeds', () => {
  const sidebarPath = fileURLToPath(new URL('../src/components/layout/Sidebar.jsx', import.meta.url))
  const sidebarSource = readFileSync(sidebarPath, 'utf8')

  assert.match(sidebarSource, /await checkHealth\(\)[\s\S]*?setBackendOnline\(true\)/)
  assert.match(sidebarSource, /catch\s*\{[\s\S]*?setBackendOnline\(false\)/)
  assert.match(sidebarSource, /'Backend online'/)
  assert.match(sidebarSource, /'Backend offline'/)
  assert.match(sidebarSource, /'Checking backend'/)
})

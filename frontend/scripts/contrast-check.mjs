import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const cssPath = path.join(root, 'src/styles/globals.css')
const css = fs.readFileSync(cssPath, 'utf8')
const sourceFiles = []

function collectSources(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const fullPath = path.join(directory, entry.name)
    if (entry.isDirectory()) collectSources(fullPath)
    else if (/\.jsx?$/.test(entry.name)) sourceFiles.push(fs.readFileSync(fullPath, 'utf8'))
  }
}

collectSources(path.join(root, 'src'))

const tokens = new Map([...css.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)].map(([, name, value]) => [name, value.trim()]))
const tokenReferences = new Set(sourceFiles.flatMap((source) => [...source.matchAll(/var\((--[\w-]+)/g)].map((match) => match[1])))
const componentHexes = sourceFiles.flatMap((source) => [...source.matchAll(/#[\da-f]{3,8}\b/gi)].map((match) => match[0]))

function resolveColor(value, seen = new Set()) {
  const reference = value.match(/^var\((--[\w-]+)\)$/)
  if (reference) {
    const name = reference[1]
    if (seen.has(name) || !tokens.has(name)) throw new Error(`Unresolved color token: ${name}`)
    seen.add(name)
    return resolveColor(tokens.get(name), seen)
  }

  const hex = value.match(/^#([\da-f]{3}|[\da-f]{6})$/i)
  if (hex) {
    const digits = hex[1].length === 3 ? [...hex[1]].map((digit) => digit + digit).join('') : hex[1]
    return [...digits.match(/../g)].map((channel) => Number.parseInt(channel, 16)).concat(1)
  }

  const rgba = value.match(/^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,?\s*([\d.]*)\s*\)$/i)
  if (rgba) return [Number(rgba[1]), Number(rgba[2]), Number(rgba[3]), rgba[4] ? Number(rgba[4]) : 1]
  throw new Error(`Unsupported color value: ${value}`)
}

function composite(foreground, background) {
  const alpha = foreground[3]
  return [0, 1, 2].map((index) => foreground[index] * alpha + background[index] * (1 - alpha)).concat(1)
}

function luminance(color) {
  const channels = color.slice(0, 3).map((value) => {
    const channel = value / 255
    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
}

function contrast(foreground, background) {
  const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a)
  return (values[0] + 0.05) / (values[1] + 0.05)
}

function tint(token, base) {
  return composite(resolveColor(tokens.get(token)), base)
}

// Browser-canvas samples from each bundled photo after image opacity and veil,
// before the glass surface is composited. Each entry is an 80x80 sample's luminance extrema.
const photoSamples = [
  ['Study desk', [4, 6, 12], [170, 173, 179]],
  ['Library stacks', [20, 27, 39], [176, 179, 185]],
  ['Lecture chalk', [11, 15, 23], [137, 137, 143]],
  ['Annotated paper', [57, 61, 70], [139, 143, 152]],
  ['Rain window', [31, 10, 18], [174, 178, 183]],
  ['Neural light', [6, 8, 14], [135, 143, 115]],
  ['Mind map', [40, 43, 51], [157, 160, 166]],
  ['Exam hall', [5, 8, 16], [177, 180, 186]],
]
const glass = resolveColor(tokens.get('--surface-glass'))
const panelSamples = photoSamples.flatMap(([scene, darkest, lightest]) => [
  { scene, area: 'darkest', color: composite(glass, darkest) },
  { scene, area: 'lightest', color: composite(glass, lightest) },
])

function minimumPair(label, foregroundToken, backgrounds) {
  const foreground = resolveColor(tokens.get(foregroundToken))
  const minimum = backgrounds.reduce((result, sample) => {
    const ratio = contrast(foreground, sample.color)
    return ratio < result.ratio ? { ratio, sample } : result
  }, { ratio: Number.POSITIVE_INFINITY, sample: null })
  return { label, foregroundToken, ratio: minimum.ratio, sample: minimum.sample }
}

function tintedSamples(token) {
  return panelSamples.map((sample) => ({
    ...sample,
    color: tint(token, sample.color),
  }))
}

const screenPairs = {
  Workspace: [
    minimumPair('Primary text / glass surface', '--text', panelSamples),
    minimumPair('Secondary text / glass surface', '--text-soft', panelSamples),
    minimumPair('Chip text / saffron tint', '--text', tintedSamples('--warn-14')),
    minimumPair('Chip text / blue tint', '--text', tintedSamples('--info-14')),
    minimumPair('Button label / cyan', '--button-text', panelSamples.map((sample) => ({ ...sample, color: resolveColor(tokens.get('--accent')) }))),
  ],
  Report: [
    minimumPair('Primary text / glass surface', '--text', panelSamples),
    minimumPair('Secondary text / glass surface', '--text-soft', panelSamples),
    ...['--accent-14', '--accent-2-14', '--info-14', '--success-14', '--warn-14', '--danger-14']
      .map((token) => minimumPair(`Chip text / ${token.slice(2)} tint`, '--text', tintedSamples(token))),
  ],
  Flashcards: [
    minimumPair('Card text / glass surface', '--text', panelSamples),
    minimumPair('Secondary text / glass surface', '--text-soft', panelSamples),
    minimumPair('Label text / glass pill', '--text', panelSamples),
  ],
  Knowledge: [
    minimumPair('Question text / glass surface', '--text', panelSamples),
    minimumPair('Secondary text / glass surface', '--text-soft', panelSamples),
    minimumPair('Correct option text / success fill', '--text', tintedSamples('--success-10')),
    minimumPair('Wrong option text / danger fill', '--text', tintedSamples('--danger-12')),
  ],
}

console.log(`Component token references: ${[...tokenReferences].sort().join(', ')}`)
console.log(`Un-tokenized component hex colors: ${componentHexes.length ? componentHexes.join(', ') : 'none'}`)
console.log('Photo samples: 8 bundled scenes, darkest/lightest sampled pixels after image, veil, and glass-surface compositing.')
console.log('| Screen | Text/background pair | Foreground | Worst sampled background | Contrast | Result |')
console.log('| --- | --- | --- | --- | ---: | --- |')
for (const [screen, pairs] of Object.entries(screenPairs)) {
  for (const row of pairs) {
    const { scene, area, color } = row.sample
    const background = color.slice(0, 3).map((channel) => Math.round(channel).toString(16).padStart(2, '0')).join('')
    console.log(`| ${screen} | ${row.label} | ${row.foregroundToken} | ${scene} ${area} (#${background}) | ${row.ratio.toFixed(2)}:1 | ${row.ratio >= 4.5 ? 'PASS' : 'FAIL'} |`)
  }
  const lowest = pairs.reduce((minimum, row) => row.ratio < minimum.ratio ? row : minimum)
  console.log(`| ${screen} | **Screen minimum** | ${lowest.foregroundToken} | ${lowest.sample.scene} ${lowest.sample.area} | **${lowest.ratio.toFixed(2)}:1** | ${lowest.ratio >= 4.5 ? 'PASS' : 'FAIL'} |`)
}

const allRows = Object.values(screenPairs).flat()
const lowest = allRows.reduce((minimum, row) => row.ratio < minimum.ratio ? row : minimum)
console.log(`Overall minimum: ${lowest.label} at ${lowest.ratio.toFixed(2)}:1`)
if (allRows.some((row) => row.ratio < 4.5)) process.exitCode = 1
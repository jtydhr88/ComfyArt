import { imageUrl } from './comfy'

export interface Adjust {
  exposure: number; contrast: number; highlights: number; shadows: number; whites: number; blacks: number
  saturation: number; vibrance: number; temperature: number; tint: number
  sharpen: number; clarity: number; grain: number
  vignette: number; bloom: number; glamour: number
}

export const NO_ADJUST: Adjust = {
  exposure: 0, contrast: 0, highlights: 0, shadows: 0, whites: 0, blacks: 0,
  saturation: 0, vibrance: 0, temperature: 0, tint: 0,
  sharpen: 0, clarity: 0, grain: 0,
  vignette: 0, bloom: 0, glamour: 0,
}

const clamp = (v: number) => (v < 0 ? 0 : v > 255 ? 255 : v)

function blurred(src: HTMLCanvasElement, radius: number): Uint8ClampedArray {
  const c = document.createElement('canvas')
  c.width = src.width
  c.height = src.height
  const ctx = c.getContext('2d', { willReadFrequently: true })!
  ctx.filter = `blur(${radius}px)`
  ctx.drawImage(src, 0, 0)
  return ctx.getImageData(0, 0, c.width, c.height).data
}

function noise(i: number): number {
  const x = Math.sin(i * 12.9898) * 43758.5453
  return x - Math.floor(x) - 0.5
}

function applyAdjust(canvas: HTMLCanvasElement, a: Adjust) {
  const { width: w, height: h } = canvas
  const ctx = canvas.getContext('2d', { willReadFrequently: true })!
  const px = ctx.getImageData(0, 0, w, h)
  const data = px.data
  const side = Math.max(w, h)
  const fine = a.sharpen ? blurred(canvas, Math.max(1, side / 900)) : null
  const wide = a.clarity || a.bloom ? blurred(canvas, side / 60) : null
  const soft = a.glamour ? blurred(canvas, side / 200) : null
  const gain = 2 ** (a.exposure / 100)
  const contrast = 1 + a.contrast / 100
  const sat = 1 + a.saturation / 100
  const warm = a.temperature * 0.4
  const tint = a.tint * 0.4
  for (let i = 0, p = 0; i < data.length; i += 4, p++) {
    let r = data[i]
    let g = data[i + 1]
    let b = data[i + 2]
    if (fine) {
      const k = a.sharpen / 50
      r += (r - fine[i]) * k
      g += (g - fine[i + 1]) * k
      b += (b - fine[i + 2]) * k
    }
    if (wide && a.clarity) {
      const k = a.clarity / 150
      r += (r - wide[i]) * k
      g += (g - wide[i + 1]) * k
      b += (b - wide[i + 2]) * k
    }
    if (soft) {
      const k = a.glamour / 200
      r = r * (1 - k) + (255 - ((255 - r) * (255 - soft[i])) / 255) * k
      g = g * (1 - k) + (255 - ((255 - g) * (255 - soft[i + 1])) / 255) * k
      b = b * (1 - k) + (255 - ((255 - b) * (255 - soft[i + 2])) / 255) * k
    }
    if (wide && a.bloom) {
      const k = a.bloom / 100
      r += Math.max(0, wide[i] - 150) * k
      g += Math.max(0, wide[i + 1] - 150) * k
      b += Math.max(0, wide[i + 2] - 150) * k
    }
    r = (r * gain - 128) * contrast + 128
    g = (g * gain - 128) * contrast + 128
    b = (b * gain - 128) * contrast + 128
    let luma = 0.299 * r + 0.587 * g + 0.114 * b
    const t = Math.min(1, Math.max(0, luma / 255))
    const lift = (luma > 128 ? (a.highlights * (luma - 128)) / 256 : (a.shadows * (128 - luma)) / 256)
      + a.whites * 0.6 * t ** 3 + a.blacks * 0.6 * (1 - t) ** 3
    r += lift
    g += lift
    b += lift
    luma += lift
    const chroma = (Math.max(r, g, b) - Math.min(r, g, b)) / 255
    const s = sat + (a.vibrance / 100) * (1 - Math.min(1, chroma))
    r = luma + (r - luma) * s + warm
    g = luma + (g - luma) * s - tint
    b = luma + (b - luma) * s - warm
    if (a.vignette) {
      const x = (p % w) / w - 0.5
      const y = Math.floor(p / w) / h - 0.5
      const k = 1 - (a.vignette / 100) * Math.min(1, (x * x + y * y) * 2)
      r *= k
      g *= k
      b *= k
    }
    if (a.grain) {
      const n = noise(p) * a.grain * 0.8
      r += n
      g += n
      b += n
    }
    data[i] = clamp(r)
    data[i + 1] = clamp(g)
    data[i + 2] = clamp(b)
  }
  ctx.putImageData(px, 0, 0)
}

export function autoAdjust(img: HTMLImageElement): Partial<Adjust> {
  const c = document.createElement('canvas')
  const k = Math.min(1, 256 / Math.max(img.naturalWidth, img.naturalHeight))
  c.width = Math.max(1, Math.round(img.naturalWidth * k))
  c.height = Math.max(1, Math.round(img.naturalHeight * k))
  const ctx = c.getContext('2d', { willReadFrequently: true })!
  ctx.drawImage(img, 0, 0, c.width, c.height)
  const d = ctx.getImageData(0, 0, c.width, c.height).data
  const lumas: number[] = []
  let [sr, sb] = [0, 0]
  for (let i = 0; i < d.length; i += 4) {
    lumas.push(0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2])
    sr += d[i]
    sb += d[i + 2]
  }
  lumas.sort((x, y) => x - y)
  const at = (q: number) => lumas[Math.floor((lumas.length - 1) * q)]
  const [lo, mid, hi] = [at(0.01), at(0.5), at(0.99)]
  const n = lumas.length
  const round = (v: number) => Math.round(Math.max(-100, Math.min(100, v)))
  return {
    exposure: round((Math.log2(118 / Math.max(mid, 1))) * 60),
    contrast: round((200 / Math.max(hi - lo, 40) - 1) * 40),
    blacks: round(-lo * 1.2),
    whites: round((255 - hi) * 1.2),
    temperature: round(((sb - sr) / n) * 0.5),
    vibrance: 15,
  }
}

export function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error(`cannot load ${src}`))
    img.src = imageUrl(src)
  })
}

export function adjustedCanvas(img: HTMLImageElement, a: Adjust, maxSide = Infinity): HTMLCanvasElement {
  const k = Math.min(1, maxSide / Math.max(img.naturalWidth, img.naturalHeight))
  const c = document.createElement('canvas')
  c.width = Math.round(img.naturalWidth * k)
  c.height = Math.round(img.naturalHeight * k)
  c.getContext('2d', { willReadFrequently: true })!.drawImage(img, 0, 0, c.width, c.height)
  applyAdjust(c, a)
  return c
}

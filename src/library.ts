import { atom } from 'tldraw'

import { readUserJson, writeUserJson } from './comfy'
import { t } from './i18n'

export type LibraryKind = 'brand' | 'character' | 'product' | 'custom'
export interface LibraryItem { id: string; kind: LibraryKind; name: string; description: string; images: string[]; colors: string[]; fonts: string[]; roles?: string[]; logos?: string[]; isDefault?: boolean; fontFiles?: FontFile[]; cover?: string }
export interface FontFile { family: string; src: string }

export const COLOR_ROLES: Record<string, string> = { primary: t('library.primary'), secondary: t('library.secondary'), accent: t('library.accent'), background: t('library.background'), text: t('library.text') }

/** display name shared by the list card and the Assets detail title (#539 P1) */
/** #497: short default「未命名」/「Untitled」 (Assets list + embedded title); canvas KitEditor keeps kitEditor.untitled+kind */
export const kitDisplayName = (item: { name: string; kind: LibraryKind }) => item.name || t('projectHeader.untitled')
export const KIND_LABELS: Record<LibraryKind, string> = { brand: t('library.brandKit'), character: t('library.character'), product: t('library.product'), custom: t('common.custom') }

const FILE = 'comfyart/library.json'

export const libraryAtom = atom<LibraryItem[]>('library', [])

const loadedFonts = new Set<string>()

export function registerFonts(list: LibraryItem[]) {
  for (const f of list.flatMap((x) => x.fontFiles ?? [])) {
    if (loadedFonts.has(f.src)) continue
    loadedFonts.add(f.src)
    void new FontFace(f.family, `url("${f.src}")`).load().then((face) => document.fonts.add(face))
  }
}

export function brandFonts(): string[] {
  return [...new Set(libraryAtom.get().filter((x) => x.kind === 'brand').flatMap((x) => [...(x.fontFiles ?? []).map((f) => f.family), ...x.fonts]))]
}

export async function loadLibrary(): Promise<LibraryItem[]> {
  const list = await readUserJson<LibraryItem[]>(FILE, [])
  libraryAtom.set(list)
  registerFonts(list)
  return list
}

export async function saveLibrary(list: LibraryItem[]) {
  libraryAtom.set(list)
  registerFonts(list)
  await writeUserJson(FILE, list)
}

export function itemImages(item: LibraryItem): string[] {
  return [...(item.logos ?? []), ...item.images]
}

export function linkedKit(brandKit: unknown): LibraryItem | null {
  return libraryAtom.get().find((x) => x.id === brandKit) ?? null
}

export function defaultKitId(): string | null {
  return libraryAtom.get().find((x) => x.kind === 'brand' && x.isDefault)?.id ?? null
}

export function describeItem(item: LibraryItem): string {
  const parts = [`${KIND_LABELS[item.kind]} "${item.name}"`]
  if (item.description) parts.push(item.description)
  if (item.colors.length) parts.push(`colors: ${item.colors.map((c, i) => (item.roles?.[i] ? `${item.roles[i]} ${c}` : c)).join(', ')}`)
  if (item.logos?.length) parts.push(`${item.logos.length} logo image(s) attached first`)
  if (item.fonts.length) parts.push(`fonts: ${item.fonts.join(', ')}`)
  if (item.images.length) parts.push(`${item.images.length} reference image(s) attached`)
  return parts.join('; ')
}

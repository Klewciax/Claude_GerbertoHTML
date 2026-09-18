import Papa from 'papaparse'
import type { BoardSide, Placement } from '../types'

const DESIGNATOR_KEYS = ['designator', 'ref', 'refdes', 'ref des']
const X_KEYS = ['mid x', 'midx', 'x', 'pos x', 'posx', 'x (mm)', 'x(mm)']
const Y_KEYS = ['mid y', 'midy', 'y', 'pos y', 'posy', 'y (mm)', 'y(mm)']
const ROTATION_KEYS = ['rotation', 'rot']
const SIDE_KEYS = ['layer', 'side']

function normalizeKey(key: string): string {
  return key.trim().toLowerCase().replace(/[_.]/g, ' ').replace(/\s+/g, ' ')
}

function findField(row: Record<string, string>, candidates: string[]): string | undefined {
  const normalizedRow: Record<string, string> = {}
  for (const [k, v] of Object.entries(row)) {
    normalizedRow[normalizeKey(k)] = v
  }
  for (const candidate of candidates) {
    if (normalizedRow[candidate] !== undefined && normalizedRow[candidate] !== '') {
      return normalizedRow[candidate]
    }
  }
  return undefined
}

function parseSide(raw: string | undefined): BoardSide {
  if (!raw) return 'top'
  const v = raw.trim().toLowerCase()
  if (v.startsWith('b') || v === 'bot') return 'bottom'
  return 'top'
}

export type LengthUnit = 'mm' | 'inch'

export function parsePlacementCsv(
  text: string,
  unit: LengthUnit = 'mm',
): { placements: Placement[]; warnings: string[] } {
  const warnings: string[] = []
  const factor = unit === 'inch' ? 25.4 : 1

  const result = Papa.parse<Record<string, string>>(text, {
    header: true,
    skipEmptyLines: true,
    transformHeader: (h) => h.trim(),
    comments: '#',
  })

  if (result.errors.length > 0) {
    warnings.push(...result.errors.slice(0, 5).map((e) => `CSV: ${e.message} (wiersz ${e.row ?? '?'})`))
  }

  const placements: Placement[] = []
  for (const row of result.data) {
    const designator = findField(row, DESIGNATOR_KEYS)
    const xRaw = findField(row, X_KEYS)
    const yRaw = findField(row, Y_KEYS)
    if (!designator || xRaw === undefined || yRaw === undefined) continue

    const x = Number(xRaw) * factor
    const y = Number(yRaw) * factor
    if (Number.isNaN(x) || Number.isNaN(y)) continue

    placements.push({
      designator: designator.trim(),
      x,
      y,
      rotation: Number(findField(row, ROTATION_KEYS) ?? 0) || 0,
      side: parseSide(findField(row, SIDE_KEYS)),
    })
  }

  if (placements.length === 0) {
    warnings.push(
      'Nie znaleziono poprawnych wierszy z pozycją (Designator, Mid X, Mid Y). Sprawdź nagłówki pliku pick-and-place.',
    )
  }

  return { placements, warnings }
}

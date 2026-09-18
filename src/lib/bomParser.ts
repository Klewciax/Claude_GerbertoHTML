import Papa from 'papaparse'
import { XMLParser } from 'fast-xml-parser'
import type { BomComponent } from '../types'
import { makeId } from '../utils/id'

const DESIGNATOR_KEYS = ['designator', 'designators', 'reference', 'references', 'refdes', 'ref des', 'ref']
const VALUE_KEYS = ['value', 'val']
const FOOTPRINT_KEYS = ['footprint', 'package', 'pattern']
const DESCRIPTION_KEYS = ['description', 'desc', 'comment']
const MANUFACTURER_KEYS = ['manufacturer', 'mfg', 'mfr']
const MPN_KEYS = ['mpn', 'manufacturer part number', 'part number', 'part_number', 'partnumber']
const QTY_KEYS = ['qty', 'quantity', 'count']

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

export function splitDesignators(raw: string): string[] {
  return raw
    .split(/[,;/\s]+/)
    .map((d) => d.trim())
    .filter(Boolean)
}

function rowToComponent(row: Record<string, string>): BomComponent | undefined {
  const designatorRaw = findField(row, DESIGNATOR_KEYS)
  if (!designatorRaw) return undefined
  const designators = splitDesignators(designatorRaw)
  if (designators.length === 0) return undefined

  const qtyRaw = findField(row, QTY_KEYS)

  return {
    id: makeId('bom'),
    designators,
    value: findField(row, VALUE_KEYS),
    footprint: findField(row, FOOTPRINT_KEYS),
    description: findField(row, DESCRIPTION_KEYS),
    manufacturer: findField(row, MANUFACTURER_KEYS),
    mpn: findField(row, MPN_KEYS),
    quantity: qtyRaw ? Number(qtyRaw) || designators.length : designators.length,
    delivered: false,
    mounted: false,
  }
}

export function parseBomCsv(text: string): { components: BomComponent[]; warnings: string[] } {
  const warnings: string[] = []
  const result = Papa.parse<Record<string, string>>(text, {
    header: true,
    skipEmptyLines: true,
    transformHeader: (h) => h.trim(),
  })

  if (result.errors.length > 0) {
    warnings.push(...result.errors.slice(0, 5).map((e) => `CSV: ${e.message} (wiersz ${e.row ?? '?'})`))
  }

  const components: BomComponent[] = []
  for (const row of result.data) {
    const component = rowToComponent(row)
    if (component) components.push(component)
  }

  if (components.length === 0) {
    warnings.push(
      'Nie znaleziono kolumny z oznaczeniami (Designator/Reference/RefDes). Sprawdź nagłówki pliku CSV.',
    )
  }

  return { components, warnings }
}

/** Recursively walk a parsed XML object looking for nodes that look like BOM line items. */
function collectXmlComponents(node: unknown, results: Record<string, string>[]): void {
  if (Array.isArray(node)) {
    for (const item of node) collectXmlComponents(item, results)
    return
  }
  if (node === null || typeof node !== 'object') return

  const obj = node as Record<string, unknown>
  const flatEntry: Record<string, string> = {}
  let looksLikeComponent = false

  for (const [key, value] of Object.entries(obj)) {
    if (key.startsWith('@_')) continue
    if (typeof value === 'string' || typeof value === 'number') {
      flatEntry[key] = String(value)
      if (DESIGNATOR_KEYS.includes(normalizeKey(key))) looksLikeComponent = true
    }
  }

  if (looksLikeComponent) {
    results.push(flatEntry)
  }

  for (const value of Object.values(obj)) {
    if (typeof value === 'object' && value !== null) {
      collectXmlComponents(value, results)
    }
  }
}

export function parseBomXml(text: string): { components: BomComponent[]; warnings: string[] } {
  const warnings: string[] = []
  const parser = new XMLParser({ ignoreAttributes: false, attributeNamePrefix: '@_' })

  let parsed: unknown
  try {
    parsed = parser.parse(text)
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return { components: [], warnings: [`Nie udało się sparsować pliku XML: ${message}`] }
  }

  const rows: Record<string, string>[] = []
  collectXmlComponents(parsed, rows)

  const components: BomComponent[] = []
  for (const row of rows) {
    const component = rowToComponent(row)
    if (component) components.push(component)
  }

  if (components.length === 0) {
    warnings.push(
      'Nie znaleziono elementów z polem Designator/Reference w pliku XML. Format XML tego eksportu BOM może nie być obsługiwany — zalecany jest format CSV.',
    )
  }

  return { components, warnings }
}

export function parseBomFile(filename: string, text: string): { components: BomComponent[]; warnings: string[] } {
  if (filename.toLowerCase().endsWith('.xml')) {
    return parseBomXml(text)
  }
  return parseBomCsv(text)
}

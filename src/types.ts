export type BoardSide = 'top' | 'bottom'

export interface Placement {
  designator: string
  x: number
  y: number
  rotation: number
  side: BoardSide
  /** true if the user positioned this manually on the canvas rather than from a PnP file */
  manual?: boolean
}

export interface BomComponent {
  id: string
  /** Reference designators covered by this BOM line, e.g. ["R1", "R2", "R5"] */
  designators: string[]
  value?: string
  footprint?: string
  description?: string
  manufacturer?: string
  mpn?: string
  quantity?: number
  delivered: boolean
  mounted: boolean
}

export interface ReworkDef {
  id: string
  label: string
  createdAt: number
}

export interface Sample {
  id: string
  name: string
  reworkIds: string[]
  notes: string
  createdAt: number
}

export interface ViewBoxTuple {
  x: number
  y: number
  width: number
  height: number
}

export interface GerberRenderResult {
  topSvg?: string
  bottomSvg?: string
  viewBox?: ViewBoxTuple
  warnings: string[]
}

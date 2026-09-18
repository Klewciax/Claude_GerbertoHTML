import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { BomComponent, GerberRenderResult, Placement, ReworkDef, Sample } from '../types'
import { makeId } from '../utils/id'

export type BoardSideView = 'top' | 'bottom'

interface AppState {
  // --- Assembly: Gerber ---
  gerber: GerberRenderResult | null
  gerberFileNames: string[]
  activeSide: BoardSideView
  setGerberResult: (result: GerberRenderResult, fileNames: string[]) => void
  setActiveSide: (side: BoardSideView) => void

  // --- Assembly: BOM + placements ---
  components: BomComponent[]
  placements: Record<string, Placement>
  selectedComponentId: string | null
  bomWarnings: string[]

  loadBom: (components: BomComponent[], warnings: string[]) => void
  mergePlacements: (placements: Placement[]) => void
  setManualPlacement: (designator: string, x: number, y: number) => void
  selectComponent: (id: string | null) => void
  toggleDelivered: (id: string) => void
  toggleMounted: (id: string) => void
  clearAssembly: () => void

  // --- Traceability ---
  reworks: ReworkDef[]
  samples: Sample[]
  addRework: (label: string) => void
  removeRework: (id: string) => void
  addSample: (name: string) => void
  removeSample: (id: string) => void
  toggleSampleRework: (sampleId: string, reworkId: string) => void
  setSampleNotes: (sampleId: string, notes: string) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      gerber: null,
      gerberFileNames: [],
      activeSide: 'top',
      setGerberResult: (result, fileNames) => set({ gerber: result, gerberFileNames: fileNames }),
      setActiveSide: (side) => set({ activeSide: side }),

      components: [],
      placements: {},
      selectedComponentId: null,
      bomWarnings: [],

      loadBom: (components, warnings) =>
        set({ components, bomWarnings: warnings, selectedComponentId: null }),

      mergePlacements: (newPlacements) =>
        set((state) => {
          const placements = { ...state.placements }
          for (const p of newPlacements) {
            placements[p.designator] = p
          }
          return { placements }
        }),

      setManualPlacement: (designator, x, y) =>
        set((state) => ({
          placements: {
            ...state.placements,
            [designator]: {
              designator,
              x,
              y,
              rotation: state.placements[designator]?.rotation ?? 0,
              side: state.placements[designator]?.side ?? 'top',
              manual: true,
            },
          },
        })),

      selectComponent: (id) => set({ selectedComponentId: id }),

      toggleDelivered: (id) =>
        set((state) => ({
          components: state.components.map((c) => (c.id === id ? { ...c, delivered: !c.delivered } : c)),
        })),

      toggleMounted: (id) =>
        set((state) => ({
          components: state.components.map((c) => (c.id === id ? { ...c, mounted: !c.mounted } : c)),
        })),

      clearAssembly: () =>
        set({
          gerber: null,
          gerberFileNames: [],
          components: [],
          placements: {},
          selectedComponentId: null,
          bomWarnings: [],
        }),

      reworks: [],
      samples: [],

      addRework: (label) =>
        set((state) => ({
          reworks: [...state.reworks, { id: makeId('rw'), label, createdAt: Date.now() }],
        })),

      removeRework: (id) =>
        set((state) => ({
          reworks: state.reworks.filter((r) => r.id !== id),
          samples: state.samples.map((s) => ({
            ...s,
            reworkIds: s.reworkIds.filter((rid) => rid !== id),
          })),
        })),

      addSample: (name) =>
        set((state) => ({
          samples: [
            ...state.samples,
            { id: makeId('smp'), name, reworkIds: [], notes: '', createdAt: Date.now() },
          ],
        })),

      removeSample: (id) => set((state) => ({ samples: state.samples.filter((s) => s.id !== id) })),

      toggleSampleRework: (sampleId, reworkId) =>
        set((state) => ({
          samples: state.samples.map((s) =>
            s.id === sampleId
              ? {
                  ...s,
                  reworkIds: s.reworkIds.includes(reworkId)
                    ? s.reworkIds.filter((r) => r !== reworkId)
                    : [...s.reworkIds, reworkId],
                }
              : s,
          ),
        })),

      setSampleNotes: (sampleId, notes) =>
        set((state) => ({
          samples: state.samples.map((s) => (s.id === sampleId ? { ...s, notes } : s)),
        })),
    }),
    {
      name: 'gerberto-html-storage',
      partialize: (state) => ({
        components: state.components,
        placements: state.placements,
        reworks: state.reworks,
        samples: state.samples,
      }),
    },
  ),
)

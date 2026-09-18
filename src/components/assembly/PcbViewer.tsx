import { useEffect, useMemo, useRef, useState, type MutableRefObject } from 'react'
import { Stage, Layer, Group, Image as KonvaImage, Circle, Rect, Text } from 'react-konva'
import type Konva from 'konva'
import type { BomComponent, Placement, ViewBoxTuple } from '../../types'
import { useSvgImage } from '../../lib/useSvgImage'

const PX_PER_MM = 12
const MIN_SCALE = 0.3
const MAX_SCALE = 40

interface Props {
  svg?: string
  viewBox?: ViewBoxTuple
  components: BomComponent[]
  placements: Record<string, Placement>
  selectedComponentId: string | null
  onSelectComponent: (id: string | null) => void
  mappingDesignator: string | null
  onManualPlace: (designator: string, x: number, y: number) => void
}

function statusFill(component: BomComponent): string {
  if (component.mounted) return 'var(--marker-mounted)'
  if (component.delivered) return 'var(--marker-delivered)'
  return 'var(--marker-pending)'
}

export function PcbViewer({
  svg,
  viewBox,
  components,
  placements,
  selectedComponentId,
  onSelectComponent,
  mappingDesignator,
  onManualPlace,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const groupRef: MutableRefObject<Konva.Group | null> = useRef(null)
  const [stageSize, setStageSize] = useState({ width: 800, height: 600 })
  const [stageTransform, setStageTransform] = useState({ scale: 1, x: 0, y: 0 })
  const image = useSvgImage(svg)

  const boardWidthPx = (viewBox?.width ?? 0) * PX_PER_MM
  const boardHeightPx = (viewBox?.height ?? 0) * PX_PER_MM

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry) {
        setStageSize({ width: entry.contentRect.width, height: entry.contentRect.height })
      }
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  function fitToView() {
    if (!viewBox || boardWidthPx <= 0 || boardHeightPx <= 0) return
    const padding = 40
    const scaleX = (stageSize.width - padding * 2) / boardWidthPx
    const scaleY = (stageSize.height - padding * 2) / boardHeightPx
    const scale = Math.max(MIN_SCALE, Math.min(scaleX, scaleY, MAX_SCALE))
    setStageTransform({
      scale,
      x: (stageSize.width - boardWidthPx * scale) / 2,
      y: (stageSize.height - boardHeightPx * scale) / 2,
    })
  }

  const fitKey = `${viewBox?.width}-${viewBox?.height}-${stageSize.width}-${stageSize.height}`
  useEffect(() => {
    if (viewBox) fitToView()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey])

  function handleWheel(e: Konva.KonvaEventObject<WheelEvent>) {
    e.evt.preventDefault()
    const stage = e.target.getStage()
    if (!stage) return
    const pointer = stage.getPointerPosition()
    if (!pointer) return

    const oldScale = stageTransform.scale
    const direction = e.evt.deltaY > 0 ? -1 : 1
    const factor = 1.08
    const newScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, direction > 0 ? oldScale * factor : oldScale / factor))

    const mousePointTo = {
      x: (pointer.x - stageTransform.x) / oldScale,
      y: (pointer.y - stageTransform.y) / oldScale,
    }

    setStageTransform({
      scale: newScale,
      x: pointer.x - mousePointTo.x * newScale,
      y: pointer.y - mousePointTo.y * newScale,
    })
  }

  function handleStageClick(e: Konva.KonvaEventObject<MouseEvent | TouchEvent>) {
    if (!mappingDesignator) {
      if (e.target === e.target.getStage()) onSelectComponent(null)
      return
    }
    const group = groupRef.current
    if (!group) return
    const pos = group.getRelativePointerPosition()
    if (!pos) return
    onManualPlace(mappingDesignator, pos.x, -pos.y)
  }

  const markers = useMemo(() => {
    const result: {
      key: string
      designator: string
      x: number
      y: number
      rotation: number
      selected: boolean
      fill: string
    }[] = []

    for (const component of components) {
      const selected = component.id === selectedComponentId
      for (const designator of component.designators) {
        const placement = placements[designator]
        if (!placement) continue
        result.push({
          key: `${component.id}-${designator}`,
          designator,
          x: placement.x,
          y: -placement.y,
          rotation: placement.rotation,
          selected,
          fill: statusFill(component),
        })
      }
    }
    return result
  }, [components, placements, selectedComponentId])

  return (
    <div className="pcb-viewer" ref={containerRef}>
      <div className="pcb-viewer__toolbar">
        <button type="button" onClick={fitToView} disabled={!viewBox}>
          Dopasuj widok
        </button>
        <button
          type="button"
          onClick={() => setStageTransform((t) => ({ ...t, scale: Math.min(MAX_SCALE, t.scale * 1.3) }))}
        >
          +
        </button>
        <button
          type="button"
          onClick={() => setStageTransform((t) => ({ ...t, scale: Math.max(MIN_SCALE, t.scale / 1.3) }))}
        >
          −
        </button>
        {mappingDesignator && (
          <span className="pcb-viewer__mapping-hint">
            Kliknij na płytce, aby ustawić pozycję <strong>{mappingDesignator}</strong>
          </span>
        )}
      </div>

      {!svg && (
        <div className="pcb-viewer__empty">Wgraj pliki Gerber, aby zobaczyć wizualizację płytki PCB.</div>
      )}

      <Stage
        width={stageSize.width}
        height={stageSize.height}
        scaleX={stageTransform.scale}
        scaleY={stageTransform.scale}
        x={stageTransform.x}
        y={stageTransform.y}
        draggable={!mappingDesignator}
        onDragEnd={(e) => setStageTransform((t) => ({ ...t, x: e.target.x(), y: e.target.y() }))}
        onWheel={handleWheel}
        onClick={handleStageClick}
        onTap={handleStageClick}
        style={{ cursor: mappingDesignator ? 'crosshair' : 'grab' }}
      >
        <Layer>
          <Group
            ref={groupRef}
            x={viewBox ? -viewBox.x * PX_PER_MM : 0}
            y={viewBox ? -viewBox.y * PX_PER_MM : 0}
            scaleX={PX_PER_MM}
            scaleY={PX_PER_MM}
          >
            {viewBox && (
              <Rect
                x={viewBox.x}
                y={viewBox.y}
                width={viewBox.width}
                height={viewBox.height}
                fill="#0a1f33"
              />
            )}
            {image && viewBox && (
              <KonvaImage image={image} x={viewBox.x} y={viewBox.y} width={viewBox.width} height={viewBox.height} />
            )}

            {markers.map((m) => {
              const rad = (m.rotation * Math.PI) / 180
              const pinOffset = 1.6
              const pinX = m.x + Math.sin(rad) * pinOffset
              const pinY = m.y - Math.cos(rad) * pinOffset
              return (
                <Group key={m.key} onClick={(e) => e.cancelBubble = true}>
                  {m.selected && <Circle x={m.x} y={m.y} radius={2.2} stroke="#ff6a00" strokeWidth={0.35} />}
                  <Circle
                    x={m.x}
                    y={m.y}
                    radius={m.selected ? 1.3 : 0.9}
                    fill={m.fill}
                    stroke={m.selected ? '#ff6a00' : '#14314f'}
                    strokeWidth={m.selected ? 0.25 : 0.12}
                    opacity={0.92}
                  />
                  <Circle x={pinX} y={pinY} radius={0.32} fill="#ffcc00" stroke="#7a5200" strokeWidth={0.08} />
                  {m.selected && (
                    <Text
                      x={m.x + 1.6}
                      y={m.y - 1.6}
                      text={m.designator}
                      fontSize={1.6}
                      fill="#ff6a00"
                      fontStyle="bold"
                    />
                  )}
                </Group>
              )
            })}
          </Group>
        </Layer>
      </Stage>
    </div>
  )
}

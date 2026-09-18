import type { BomComponent, Placement } from '../../types'
import { useAppStore } from '../../store/useAppStore'

interface Props {
  components: BomComponent[]
  placements: Record<string, Placement>
  selectedComponentId: string | null
  onSelect: (id: string | null) => void
  mappingDesignator: string | null
  onStartMapping: (designator: string | null) => void
}

export function ComponentList({
  components,
  placements,
  selectedComponentId,
  onSelect,
  mappingDesignator,
  onStartMapping,
}: Props) {
  const toggleDelivered = useAppStore((s) => s.toggleDelivered)
  const toggleMounted = useAppStore((s) => s.toggleMounted)

  if (components.length === 0) {
    return (
      <div className="component-list component-list--empty">
        Wgraj plik BOM, aby zobaczyć listę komponentów.
      </div>
    )
  }

  return (
    <div className="component-list">
      <table>
        <thead>
          <tr>
            <th>Oznaczenie</th>
            <th>Wartość / Footprint</th>
            <th title="Dostarczono">Dost.</th>
            <th title="Zamontowano">Mont.</th>
          </tr>
        </thead>
        <tbody>
          {components.map((component) => {
            const isSelected = component.id === selectedComponentId
            const unplaced = component.designators.filter((d) => !placements[d])
            return (
              <tr
                key={component.id}
                className={isSelected ? 'is-selected' : ''}
                onClick={() => onSelect(isSelected ? null : component.id)}
              >
                <td>
                  <div className="component-list__designators">{component.designators.join(', ')}</div>
                  {component.mpn && <div className="component-list__mpn">{component.mpn}</div>}
                  {unplaced.length > 0 && (
                    <div className="component-list__unplaced">
                      Brak pozycji: {unplaced.join(', ')}{' '}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          onStartMapping(mappingDesignator === unplaced[0] ? null : unplaced[0])
                        }}
                      >
                        {mappingDesignator === unplaced[0] ? 'Anuluj' : 'Ustaw na płytce'}
                      </button>
                    </div>
                  )}
                </td>
                <td>
                  <div>{component.value ?? '—'}</div>
                  <div className="component-list__footprint">{component.footprint ?? ''}</div>
                </td>
                <td onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={component.delivered}
                    onChange={() => toggleDelivered(component.id)}
                  />
                </td>
                <td onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={component.mounted}
                    onChange={() => toggleMounted(component.id)}
                  />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

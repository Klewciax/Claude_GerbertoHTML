import { useState } from 'react'
import { useAppStore } from '../../store/useAppStore'
import { FileUploadPanel } from './FileUploadPanel'
import { ComponentList } from './ComponentList'
import { PcbViewer } from './PcbViewer'

export function AssemblyTab() {
  const gerber = useAppStore((s) => s.gerber)
  const activeSide = useAppStore((s) => s.activeSide)
  const setActiveSide = useAppStore((s) => s.setActiveSide)
  const components = useAppStore((s) => s.components)
  const placements = useAppStore((s) => s.placements)
  const selectedComponentId = useAppStore((s) => s.selectedComponentId)
  const selectComponent = useAppStore((s) => s.selectComponent)
  const setManualPlacement = useAppStore((s) => s.setManualPlacement)

  const [mappingDesignator, setMappingDesignator] = useState<string | null>(null)
  const [showUpload, setShowUpload] = useState(true)

  const totalDesignators = components.reduce((sum, c) => sum + c.designators.length, 0)
  const deliveredCount = components.reduce((sum, c) => sum + (c.delivered ? c.designators.length : 0), 0)
  const mountedCount = components.reduce((sum, c) => sum + (c.mounted ? c.designators.length : 0), 0)

  const svg = activeSide === 'top' ? gerber?.topSvg : gerber?.bottomSvg

  return (
    <div className="assembly-tab">
      <aside className="assembly-tab__sidebar">
        <div className="assembly-tab__sidebar-toggle">
          <button type="button" onClick={() => setShowUpload((v) => !v)}>
            {showUpload ? 'Ukryj wgrywanie plików' : 'Pokaż wgrywanie plików'}
          </button>
        </div>
        {showUpload && <FileUploadPanel />}

        <div className="assembly-tab__summary">
          <div>
            Elementy: <strong>{totalDesignators}</strong>
          </div>
          <div>
            Dostarczone: <strong>{deliveredCount}</strong>/{totalDesignators}
          </div>
          <div>
            Zamontowane: <strong>{mountedCount}</strong>/{totalDesignators}
          </div>
        </div>

        <ComponentList
          components={components}
          placements={placements}
          selectedComponentId={selectedComponentId}
          onSelect={selectComponent}
          mappingDesignator={mappingDesignator}
          onStartMapping={setMappingDesignator}
        />
      </aside>

      <section className="assembly-tab__viewer">
        <div className="assembly-tab__side-switch">
          <button
            type="button"
            className={activeSide === 'top' ? 'is-active' : ''}
            onClick={() => setActiveSide('top')}
          >
            Góra (Top)
          </button>
          <button
            type="button"
            className={activeSide === 'bottom' ? 'is-active' : ''}
            onClick={() => setActiveSide('bottom')}
          >
            Dół (Bottom)
          </button>
          {gerber && gerber.warnings.length > 0 && (
            <span className="assembly-tab__warning" title={gerber.warnings.join('\n')}>
              ⚠ {gerber.warnings.length} ostrzeżeń
            </span>
          )}
        </div>
        <PcbViewer
          svg={svg}
          viewBox={gerber?.viewBox}
          components={components}
          placements={placements}
          selectedComponentId={selectedComponentId}
          onSelectComponent={selectComponent}
          mappingDesignator={mappingDesignator}
          onManualPlace={(designator, x, y) => {
            setManualPlacement(designator, x, y)
            setMappingDesignator(null)
          }}
        />
      </section>
    </div>
  )
}

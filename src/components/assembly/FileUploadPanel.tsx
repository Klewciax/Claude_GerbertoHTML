import { useRef, useState } from 'react'
import { renderGerberFiles } from '../../lib/gerber'
import { parseBomFile } from '../../lib/bomParser'
import { parsePlacementCsv, type LengthUnit } from '../../lib/placementParser'
import { useAppStore } from '../../store/useAppStore'

export function FileUploadPanel() {
  const setGerberResult = useAppStore((s) => s.setGerberResult)
  const loadBom = useAppStore((s) => s.loadBom)
  const mergePlacements = useAppStore((s) => s.mergePlacements)
  const clearAssembly = useAppStore((s) => s.clearAssembly)

  const [gerberBusy, setGerberBusy] = useState(false)
  const [bomBusy, setBomBusy] = useState(false)
  const [placementBusy, setPlacementBusy] = useState(false)
  const [unit, setUnit] = useState<LengthUnit>('mm')
  const [messages, setMessages] = useState<string[]>([])

  const gerberInputRef = useRef<HTMLInputElement>(null)
  const bomInputRef = useRef<HTMLInputElement>(null)
  const placementInputRef = useRef<HTMLInputElement>(null)

  async function handleGerberFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return
    setGerberBusy(true)
    setMessages([])
    try {
      const files = Array.from(fileList)
      const result = await renderGerberFiles(files)
      setGerberResult(result, files.map((f) => f.name))
      setMessages(result.warnings)
    } finally {
      setGerberBusy(false)
    }
  }

  async function handleBomFile(fileList: FileList | null) {
    const file = fileList?.[0]
    if (!file) return
    setBomBusy(true)
    setMessages([])
    try {
      const text = await file.text()
      const { components, warnings } = parseBomFile(file.name, text)
      loadBom(components, warnings)
      setMessages(warnings)
    } finally {
      setBomBusy(false)
    }
  }

  async function handlePlacementFile(fileList: FileList | null) {
    const file = fileList?.[0]
    if (!file) return
    setPlacementBusy(true)
    setMessages([])
    try {
      const text = await file.text()
      const { placements, warnings } = parsePlacementCsv(text, unit)
      mergePlacements(placements)
      setMessages(warnings)
    } finally {
      setPlacementBusy(false)
    }
  }

  return (
    <div className="upload-panel">
      <h2>Dane wejściowe</h2>

      <div className="upload-panel__row">
        <label className="upload-panel__label">1. Pliki Gerber (RS-274X) / Excellon</label>
        <input
          ref={gerberInputRef}
          type="file"
          multiple
          accept=".gbr,.gbl,.gbo,.gbp,.gbs,.gko,.gtl,.gto,.gtp,.gts,.gml,.gm1,.txt,.drl,.xnc,.nc,.tho,.thd"
          onChange={(e) => handleGerberFiles(e.target.files)}
        />
        {gerberBusy && <span className="upload-panel__status">Renderowanie…</span>}
      </div>

      <div className="upload-panel__row">
        <label className="upload-panel__label">2. Plik BOM (CSV lub XML)</label>
        <input
          ref={bomInputRef}
          type="file"
          accept=".csv,.xml"
          onChange={(e) => handleBomFile(e.target.files)}
        />
        {bomBusy && <span className="upload-panel__status">Parsowanie…</span>}
      </div>

      <div className="upload-panel__row">
        <label className="upload-panel__label">3. Plik pick-and-place (opcjonalnie, CSV)</label>
        <div className="upload-panel__inline">
          <input
            ref={placementInputRef}
            type="file"
            accept=".csv,.txt"
            onChange={(e) => handlePlacementFile(e.target.files)}
          />
          <select value={unit} onChange={(e) => setUnit(e.target.value as LengthUnit)}>
            <option value="mm">mm</option>
            <option value="inch">cale</option>
          </select>
          {placementBusy && <span className="upload-panel__status">Parsowanie…</span>}
        </div>
        <p className="upload-panel__hint">
          Kolumny: Designator, Mid X, Mid Y, Rotation, Layer. Bez tego pliku komponenty można pozycjonować
          ręcznie na liście po lewej stronie.
        </p>
      </div>

      {messages.length > 0 && (
        <ul className="upload-panel__messages">
          {messages.map((m, i) => (
            <li key={i}>{m}</li>
          ))}
        </ul>
      )}

      <button
        type="button"
        className="upload-panel__reset"
        onClick={() => {
          clearAssembly()
          setMessages([])
          if (gerberInputRef.current) gerberInputRef.current.value = ''
          if (bomInputRef.current) bomInputRef.current.value = ''
          if (placementInputRef.current) placementInputRef.current.value = ''
        }}
      >
        Wyczyść dane Assembly
      </button>
    </div>
  )
}

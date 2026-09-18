import type { ReworkDef, Sample } from '../../types'
import { useAppStore } from '../../store/useAppStore'

interface Props {
  sample: Sample
  reworks: ReworkDef[]
}

export function SampleCard({ sample, reworks }: Props) {
  const toggleSampleRework = useAppStore((s) => s.toggleSampleRework)
  const setSampleNotes = useAppStore((s) => s.setSampleNotes)
  const removeSample = useAppStore((s) => s.removeSample)

  return (
    <div className="sample-card">
      <div className="sample-card__header">
        <h3>{sample.name}</h3>
        <button type="button" onClick={() => removeSample(sample.id)} title="Usuń sampel">
          ✕
        </button>
      </div>

      <div className="sample-card__reworks">
        {reworks.length === 0 && <p className="sample-card__empty">Dodaj przeróbki do wspólnej listy.</p>}
        {reworks.map((rework) => (
          <label key={rework.id} className="sample-card__rework-item">
            <input
              type="checkbox"
              checked={sample.reworkIds.includes(rework.id)}
              onChange={() => toggleSampleRework(sample.id, rework.id)}
            />
            <span>{rework.label}</span>
          </label>
        ))}
      </div>

      <textarea
        className="sample-card__notes"
        placeholder="Uwagi dotyczące tego sampla…"
        value={sample.notes}
        onChange={(e) => setSampleNotes(sample.id, e.target.value)}
      />
    </div>
  )
}

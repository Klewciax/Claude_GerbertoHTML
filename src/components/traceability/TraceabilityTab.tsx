import { useState } from 'react'
import { useAppStore } from '../../store/useAppStore'
import { ReworkPool } from './ReworkPool'
import { SampleCard } from './SampleCard'

export function TraceabilityTab() {
  const reworks = useAppStore((s) => s.reworks)
  const samples = useAppStore((s) => s.samples)
  const addSample = useAppStore((s) => s.addSample)
  const [sampleName, setSampleName] = useState('')

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = sampleName.trim()
    if (!trimmed) return
    addSample(trimmed)
    setSampleName('')
  }

  return (
    <div className="traceability-tab">
      <aside className="traceability-tab__sidebar">
        <ReworkPool />
      </aside>

      <section className="traceability-tab__samples">
        <div className="traceability-tab__add-sample">
          <h2>Sample</h2>
          <form onSubmit={submit}>
            <input
              type="text"
              value={sampleName}
              onChange={(e) => setSampleName(e.target.value)}
              placeholder="np. Sample #12 / SN-0042"
            />
            <button type="submit">Dodaj sampel</button>
          </form>
        </div>

        {samples.length === 0 && (
          <p className="traceability-tab__empty">Brak sampli — dodaj pierwszy powyżej.</p>
        )}

        <div className="traceability-tab__grid">
          {samples.map((sample) => (
            <SampleCard key={sample.id} sample={sample} reworks={reworks} />
          ))}
        </div>
      </section>
    </div>
  )
}

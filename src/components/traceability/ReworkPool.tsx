import { useState } from 'react'
import { useAppStore } from '../../store/useAppStore'

export function ReworkPool() {
  const reworks = useAppStore((s) => s.reworks)
  const addRework = useAppStore((s) => s.addRework)
  const removeRework = useAppStore((s) => s.removeRework)
  const [label, setLabel] = useState('')

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = label.trim()
    if (!trimmed) return
    addRework(trimmed)
    setLabel('')
  }

  return (
    <div className="rework-pool">
      <h2>Wspólna lista przeróbek (rework)</h2>
      <p className="rework-pool__hint">
        Przeróbki dodane tutaj są wspólne dla wszystkich sampli — dla każdego sampla zaznaczysz, które z nich
        wystąpiły.
      </p>
      <form onSubmit={submit} className="rework-pool__form">
        <input
          type="text"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="np. Wymiana R12 na wartość 10k"
        />
        <button type="submit">Dodaj przeróbkę</button>
      </form>

      <ul className="rework-pool__list">
        {reworks.length === 0 && <li className="rework-pool__empty">Brak przeróbek na liście.</li>}
        {reworks.map((r) => (
          <li key={r.id}>
            <span>{r.label}</span>
            <button type="button" onClick={() => removeRework(r.id)} title="Usuń przeróbkę z wspólnej listy">
              ✕
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

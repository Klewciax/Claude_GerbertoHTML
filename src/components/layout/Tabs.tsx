export type TabKey = 'assembly' | 'traceability'

interface Props {
  active: TabKey
  onChange: (tab: TabKey) => void
}

const TABS: { key: TabKey; label: string }[] = [
  { key: 'assembly', label: 'Assembly' },
  { key: 'traceability', label: 'Traceability' },
]

export function Tabs({ active, onChange }: Props) {
  return (
    <nav className="tabs">
      {TABS.map((tab) => (
        <button
          key={tab.key}
          type="button"
          className={`tabs__button ${active === tab.key ? 'is-active' : ''}`}
          onClick={() => onChange(tab.key)}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  )
}

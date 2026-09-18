import { useState } from 'react'
import { Tabs, type TabKey } from './components/layout/Tabs'
import { AssemblyTab } from './components/assembly/AssemblyTab'
import { TraceabilityTab } from './components/traceability/TraceabilityTab'

function App() {
  const [tab, setTab] = useState<TabKey>('assembly')

  return (
    <div className="app">
      <header className="app__header">
        <div className="app__brand">
          <span className="app__brand-mark">PCB</span>
          <div>
            <h1>GerbertoHTML</h1>
            <p>Zarządzanie montażem i śledzenie przeróbek płytek PCB</p>
          </div>
        </div>
        <Tabs active={tab} onChange={setTab} />
      </header>

      <main className="app__main">
        {tab === 'assembly' ? <AssemblyTab /> : <TraceabilityTab />}
      </main>
    </div>
  )
}

export default App

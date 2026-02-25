import { useState, useEffect, useCallback } from 'react'
import './theme.css'
import ServiceHealth from './components/ServiceHealth'
import ErrorStats from './components/ErrorStats'
import MemoryStats from './components/MemoryStats'
import ContainerLoad from './components/ContainerLoad'

const REFRESH_INTERVAL = 30_000  // 30 seconds

function useAutoFetch(url) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [lastUpdated, setLastUpdated] = useState(null)

  const fetch_ = useCallback(async () => {
    try {
      const res = await fetch(url)
      if (!res.ok) throw new Error(res.status)
      setData(await res.json())
      setError(false)
      setLastUpdated(new Date())
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [url])

  useEffect(() => {
    fetch_()
    const id = setInterval(fetch_, REFRESH_INTERVAL)
    return () => clearInterval(id)
  }, [fetch_])

  return { data, loading, error, lastUpdated }
}

function Panel({ title, lastUpdated, children }) {
  const timeStr = lastUpdated
    ? lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '—'
  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">{title}</span>
        <span className="panel-updated">updated {timeStr}</span>
      </div>
      <div className="panel-body">{children}</div>
    </div>
  )
}

export default function App() {
  const services   = useAutoFetch('/api/services')
  const errors     = useAutoFetch('/api/errors')
  const memory     = useAutoFetch('/api/memory')
  const containers = useAutoFetch('/api/containers')

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>RuneGuard Dashboard</h1>
        <span className="header-meta">auto-refresh every 30s</span>
      </div>
      <div className="grid">
        <Panel title="Service Health" lastUpdated={services.lastUpdated}>
          <ServiceHealth {...services} />
        </Panel>
        <Panel title="Error Stats" lastUpdated={errors.lastUpdated}>
          <ErrorStats {...errors} />
        </Panel>
        <Panel title="Memory / AI" lastUpdated={memory.lastUpdated}>
          <MemoryStats {...memory} />
        </Panel>
        <Panel title="Container Load" lastUpdated={containers.lastUpdated}>
          <ContainerLoad {...containers} />
        </Panel>
      </div>
    </div>
  )
}

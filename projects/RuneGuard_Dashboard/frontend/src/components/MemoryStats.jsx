export default function MemoryStats({ data, loading, error }) {
  if (loading) return <p className="state-msg">Loading...</p>
  if (error)   return <p className="state-msg error">Failed to load memory stats</p>

  const total      = data?.memories?.total ?? 0
  const recent24h  = data?.recent_24h ?? 0
  const byNs       = data?.memories?.by_namespace ?? {}
  const influx     = data?.influx_available ?? false
  const redis      = data?.redis_available ?? false

  return (
    <div>
      <div className="stat-row">
        <span className="stat-label">Total memories</span>
        <span className="stat-value accent">{total.toLocaleString()}</span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Added last 24 h</span>
        <span className="stat-value">{recent24h}</span>
      </div>
      <div className="stat-row" style={{ alignItems: 'flex-start', flexDirection: 'column', gap: '4px' }}>
        <span className="stat-label">By namespace</span>
        {Object.keys(byNs).length === 0
          ? <span style={{ color: 'var(--text-dim)', fontSize: '11px' }}>none</span>
          : Object.entries(byNs).map(([ns, cnt]) => (
              <span key={ns} style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                <span style={{ color: 'var(--text-secondary)', fontSize: '11px' }}>{ns}</span>
                <span style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{cnt}</span>
              </span>
            ))
        }
      </div>
      <div className="stat-row">
        <span className="stat-label">InfluxDB</span>
        <span>
          <span className={`avail-dot ${influx ? 'yes' : 'no'}`} />
          <span className={`stat-value ${influx ? 'online' : 'offline'}`}>
            {influx ? 'available' : 'unavailable'}
          </span>
        </span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Redis</span>
        <span>
          <span className={`avail-dot ${redis ? 'yes' : 'no'}`} />
          <span className={`stat-value ${redis ? 'online' : 'offline'}`}>
            {redis ? 'available' : 'unavailable'}
          </span>
        </span>
      </div>
    </div>
  )
}

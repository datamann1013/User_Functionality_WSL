export default function ErrorStats({ data, loading, error }) {
  if (loading) return <p className="state-msg">Loading...</p>
  if (error)   return <p className="state-msg error">Failed to load error stats</p>

  const total      = data?.total_errors ?? 0
  const lastHour   = data?.errors_last_hour ?? 0
  const errCount   = data?.error_count ?? 0
  const warnCount  = data?.warning_count ?? 0
  const infoCount  = data?.info_count ?? 0

  return (
    <div>
      <div className="stat-row">
        <span className="stat-label">Total logged</span>
        <span className="stat-value accent">{total.toLocaleString()}</span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Last hour</span>
        <span className={`stat-value ${lastHour > 0 ? 'warning' : 'online'}`}>
          {lastHour}
        </span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Errors (E)</span>
        <span className={`stat-value ${errCount > 0 ? 'offline' : 'online'}`}>
          {errCount}
        </span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Warnings (W)</span>
        <span className={`stat-value ${warnCount > 0 ? 'warning' : 'online'}`}>
          {warnCount}
        </span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Info (I)</span>
        <span className="stat-value">{infoCount}</span>
      </div>
    </div>
  )
}

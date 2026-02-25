export default function ServiceHealth({ data, loading, error }) {
  if (loading) return <p className="state-msg">Loading...</p>
  if (error)   return <p className="state-msg error">Failed to load service health</p>

  const services = data?.services ?? []
  if (services.length === 0)
    return <p className="state-msg">No service data yet — waiting for first snapshot</p>

  return (
    <table>
      <thead>
        <tr>
          <th>Service</th>
          <th>Status</th>
          <th>Last Seen</th>
        </tr>
      </thead>
      <tbody>
        {services.map(svc => {
          const online = svc.is_online === 1 || svc.is_online === true
          const secs = svc.seconds_since_heartbeat
          const lastSeen = secs != null
            ? secs < 60
              ? `${Math.round(secs)}s ago`
              : secs < 3600
              ? `${Math.round(secs / 60)}m ago`
              : `${Math.round(secs / 3600)}h ago`
            : '—'
          return (
            <tr key={svc.name}>
              <td>{svc.name}</td>
              <td>
                <span className={`badge badge-${online ? 'online' : 'offline'}`}>
                  {online ? 'online' : 'offline'}
                </span>
              </td>
              <td style={{ color: 'var(--text-secondary)', fontSize: '11px' }}>{lastSeen}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

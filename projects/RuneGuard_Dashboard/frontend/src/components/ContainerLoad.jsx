function CpuBar({ pct }) {
  const clamped = Math.min(100, Math.max(0, pct ?? 0))
  const color = clamped > 80 ? 'var(--offline)' : clamped > 50 ? 'var(--warning)' : 'var(--accent)'
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
      <span className="cpu-bar-bg">
        <span className="cpu-bar-fill" style={{ width: `${clamped}%`, background: color }} />
      </span>
      <span style={{ minWidth: '38px', textAlign: 'right' }}>{clamped.toFixed(1)}%</span>
    </span>
  )
}

export default function ContainerLoad({ data, loading, error }) {
  if (loading) return <p className="state-msg">Loading...</p>
  if (error)   return <p className="state-msg error">Failed to load container data</p>

  const containers = data?.containers ?? []
  if (containers.length === 0)
    return <p className="state-msg">No container data yet — waiting for Insight collector</p>

  const sorted = [...containers].sort((a, b) => b.cpu_percent - a.cpu_percent)

  return (
    <table>
      <thead>
        <tr>
          <th>Container</th>
          <th>CPU</th>
          <th>RAM (MB)</th>
          <th>Net RX/TX (MB)</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map(c => (
          <tr key={c.container_name}>
            <td style={{ fontSize: '11px' }}>{c.service_name}</td>
            <td><CpuBar pct={c.cpu_percent} /></td>
            <td style={{ fontSize: '11px' }}>
              {(c.mem_usage_mb ?? 0).toFixed(0)} / {(c.mem_limit_mb ?? 0).toFixed(0)}
            </td>
            <td style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
              {(c.net_rx_mb ?? 0).toFixed(1)} / {(c.net_tx_mb ?? 0).toFixed(1)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

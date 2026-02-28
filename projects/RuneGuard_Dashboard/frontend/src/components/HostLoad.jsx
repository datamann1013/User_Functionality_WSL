function UsageBar({ pct, color }) {
  return (
    <span className="cpu-bar-bg">
      <div
        className="cpu-bar-fill"
        style={{ width: `${Math.min(Math.max(pct, 0), 100)}%`, background: color || 'var(--accent)' }}
      />
    </span>
  )
}

export default function HostLoad({ data, loading, error }) {
  if (loading) return <p className="state-msg">Loading…</p>
  if (error) return <p className="state-msg error">Unavailable</p>
  if (!data?.available) return <p className="state-msg">No data — is Sentinel running?</p>

  const m = data.metrics
  const cpuPct = m.cpu_percent ?? 0
  const memUsed = m.mem_used_gb ?? 0
  const memTotal = m.mem_total_gb ?? 0
  const memPct = memTotal > 0 ? (memUsed / memTotal) * 100 : 0

  // Discover GPU slots: gpu_0_util_percent, gpu_1_util_percent, …
  const gpuSlots = []
  for (let i = 0; i < 8; i++) {
    const util = m[`gpu_${i}_util_percent`]
    if (util === undefined) break
    gpuSlots.push({
      slot: i,
      util,
      memUsed: m[`gpu_${i}_mem_used_gb`],
      memTotal: m[`gpu_${i}_mem_total_gb`],
    })
  }

  return (
    <div>
      {/* CPU */}
      <div className="stat-row">
        <span className="stat-label">CPU</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <UsageBar pct={cpuPct} />
          <span className="stat-value">{cpuPct.toFixed(1)}%</span>
        </span>
      </div>

      {/* RAM */}
      <div className="stat-row">
        <span className="stat-label">RAM</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <UsageBar pct={memPct} />
          <span className="stat-value">{memUsed.toFixed(1)} / {memTotal.toFixed(1)} GB</span>
        </span>
      </div>

      {/* GPU(s) */}
      {gpuSlots.length > 0
        ? gpuSlots.map((g) => (
          <div key={g.slot} className="stat-row">
            <span className="stat-label">GPU{gpuSlots.length > 1 ? ` ${g.slot}` : ''}</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <UsageBar pct={g.util} color="var(--online)" />
              <span className="stat-value">
                {g.util.toFixed(1)}%
                {g.memUsed != null && g.memTotal != null
                  ? ` · ${g.memUsed.toFixed(1)}/${g.memTotal.toFixed(1)}GB`
                  : ''}
              </span>
            </span>
          </div>
        ))
        : (
          <div className="stat-row">
            <span className="stat-label">GPU</span>
            <span className="stat-value" style={{ color: 'var(--text-dim)' }}>no utilization data</span>
          </div>
        )
      }
    </div>
  )
}

export default function MachineProfile({ data, loading, error }) {
  if (loading) return <p className="state-msg">Loading…</p>
  if (error) return <p className="state-msg error">Unavailable</p>
  if (!data?.available) return <p className="state-msg">No profile — is Sentinel running?</p>

  const p = data.profile

  // Split GPUs into discrete and integrated for labelling
  const gpus = p.gpu || []
  const discrete   = gpus.filter(g => g.gpu_type !== 'integrated')
  const integrated = gpus.filter(g => g.gpu_type === 'integrated')

  function GpuRow({ g, label }) {
    const vram = g.total_memory_gb != null && g.total_memory_gb > 0
      ? ` · ${g.total_memory_gb.toFixed(0)}GB`
      : ''
    return (
      <div className="stat-row">
        <span className="stat-label">{label}</span>
        <span className="stat-value" style={{ fontSize: 11 }}>
          {g.name || '—'}{vram}
        </span>
      </div>
    )
  }

  return (
    <div>
      <div className="stat-row">
        <span className="stat-label">HOST</span>
        <span className="stat-value">{p.hostname || '—'}</span>
      </div>
      <div className="stat-row">
        <span className="stat-label">OS</span>
        <span className="stat-value">{p.platform || '—'}</span>
      </div>
      <div className="stat-row">
        <span className="stat-label">CPU</span>
        <span className="stat-value" style={{ fontSize: 11 }}>{p.cpu_model || '—'}</span>
      </div>
      <div className="stat-row">
        <span className="stat-label">CORES</span>
        <span className="stat-value">{p.cpu_cores ?? '—'} threads</span>
      </div>
      <div className="stat-row">
        <span className="stat-label">RAM</span>
        <span className="stat-value">{p.memory_total_gb != null ? `${p.memory_total_gb.toFixed(1)} GB` : '—'}</span>
      </div>

      {/* Discrete GPUs */}
      {discrete.length > 0
        ? discrete.map((g, i) => (
          <GpuRow key={i} g={g} label={discrete.length > 1 ? `GPU ${i}` : 'GPU'} />
        ))
        : (
          <div className="stat-row">
            <span className="stat-label">GPU</span>
            <span className="stat-value" style={{ color: 'var(--text-dim)' }}>—</span>
          </div>
        )
      }

      {/* Integrated GPUs */}
      {integrated.map((g, i) => (
        <GpuRow key={i} g={g} label={integrated.length > 1 ? `iGPU ${i}` : 'iGPU'} />
      ))}

      {/* NPU row(s) */}
      {(p.npu || []).length > 0
        ? (p.npu || []).map((n, i) => (
          <div key={i} className="stat-row">
            <span className="stat-label">NPU{(p.npu || []).length > 1 ? ` ${i}` : ''}</span>
            <span className="stat-value" style={{ fontSize: 11 }}>{n.name || '—'}</span>
          </div>
        ))
        : (
          <div className="stat-row">
            <span className="stat-label">NPU</span>
            <span className="stat-value" style={{ color: 'var(--text-dim)' }}>—</span>
          </div>
        )
      }

      {/* Disk row(s) */}
      {(p.disks || []).map((d, i) => (
        <div key={i} className="stat-row">
          <span className="stat-label">DISK{(p.disks || []).length > 1 ? ` ${i}` : ''}</span>
          <span className="stat-value" style={{ fontSize: 11 }}>
            {d.model || '—'}
            {d.size_gb != null ? ` · ${Math.round(d.size_gb)}GB` : ''}
            {d.media_type ? ` [${d.media_type}]` : ''}
          </span>
        </div>
      ))}

      {/* RAM slot row(s) */}
      {(p.ram_slots || []).map((s, i) => (
        <div key={i} className="stat-row">
          <span className="stat-label">DIMM{(p.ram_slots || []).length > 1 ? ` ${i + 1}` : ''}</span>
          <span className="stat-value">
            {s.capacity_gb != null ? `${Math.round(s.capacity_gb)}GB` : '—'}
            {s.memory_type ? ` ${s.memory_type}` : ''}
            {s.speed_mhz ? ` @ ${s.speed_mhz}MHz` : ''}
          </span>
        </div>
      ))}
    </div>
  )
}

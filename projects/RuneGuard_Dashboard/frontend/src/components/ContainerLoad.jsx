import { useState, useEffect } from 'react'

// ── Mini bar ──────────────────────────────────────────────────────────────────

function Bar({ pct, color }) {
  const clamped = Math.min(100, Math.max(0, pct ?? 0))
  const c = color ?? (clamped > 80 ? 'var(--offline)' : clamped > 50 ? 'var(--warning)' : 'var(--accent)')
  return (
    <span className="cpu-bar-bg">
      <div className="cpu-bar-fill" style={{ width: `${clamped}%`, background: c }} />
    </span>
  )
}

function CpuCell({ pct }) {
  const v = pct ?? 0
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
      <Bar pct={v} />
      <span style={{ minWidth: '38px', textAlign: 'right' }}>{v.toFixed(1)}%</span>
    </span>
  )
}

// RAM bar — if limit is 0 (unlimited), use 200 MB as a baseline reference
function RamCell({ usedMb, limitMb }) {
  const used  = usedMb  ?? 0
  const limit = limitMb ?? 0
  const ref   = limit > 0 ? limit : 200        // fallback reference
  const pct   = Math.min(100, (used / ref) * 100)
  const color = pct > 90 ? 'var(--offline)' : pct > 70 ? 'var(--warning)' : 'var(--accent)'
  const limitStr = limit > 0
    ? `${limit >= 1024 ? (limit / 1024).toFixed(1) + 'G' : limit.toFixed(0) + 'M'}`
    : '∞'
  const usedStr = used >= 1024
    ? `${(used / 1024).toFixed(2)}G`
    : `${used.toFixed(0)}M`
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
      <Bar pct={pct} color={color} />
      <span style={{ minWidth: '60px', fontSize: '11px' }}>{usedStr} / {limitStr}</span>
    </span>
  )
}

// ── Sparkline SVG ─────────────────────────────────────────────────────────────

function Sparkline({ points, width = 80, height = 20, color = 'var(--accent)' }) {
  if (!points || points.length < 2) return <span style={{ color: 'var(--text-dim)', fontSize: 10 }}>no data</span>
  const vals = points.map(p => p.value)
  const max  = Math.max(...vals, 0.001)
  const coords = vals.map((v, i) => {
    const x = (i / (vals.length - 1)) * width
    const y = height - (v / max) * (height - 2) - 1
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
  return (
    <svg width={width} height={height} style={{ display: 'block', overflow: 'visible' }}>
      <polyline points={coords} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  )
}

// ── Hover stats panel ─────────────────────────────────────────────────────────

function HoverPanel({ containerName, series }) {
  const s = series?.[containerName] ?? {}
  const cpuPts = s['cpu_percent']    ?? []
  const ramPts = s['mem_usage_mb']   ?? []
  const netRx  = s['net_rx_mb']      ?? []
  const netTx  = s['net_tx_mb']      ?? []

  const latestCpu = cpuPts.at(-1)?.value
  const peakCpu   = cpuPts.length ? Math.max(...cpuPts.map(p => p.value)) : null
  const latestRam = ramPts.at(-1)?.value

  return (
    <td colSpan={4} style={{ padding: '6px 10px 8px 10px', background: 'rgba(59,130,246,0.06)', borderTop: 'none' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px', fontSize: '11px' }}>
        <div>
          <div style={{ color: 'var(--text-dim)', marginBottom: '4px' }}>CPU 30m</div>
          <Sparkline points={cpuPts} color="var(--accent)" />
          {latestCpu != null && <div style={{ color: 'var(--text-secondary)' }}>now {latestCpu.toFixed(1)}% · peak {(peakCpu ?? 0).toFixed(1)}%</div>}
        </div>
        <div>
          <div style={{ color: 'var(--text-dim)', marginBottom: '4px' }}>RAM 30m</div>
          <Sparkline points={ramPts} color="#a78bfa" />
          {latestRam != null && <div style={{ color: 'var(--text-secondary)' }}>{latestRam >= 1024 ? (latestRam / 1024).toFixed(2) + 'G' : latestRam.toFixed(0) + 'M'}</div>}
        </div>
        <div>
          <div style={{ color: 'var(--text-dim)', marginBottom: '4px' }}>Net RX/TX 30m</div>
          <svg width={80} height={20} style={{ display: 'block', overflow: 'visible' }}>
            {netRx.length >= 2 && (() => {
              const max = Math.max(...netRx.map(p => p.value), ...netTx.map(p => p.value), 0.001)
              const rx = netRx.map((p, i) => `${(i/(netRx.length-1)*80).toFixed(1)},${(20-(p.value/max)*18-1).toFixed(1)}`).join(' ')
              const tx = netTx.map((p, i) => `${(i/(netTx.length-1)*80).toFixed(1)},${(20-(p.value/max)*18-1).toFixed(1)}`).join(' ')
              return <>
                <polyline points={rx} fill="none" stroke="#34d399" strokeWidth="1.5" strokeLinejoin="round" />
                <polyline points={tx} fill="none" stroke="#f87171" strokeWidth="1.5" strokeLinejoin="round" />
              </>
            })()}
          </svg>
          <div style={{ color: 'var(--text-secondary)', display: 'flex', gap: '6px' }}>
            <span style={{ color: '#34d399' }}>↓ RX</span>
            <span style={{ color: '#f87171' }}>↑ TX</span>
          </div>
        </div>
      </div>
    </td>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ContainerLoad({ data, loading, error }) {
  const [history, setHistory] = useState({})
  const [hovered, setHovered] = useState(null)

  useEffect(() => {
    fetch('/api/containers/history')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.series) setHistory(d.series) })
      .catch(() => {})
  }, [data])  // refresh history whenever the main data refreshes

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
          <th>RAM</th>
          <th>Net RX/TX (MB)</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map(c => (
          <>
            <tr
              key={c.container_name}
              style={{ cursor: 'pointer', transition: 'background 0.15s' }}
              onMouseEnter={() => setHovered(c.container_name)}
              onMouseLeave={() => setHovered(null)}
            >
              <td style={{ fontSize: '11px' }}>{c.service_name}</td>
              <td><CpuCell pct={c.cpu_percent} /></td>
              <td><RamCell usedMb={c.mem_usage_mb} limitMb={c.mem_limit_mb} /></td>
              <td style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                {(c.net_rx_mb ?? 0).toFixed(1)} / {(c.net_tx_mb ?? 0).toFixed(1)}
              </td>
            </tr>
            {hovered === c.container_name && (
              <tr key={`${c.container_name}-hover`}>
                <HoverPanel containerName={c.container_name} series={history} />
              </tr>
            )}
          </>
        ))}
      </tbody>
    </table>
  )
}

export default function HealthDot({ name, connected, detail }) {
  const color = connected ? 'var(--success)' : 'var(--danger)'
  const status = connected ? 'CONNECTED' : 'OFFLINE'
  
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '12px',
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)',
      padding: '16px 20px',
      minWidth: '180px',
      boxShadow: 'var(--shadow-sm)'
    }}>
      <div style={{
        width: '10px',
        height: '10px',
        borderRadius: '50%',
        background: color,
        boxShadow: `0 0 6px ${color}`,
        animation: connected ? 'pulse 2s infinite' : 'none',
        flexShrink: 0
      }} />
      
      <div style={{ flex: 1 }}>
        <div style={{ color: 'var(--text-primary)', fontSize: '14px', fontWeight: 600 }}>{name}</div>
        {detail && <div style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>{detail}</div>}
      </div>
      
      <div style={{ color, fontSize: '11px', fontWeight: 600, letterSpacing: '0.5px' }}>
        {status}
      </div>
      
      <style>{`
        @keyframes pulse {
          0% { transform: scale(1); }
          50% { transform: scale(1.3); }
          100% { transform: scale(1); }
        }
      `}</style>
    </div>
  )
}

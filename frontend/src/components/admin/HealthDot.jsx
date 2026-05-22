export default function HealthDot({ name, connected, detail }) {
  const color = connected ? 'var(--green)' : 'var(--red)'
  const status = connected ? 'CONNECTED' : 'OFFLINE'
  
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      background: 'var(--panel)',
      border: '1px solid var(--border)',
      borderRadius: '8px',
      padding: '14px 18px',
      minWidth: '180px'
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
        <div style={{ color: 'var(--text)', fontSize: '13px', fontWeight: 600 }}>{name}</div>
        {detail && <div style={{ color: 'var(--text3)', fontSize: '10px' }}>{detail}</div>}
      </div>
      
      <div style={{ color, fontSize: '10px', fontWeight: 600 }}>
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

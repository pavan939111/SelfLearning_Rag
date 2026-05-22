export default function ConfidenceBar({ confidence }) {
  const pct = Math.round((confidence || 0) * 100)
  
  const color = confidence >= 0.75 ? 'var(--green)'
              : confidence >= 0.50 ? 'var(--yellow)'
              : 'var(--red)'

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <div style={{
        width: '80px',
        height: '6px',
        background: 'var(--border)',
        borderRadius: '3px',
        overflow: 'hidden',
        position: 'relative',
      }}>
        <div style={{
          position: 'absolute',
          left: 0, top: 0, bottom: 0,
          width: `${Math.max(pct, 3)}%`,
          background: color,
          borderRadius: '3px',
          transition: 'width 0.5s ease',
        }} />
      </div>
      <span style={{
        fontSize: '11px',
        color: color,
        fontWeight: 600,
        minWidth: '28px',
      }}>
        {pct}%
      </span>
    </div>
  )
}

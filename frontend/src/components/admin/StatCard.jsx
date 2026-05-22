export default function StatCard({ label, value, sublabel, color, icon }) {
  return (
    <div style={{
      background: 'var(--panel)',
      border: '1px solid var(--border)',
      borderTop: `3px solid ${color}`,
      borderRadius: '10px',
      padding: '20px 24px',
      display: 'flex',
      flexDirection: 'column'
    }}>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '8px' }}>
        <div style={{ fontSize: '20px', color }}>{icon}</div>
      </div>
      
      <div style={{ fontFamily: 'var(--display)', fontSize: '28px', fontWeight: 800, color, lineHeight: 1 }}>
        {value}
      </div>
      
      <div style={{ fontSize: '11px', letterSpacing: '1.5px', textTransform: 'uppercase', color: 'var(--text3)', marginTop: '6px' }}>
        {label}
      </div>
      
      {sublabel && (
        <div style={{ fontSize: '11px', color: 'var(--text2)', marginTop: '4px' }}>
          {sublabel}
        </div>
      )}
    </div>
  )
}

export default function StatCard({ label, value, sublabel, color, icon }) {
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderTop: `4px solid ${color}`,
      borderRadius: 'var(--radius-lg)',
      padding: '24px',
      display: 'flex',
      flexDirection: 'column',
      boxShadow: 'var(--shadow-sm)'
    }}>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '8px' }}>
        <div style={{ fontSize: '20px', color }}>{icon}</div>
      </div>
      
      <div style={{ fontFamily: 'var(--font-heading)', fontSize: '32px', color, lineHeight: 1 }}>
        {value}
      </div>
      
      <div style={{ fontSize: '11px', letterSpacing: '1px', textTransform: 'uppercase', fontWeight: 600, color: 'var(--text-muted)', marginTop: '12px' }}>
        {label}
      </div>
      
      {sublabel && (
        <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
          {sublabel}
        </div>
      )}
    </div>
  )
}

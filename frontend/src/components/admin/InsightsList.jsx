export default function InsightsList({ stats }) {
  const agent6_insights = stats?.agent6_insights || 0
  const top_gaps = stats?.top_gaps || []

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)',
      overflow: 'hidden',
      boxShadow: 'var(--shadow-sm)'
    }}>
      <div style={{
        padding: '24px',
        borderBottom: '1px solid var(--border-light)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <h2 style={{ fontFamily: 'var(--font-heading)', fontSize: '20px', color: 'var(--text-primary)' }}>
          Agent 6 Insights
        </h2>
        
        <div style={{ background: 'var(--accent-blue-light)', color: 'var(--accent-blue)', padding: '4px 12px', borderRadius: 'var(--radius-lg)', fontSize: '12px', fontWeight: 600 }}>
          {agent6_insights} insights
        </div>
      </div>

      <div style={{ padding: '24px' }}>
        <div style={{ color: 'var(--text-muted)', fontSize: '11px', textTransform: 'uppercase', marginBottom: '16px', fontWeight: 600, letterSpacing: '1px' }}>
          TOP COVERAGE GAPS
        </div>

        {top_gaps.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: '13px', textAlign: 'center', padding: '24px 0' }}>
            Agent 6 is learning from queries...<br/>
            Insights will appear after more queries
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', paddingBottom: '12px' }}>
            {top_gaps.map((gap, i) => {
              const maxCount = top_gaps[0].count
              const percentage = Math.max(10, (gap.count / maxCount) * 100)
              
              return (
                <div key={i}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontSize: '13px', color: 'var(--text-primary)', fontWeight: 500 }}>{gap.topic}</span>
                    <span style={{ background: 'var(--danger-bg)', color: 'var(--danger)', fontSize: '11px', padding: '2px 8px', borderRadius: 'var(--radius-sm)', fontWeight: 600 }}>
                      {gap.count} queries
                    </span>
                  </div>
                  <div style={{ width: '100%', height: '6px', background: 'var(--border-light)', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ width: `${percentage}%`, height: '100%', background: 'var(--danger)', opacity: 0.8 }} />
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

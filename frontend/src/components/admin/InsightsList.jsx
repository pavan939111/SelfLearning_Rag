export default function InsightsList({ stats }) {
  const agent6_insights = stats?.agent6_insights || 0
  const top_gaps = stats?.top_gaps || []

  return (
    <div style={{
      background: 'var(--bg2)',
      border: '1px solid var(--border)',
      borderRadius: '12px',
      overflow: 'hidden'
    }}>
      <div style={{
        padding: '18px 20px',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <h2 style={{ fontFamily: 'var(--display)', fontSize: '15px', fontWeight: 700, color: 'var(--text)' }}>
          Agent 6 Insights
        </h2>
        
        <div style={{ background: 'rgba(168,85,247,0.1)', color: 'var(--purple)', padding: '2px 8px', borderRadius: '10px', fontSize: '11px', fontWeight: 600 }}>
          {agent6_insights} insights
        </div>
      </div>

      <div style={{ padding: '16px 20px 8px' }}>
        <div style={{ color: 'var(--text3)', fontSize: '10px', textTransform: 'uppercase', marginBottom: '16px', fontWeight: 600 }}>
          TOP COVERAGE GAPS
        </div>

        {top_gaps.length === 0 ? (
          <div style={{ color: 'var(--text3)', fontSize: '12px', textAlign: 'center', padding: '20px 0' }}>
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
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <span style={{ fontSize: '12px', color: 'var(--text)' }}>{gap.topic}</span>
                    <span style={{ background: 'rgba(255,77,109,0.1)', color: 'var(--red)', fontSize: '10px', padding: '2px 6px', borderRadius: '4px', fontWeight: 600 }}>
                      {gap.count} queries
                    </span>
                  </div>
                  <div style={{ width: '100%', height: '4px', background: 'var(--border)', borderRadius: '2px', overflow: 'hidden' }}>
                    <div style={{ width: `${percentage}%`, height: '100%', background: 'var(--red)', opacity: 0.8 }} />
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

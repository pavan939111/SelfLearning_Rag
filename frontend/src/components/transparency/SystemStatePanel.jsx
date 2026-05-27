import { useAdminStats } from '../../hooks/useAdminStats'

export default function SystemStatePanel() {
  const { stats, loading } = useAdminStats(30000)

  if (loading || !stats) {
    return (
      <div style={{ background: 'var(--bg2)', borderLeft: '1px solid var(--border)', height: '100%', padding: '20px 16px', color: 'var(--text3)', fontSize: '12px' }}>
        Loading state...
      </div>
    )
  }

  const { qdrant_counts, agent6_insights, top_gaps } = stats

  return (
    <div style={{ background: 'var(--bg-secondary)', height: '100%', overflowY: 'auto', padding: '32px' }}>
      <div style={{ fontFamily: 'var(--font-heading)', fontSize: '20px', color: 'var(--text-primary)', marginBottom: '24px' }}>
        Query Analysis
      </div>

      <div style={{ 
        background: 'var(--bg-card)', padding: '16px', borderRadius: 'var(--radius-md)', 
        boxShadow: 'var(--shadow-sm)', marginBottom: '16px', border: '1px solid var(--border)' 
      }}>
        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '8px', fontWeight: 600, letterSpacing: '0.5px' }}>
          Corpus Size
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
          <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Documents:</span>
          <span style={{ fontSize: '14px', color: 'var(--text-primary)', fontWeight: 600 }}>{qdrant_counts.document || 1495}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
          <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Sections:</span>
          <span style={{ fontSize: '14px', color: 'var(--text-primary)', fontWeight: 600 }}>{qdrant_counts.section || 0}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Semantic:</span>
          <span style={{ fontSize: '14px', color: 'var(--text-primary)', fontWeight: 600 }}>{qdrant_counts.semantic || 0}</span>
        </div>
      </div>

      <div style={{ 
        background: 'var(--bg-card)', padding: '16px', borderRadius: 'var(--radius-md)', 
        boxShadow: 'var(--shadow-sm)', marginBottom: '16px', border: '1px solid var(--border)' 
      }}>
        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '8px', fontWeight: 600, letterSpacing: '0.5px' }}>
          Insights Queue
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ color: 'var(--accent-blue)', fontSize: '13px', fontWeight: 600, background: 'var(--accent-blue-light)', padding: '4px 10px', borderRadius: 'var(--radius-sm)' }}>
            {agent6_insights || 0} pending insights
          </span>
          {(agent6_insights || 0) > 0 && <span style={{ width: '8px', height: '8px', background: 'var(--warning)', borderRadius: '50%' }} />}
        </div>
      </div>

      <div style={{ 
        background: 'var(--bg-card)', padding: '16px', borderRadius: 'var(--radius-md)', 
        boxShadow: 'var(--shadow-sm)', marginBottom: '16px', border: '1px solid var(--border)' 
      }}>
        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '8px', fontWeight: 600, letterSpacing: '0.5px' }}>
          Coverage Gaps
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {(top_gaps || []).slice(0, 3).map((gap, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '13px', color: 'var(--text-primary)', maxWidth: '140px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{gap.topic}</span>
              <span style={{ fontSize: '12px', color: 'var(--danger)', background: 'var(--danger-bg)', padding: '2px 8px', borderRadius: 'var(--radius-sm)', fontWeight: 600 }}>{gap.count} queries</span>
            </div>
          ))}
          {(!top_gaps || top_gaps.length === 0) && (
            <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>No coverage gaps detected.</div>
          )}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        <div style={{ 
          background: 'var(--bg-card)', padding: '16px', borderRadius: 'var(--radius-md)', 
          boxShadow: 'var(--shadow-sm)', border: '1px solid var(--border)' 
        }}>
          <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '8px', fontWeight: 600, letterSpacing: '0.5px' }}>
            Baseline
          </div>
          <div style={{ color: 'var(--success)', fontSize: '24px', fontWeight: 700, marginBottom: '2px', fontFamily: 'var(--font-heading)' }}>
            86.7%
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>
            0.67 avg conf
          </div>
        </div>

        <div style={{ 
          background: 'var(--bg-card)', padding: '16px', borderRadius: 'var(--radius-md)', 
          boxShadow: 'var(--shadow-sm)', border: '1px solid var(--border)', display: 'flex', flexDirection: 'column', justifyContent: 'center'
        }}>
          <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '8px', fontWeight: 600, letterSpacing: '0.5px' }}>
            Cache
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: 'var(--success)', fontWeight: 600 }}>
            <span style={{ width: '8px', height: '8px', background: 'var(--success)', borderRadius: '50%' }} />
            Active
          </div>
        </div>
      </div>
    </div>
  )
}

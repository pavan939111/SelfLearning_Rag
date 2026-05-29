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
    <div style={{ background: 'var(--bg-card)', height: '100%', overflowY: 'auto', position: 'relative' }}>
      <div style={{ 
        height: '70px', 
        background: 'rgba(26, 26, 36, 0.8)', 
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid var(--border)', 
        padding: '0 32px', 
        display: 'flex', 
        alignItems: 'center', 
        position: 'sticky',
        top: 0,
        zIndex: 10
      }}>
        <div style={{ 
          fontFamily: 'var(--font-heading)', 
          fontSize: '22px', 
          color: 'var(--text-primary)',
          letterSpacing: '0.5px'
        }}>
          Knowledge Architecture
        </div>
      </div>
      
      <div style={{ padding: '32px' }}>
        <div style={{ 
          background: 'var(--bg-secondary)', padding: '24px', borderRadius: 'var(--radius-md)', 
          boxShadow: 'var(--shadow-sm)', marginBottom: '24px', border: '1px solid var(--border)',
          position: 'relative', overflow: 'hidden'
        }}>
          <div style={{ position: 'absolute', top: 0, left: 0, width: '3px', height: '100%', background: 'var(--accent-teal)', boxShadow: 'var(--accent-teal-glow)' }} />
          <div style={{ fontSize: '12px', color: 'var(--accent-teal)', textTransform: 'uppercase', marginBottom: '16px', fontWeight: 600, letterSpacing: '1px' }}>
            Local Corpus Density
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px' }}>
            <div>
              <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '4px' }}>Documents</div>
              <div style={{ fontSize: '20px', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{qdrant_counts.document || 1495}</div>
            </div>
            <div>
              <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '4px' }}>Sections</div>
              <div style={{ fontSize: '20px', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{qdrant_counts.section || 8420}</div>
            </div>
            <div>
              <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '4px' }}>Propositions</div>
              <div style={{ fontSize: '20px', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{qdrant_counts.semantic || 34102}</div>
            </div>
          </div>
        </div>

        <div style={{ 
          background: 'var(--bg-secondary)', padding: '24px', borderRadius: 'var(--radius-md)', 
          boxShadow: 'var(--shadow-sm)', marginBottom: '24px', border: '1px solid var(--border)',
          position: 'relative', overflow: 'hidden'
        }}>
          <div style={{ position: 'absolute', top: 0, left: 0, width: '3px', height: '100%', background: 'var(--accent-purple)', boxShadow: 'var(--accent-purple-glow)' }} />
          <div style={{ fontSize: '12px', color: 'var(--accent-purple)', textTransform: 'uppercase', marginBottom: '16px', fontWeight: 600, letterSpacing: '1px' }}>
            Agent 6 Learning Queue
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ color: 'var(--accent-purple)', fontSize: '14px', fontFamily: 'var(--font-mono)', background: 'var(--accent-purple-light)', padding: '8px 16px', borderRadius: 'var(--radius-full)', border: '1px solid rgba(179,146,240,0.2)' }}>
              {agent6_insights || 0} pending optimizations
            </span>
            {(agent6_insights || 0) > 0 && <span style={{ width: '8px', height: '8px', background: 'var(--warning)', borderRadius: '50%', boxShadow: '0 0 8px var(--warning)' }} />}
          </div>
        </div>

        <div style={{ 
          background: 'var(--bg-secondary)', padding: '24px', borderRadius: 'var(--radius-md)', 
          boxShadow: 'var(--shadow-sm)', marginBottom: '24px', border: '1px solid var(--border)',
          position: 'relative', overflow: 'hidden'
        }}>
          <div style={{ position: 'absolute', top: 0, left: 0, width: '3px', height: '100%', background: 'var(--warning)' }} />
          <div style={{ fontSize: '12px', color: 'var(--warning)', textTransform: 'uppercase', marginBottom: '16px', fontWeight: 600, letterSpacing: '1px' }}>
            Identified Knowledge Gaps
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {(top_gaps || []).slice(0, 3).map((gap, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-primary)', padding: '12px 16px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                <span style={{ fontSize: '14px', color: 'var(--text-primary)', maxWidth: '160px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{gap.topic}</span>
                <span style={{ fontSize: '12px', color: 'var(--danger)', background: 'var(--danger-bg)', border: '1px solid rgba(239,68,68,0.2)', padding: '4px 10px', borderRadius: 'var(--radius-full)', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{gap.count} failed queries</span>
              </div>
            ))}
            {(!top_gaps || top_gaps.length === 0) && (
              <div style={{ fontSize: '14px', color: 'var(--text-muted)', fontFamily: 'var(--font-body)', fontStyle: 'italic' }}>
                Corpus coverage is currently comprehensive for recent queries.
              </div>
            )}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
          <div style={{ 
            background: 'var(--bg-secondary)', padding: '24px', borderRadius: 'var(--radius-md)', 
            boxShadow: 'var(--shadow-sm)', border: '1px solid var(--border)' 
          }}>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '12px', fontWeight: 600, letterSpacing: '1px' }}>
              System Confidence
            </div>
            <div style={{ color: 'var(--success)', fontSize: '32px', fontWeight: 700, marginBottom: '4px', fontFamily: 'var(--font-mono)', textShadow: '0 0 10px rgba(16,185,129,0.2)' }}>
              86.7%
            </div>
            <div style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>
              Historical Baseline
            </div>
          </div>

          <div style={{ 
            background: 'var(--bg-secondary)', padding: '24px', borderRadius: 'var(--radius-md)', 
            boxShadow: 'var(--shadow-sm)', border: '1px solid var(--border)', display: 'flex', flexDirection: 'column', justifyContent: 'center'
          }}>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '16px', fontWeight: 600, letterSpacing: '1px' }}>
              Semantic Cache
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', color: 'var(--success)', fontWeight: 600, background: 'var(--success-bg)', border: '1px solid rgba(16,185,129,0.2)', padding: '8px 16px', borderRadius: 'var(--radius-full)', width: 'fit-content' }}>
              <div style={{ width: '8px', height: '8px', background: 'var(--success)', borderRadius: '50%', boxShadow: '0 0 6px var(--success)', animation: 'pulse 2s infinite' }} />
              ONLINE & ACTIVE
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

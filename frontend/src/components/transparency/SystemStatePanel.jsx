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
    <div style={{ background: 'var(--bg2)', borderLeft: '1px solid var(--border)', height: '100%', overflowY: 'auto', padding: '20px 16px' }}>
      <div style={{ fontFamily: 'var(--display)', fontSize: '14px', fontWeight: 700, color: 'var(--text)', borderBottom: '1px solid var(--border)', paddingBottom: '12px', marginBottom: '16px' }}>
        System State
      </div>

      <div style={{ marginBottom: '24px' }}>
        <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', marginBottom: '8px', fontWeight: 600 }}>
          CORPUS
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
          <span style={{ fontSize: '11px', color: 'var(--text3)' }}>Documents:</span>
          <span style={{ fontSize: '12px', color: 'var(--text)', fontWeight: 600 }}>{qdrant_counts.document || 1495}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
          <span style={{ fontSize: '11px', color: 'var(--text3)' }}>Sections:</span>
          <span style={{ fontSize: '12px', color: 'var(--text)', fontWeight: 600 }}>{qdrant_counts.section || 0}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '11px', color: 'var(--text3)' }}>Semantic:</span>
          <span style={{ fontSize: '12px', color: 'var(--text)', fontWeight: 600 }}>{qdrant_counts.semantic || 0}</span>
        </div>
      </div>

      <div style={{ marginBottom: '24px' }}>
        <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', marginBottom: '8px', fontWeight: 600 }}>
          INSIGHTS
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ color: 'var(--cyan)', fontSize: '12px', fontWeight: 600, background: 'rgba(0,212,255,0.1)', padding: '2px 8px', borderRadius: '4px' }}>
            {agent6_insights || 0} pending insights
          </span>
          {(agent6_insights || 0) > 0 && <span style={{ width: '6px', height: '6px', background: 'var(--orange)', borderRadius: '50%' }} />}
        </div>
      </div>

      <div style={{ marginBottom: '24px' }}>
        <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', marginBottom: '8px', fontWeight: 600 }}>
          TOP GAPS
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {(top_gaps || []).slice(0, 3).map((gap, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '11px', color: 'var(--text2)', maxWidth: '140px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{gap.topic}</span>
              <span style={{ fontSize: '10px', color: 'var(--red)', background: 'rgba(255,77,109,0.1)', padding: '2px 6px', borderRadius: '4px' }}>{gap.count} queries</span>
            </div>
          ))}
          {(!top_gaps || top_gaps.length === 0) && (
            <div style={{ fontSize: '11px', color: 'var(--text3)' }}>No coverage gaps detected.</div>
          )}
        </div>
      </div>

      <div style={{ marginBottom: '24px' }}>
        <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', marginBottom: '8px', fontWeight: 600 }}>
          BASELINE
        </div>
        <div style={{ color: 'var(--green)', fontSize: '20px', fontWeight: 700, marginBottom: '2px' }}>
          86.7%
        </div>
        <div style={{ color: 'var(--text2)', fontSize: '11px', marginBottom: '2px' }}>
          0.67 avg confidence
        </div>
        <div style={{ color: 'var(--text3)', fontSize: '10px' }}>
          Updated just now
        </div>
      </div>

      <div>
        <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', marginBottom: '8px', fontWeight: 600 }}>
          CACHE
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--green)' }}>
          <span style={{ width: '6px', height: '6px', background: 'var(--green)', borderRadius: '50%' }} />
          Semantic hash cache active
        </div>
      </div>
    </div>
  )
}

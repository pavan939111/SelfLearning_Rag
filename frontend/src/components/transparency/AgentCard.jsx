import { motion } from 'framer-motion'
import LoadingSpinner from '../shared/LoadingSpinner'

export default function AgentCard({ event }) {
  const AGENT_COLORS = {
    cache:   '#00d4ff',
    agent1:  '#4a9eff',
    agent2:  '#00d4ff',
    agent3:  '#ffd60a',
    agent4a: '#ff8c42',
    agent4b: '#a855f7',
    agent7:  '#00e5a0',
    system:  '#6b7d9e',
  }

  const AGENT_NAMES = {
    cache:   'Cache',
    agent1:  'Agent 1 — Retrieval',
    agent2:  'Agent 2 — Quality Gate',
    agent3:  'Agent 3 — Diagnosis',
    agent4a: 'Agent 4A — Repair',
    agent4b: 'Agent 4B — BG Repair',
    agent7:  'Agent 7 — Generator',
    system:  'System',
  }

  const color = AGENT_COLORS[event.agent] || '#00d4ff'
  const displayName = AGENT_NAMES[event.agent] || event.agent

  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      style={{
        background: 'var(--bg3)',
        border: '1px solid var(--border)',
        borderLeft: `3px solid ${color}`,
        borderRadius: '8px',
        padding: '12px 16px',
        marginBottom: '8px'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div style={{
            border: `1px solid ${color}`,
            color: color,
            padding: '2px 8px',
            borderRadius: '4px',
            fontSize: '10px',
            fontWeight: 600,
            textTransform: 'uppercase'
          }}>
            {displayName}
          </div>
          <div style={{ color: 'var(--text2)', fontSize: '12px', marginLeft: '8px' }}>
            {event.step}
          </div>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {event.status === 'running' && <LoadingSpinner />}
          {event.status === 'complete' && <span style={{ color: 'var(--green)' }}>✓</span>}
          {event.status === 'fail' && <span style={{ color: 'var(--red)' }}>✗</span>}
          {event.status === 'info' && <span style={{ color: 'var(--text3)' }}>ℹ</span>}
          {event.status === 'pass' && <span style={{ color: 'var(--green)', fontSize: '10px', fontWeight: 600 }}>✓ PASS</span>}
          
          {event.duration_ms !== undefined && event.duration_ms > 0 && (
            <div style={{ color: 'var(--text3)', fontSize: '10px' }}>
              {event.duration_ms}ms
            </div>
          )}
        </div>
      </div>

      <div style={{ color: 'var(--text2)', fontSize: '11px', marginTop: '6px', lineHeight: 1.5 }}>
        {event.detail}
      </div>

      {event.checks && event.checks.length > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '4px',
          marginTop: '8px',
        }}>
          {event.checks.map((check, i) => (
            <div key={i} style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '10px',
              color: check.passed ? 'var(--green)' : 'var(--red)',
            }}>
              <span>{check.passed ? '✓' : '✗'}</span>
              <span style={{ color: 'var(--text3)' }}>
                {check.name.replace('_', ' ')}
              </span>
              <span style={{ marginLeft: 'auto' }}>
                {(check.score * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  )
}

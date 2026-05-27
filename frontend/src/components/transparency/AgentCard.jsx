import { motion } from 'framer-motion'
import LoadingSpinner from '../shared/LoadingSpinner'

export default function AgentCard({ event }) {
  const AGENT_COLORS = {
    cache:   'var(--accent-teal)',
    agent1:  'var(--accent-blue)',
    agent2:  'var(--accent-teal)',
    agent3:  'var(--warning)',
    agent4a: 'var(--warning)',
    agent4b: 'var(--warning)',
    agent7:  'var(--success)',
    system:  'var(--text-muted)',
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

  const isRepair = event.agent === 'agent4a' || event.agent === 'agent4b'
  const bgColor = isRepair ? 'var(--warning-bg)' : 'var(--bg-card)'

  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      style={{
        background: bgColor,
        border: '1px solid var(--border)',
        borderLeft: `4px solid ${color}`,
        borderRadius: 'var(--radius-sm)',
        padding: '16px',
        marginBottom: '12px',
        boxShadow: 'var(--shadow-sm)'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div style={{
            color: color,
            padding: '2px 8px',
            borderRadius: '4px',
            fontSize: '11px',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.5px'
          }}>
            {displayName}
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '12px', marginLeft: '8px' }}>
            {event.step}
          </div>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {event.status === 'running' && (
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-blue)', animation: 'pulse 1.5s infinite' }} />
          )}
          {event.status === 'complete' && <span style={{ color: 'var(--success)' }}>✓</span>}
          {event.status === 'fail' && <span style={{ color: 'var(--danger)' }}>✗</span>}
          {event.status === 'info' && <span style={{ color: 'var(--text-muted)' }}>ℹ</span>}
          {event.status === 'pass' && <span style={{ color: 'var(--success)', fontSize: '11px', fontWeight: 600 }}>✓ PASS</span>}
          
          {event.duration_ms !== undefined && event.duration_ms > 0 && (
            <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
              {event.duration_ms}ms
            </div>
          )}
        </div>
      </div>

      <div style={{ color: 'var(--text-primary)', fontSize: '13px', marginTop: '8px', lineHeight: 1.6 }}>
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
              fontSize: '11px',
              color: check.passed ? 'var(--success)' : 'var(--danger)',
            }}>
              <span>{check.passed ? '✓' : '✗'}</span>
              <span style={{ color: 'var(--text-secondary)' }}>
                {check.name.replace('_', ' ')}
              </span>
              <span style={{ marginLeft: 'auto', fontWeight: 600 }}>
                {(check.score * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  )
}

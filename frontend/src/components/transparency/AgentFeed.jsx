import { useEffect, useRef, useState } from 'react'
import AgentCard from './AgentCard'
import { ThoughtTraceCard } from './ThoughtTraceCard'

export default function AgentFeed({ events, streaming }) {
  const endRef = useRef(null)
  const [showReasoning, setShowReasoning] = useState(false)

  useEffect(() => {
    if (endRef.current) {
      endRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [events])

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{
        height: '72px',
        background: 'var(--bg-card)',
        borderBottom: '1px solid var(--border)',
        padding: '0 32px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0,
        boxShadow: 'var(--shadow-sm)'
      }}>
        <div style={{ fontFamily: 'var(--font-heading)', fontSize: '20px', color: 'var(--text-primary)' }}>
          Agent Activity
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--text-secondary)' }}>
          {streaming ? (
            <>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-blue)', boxShadow: '0 0 6px var(--accent-blue)', animation: 'pulse 1.5s infinite' }} />
              Processing...
            </>
          ) : events.length > 0 ? (
            <>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--success)' }} />
              Complete
            </>
          ) : (
            <>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--text-muted)' }} />
              Waiting for query
            </>
          )}
          
          <button
            onClick={() => setShowReasoning(!showReasoning)}
            style={{
              marginLeft: '16px',
              padding: '6px 12px',
              borderRadius: 'var(--radius-sm)',
              fontSize: '11px',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '1px',
              border: '1px solid',
              transition: 'all 0.2s',
              backgroundColor: showReasoning ? 'var(--bg-sidebar)' : 'transparent',
              borderColor: showReasoning ? 'var(--bg-sidebar)' : 'var(--border)',
              color: showReasoning ? '#FFFFFF' : 'var(--text-secondary)'
            }}
          >
            {showReasoning ? 'Reasoning ON' : 'Reasoning OFF'}
          </button>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
        {events.length === 0 && !streaming && (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            gap: '16px',
            color: 'var(--text-muted)',
            padding: '40px',
            textAlign: 'center',
          }}>
            <div style={{
              fontSize: '40px',
              opacity: 0.4,
            }}>⚙️</div>
            <div>
              <div style={{
                fontFamily: 'var(--font-heading)',
                fontSize: '20px',
                color: 'var(--text-secondary)',
                marginBottom: '6px',
              }}>
                Agent Activity Feed
              </div>
              <div style={{ fontSize: '14px', lineHeight: 1.6, color: 'var(--text-secondary)' }}>
                Send a query in the chat panel to watch<br/>
                the nine agents work in real time
              </div>
            </div>
            
            {/* Agent legend */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '6px',
              marginTop: '16px',
              width: '100%',
              maxWidth: '320px',
            }}>
              {[
                { name: 'Agent 1 — Retrieval', color: 'var(--accent-blue)' },
                { name: 'Agent 2 — Quality Gate', color: 'var(--accent-teal)' },
                { name: 'Agent 3 — Diagnosis', color: 'var(--warning)' },
                { name: 'Agent 4A — Repair', color: 'var(--warning)' },
                { name: 'Agent 7 — Generator', color: 'var(--success)' },
                { name: 'Cache Check', color: 'var(--accent-teal)' },
              ].map((a, i) => (
                <div key={i} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '11px',
                  color: 'var(--text-secondary)',
                  padding: '8px 12px',
                  background: 'var(--bg-primary)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border)',
                  borderLeft: `3px solid ${a.color}`,
                }}>
                  {a.name}
                </div>
              ))}
            </div>
          </div>
        )}
        
        {events.map((evt) => {
          if (evt.type === 'thought') {
            if (!showReasoning) return null
            return <ThoughtTraceCard key={evt.id} trace={evt} />
          }
          return <AgentCard key={evt.id} event={evt} />
        })}
        
        <div ref={endRef} />
      </div>
    </div>
  )
}

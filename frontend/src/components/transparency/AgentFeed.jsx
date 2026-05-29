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
        height: '70px',
        background: 'rgba(26, 26, 36, 0.8)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid var(--border)',
        padding: '0 32px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0,
        zIndex: 10
      }}>
        <div style={{ 
          fontFamily: 'var(--font-heading)', 
          fontSize: '22px', 
          color: 'var(--text-primary)',
          letterSpacing: '0.5px'
        }}>
          Multi-Agent Telemetry
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--text-secondary)' }}>
          {streaming ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'var(--accent-teal-light)', padding: '6px 12px', borderRadius: 'var(--radius-full)', border: '1px solid rgba(100,255,218,0.2)' }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-teal)', boxShadow: '0 0 10px var(--accent-teal)', animation: 'pulse 1.5s infinite' }} />
              <span style={{ color: 'var(--accent-teal)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>PROCESSING</span>
            </div>
          ) : events.length > 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'var(--bg-primary)', padding: '6px 12px', borderRadius: 'var(--radius-full)', border: '1px solid var(--border)' }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--success)' }} />
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>IDLE</span>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'var(--bg-primary)', padding: '6px 12px', borderRadius: 'var(--radius-full)', border: '1px dashed var(--border-light)' }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--text-muted)' }} />
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>WAITING</span>
            </div>
          )}
          
          <button
            onClick={() => setShowReasoning(!showReasoning)}
            style={{
              marginLeft: '16px',
              padding: '8px 16px',
              borderRadius: 'var(--radius-full)',
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '1px',
              border: '1px solid',
              transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
              backgroundColor: showReasoning ? 'var(--accent-purple-light)' : 'var(--bg-primary)',
              borderColor: showReasoning ? 'rgba(179,146,240,0.3)' : 'var(--border)',
              color: showReasoning ? 'var(--accent-purple)' : 'var(--text-secondary)',
              cursor: 'pointer'
            }}
          >
            {showReasoning ? '🧠 Trace ON' : '🧠 Trace OFF'}
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

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
        height: '48px',
        background: 'var(--bg2)',
        borderBottom: '1px solid var(--border)',
        padding: '0 20px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0
      }}>
        <div style={{ fontFamily: 'var(--display)', fontSize: '14px', fontWeight: 700, color: 'var(--text)' }}>
          Agent Activity
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: 'var(--text3)' }}>
          {streaming ? (
            <>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--cyan)', boxShadow: '0 0 6px var(--cyan)', animation: 'pulse 1.5s infinite' }} />
              Processing...
            </>
          ) : events.length > 0 ? (
            <>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--green)' }} />
              Complete
            </>
          ) : (
            <>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--text3)' }} />
              Waiting for query
            </>
          )}
          
          <button
            onClick={() => setShowReasoning(!showReasoning)}
            className={`ml-4 px-2 py-1 rounded text-xs font-semibold uppercase tracking-wider border transition-colors ${
              showReasoning 
                ? 'bg-slate-700 border-slate-500 text-slate-200' 
                : 'bg-transparent border-slate-700 text-slate-500 hover:text-slate-300'
            }`}
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
            color: 'var(--text3)',
            padding: '40px',
            textAlign: 'center',
          }}>
            <div style={{
              fontSize: '40px',
              opacity: 0.4,
            }}>⚙️</div>
            <div>
              <div style={{
                fontFamily: 'var(--display)',
                fontSize: '15px',
                color: 'var(--text2)',
                marginBottom: '6px',
              }}>
                Agent Activity Feed
              </div>
              <div style={{ fontSize: '12px', lineHeight: 1.6 }}>
                Send a query in the left panel to watch<br/>
                the nine agents work in real time
              </div>
            </div>
            
            {/* Agent legend */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '6px',
              marginTop: '8px',
              width: '100%',
              maxWidth: '280px',
            }}>
              {[
                { name: 'Agent 1 — Retrieval', color: '#4a9eff' },
                { name: 'Agent 2 — Quality Gate', color: '#00d4ff' },
                { name: 'Agent 3 — Diagnosis', color: '#ffd60a' },
                { name: 'Agent 4A — Repair', color: '#ff8c42' },
                { name: 'Agent 7 — Generator', color: '#00e5a0' },
                { name: 'Cache Check', color: '#00d4ff' },
              ].map((a, i) => (
                <div key={i} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '10px',
                  color: 'var(--text3)',
                  padding: '5px 8px',
                  background: 'var(--bg3)',
                  borderRadius: '4px',
                  borderLeft: `2px solid ${a.color}`,
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

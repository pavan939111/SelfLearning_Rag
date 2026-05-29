import { useState } from 'react'
import ConfidenceBar from '../chat/ConfidenceBar'
import LoadingSpinner from '../shared/LoadingSpinner'

export default function MiniChat({ onQuery, answer, streaming }) {
  const [text, setText] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!text.trim() || streaming) return
    onQuery(text)
    setText('')
  }

  return (
    <div style={{ background: 'var(--bg-card)', height: '100%', display: 'flex', flexDirection: 'column', position: 'relative' }}>
      <div style={{ 
        height: '70px', 
        background: 'rgba(26, 26, 36, 0.8)', 
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid var(--border)', 
        padding: '0 24px', 
        display: 'flex', 
        alignItems: 'center', 
        flexShrink: 0,
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
          Live Pipeline Query
        </div>
        <div style={{
          marginLeft: 'auto',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          background: 'var(--accent-teal-light)',
          padding: '4px 12px',
          borderRadius: 'var(--radius-full)',
          border: '1px solid rgba(100,255,218,0.2)'
        }}>
          <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-teal)', boxShadow: 'var(--accent-teal-glow)' }} />
          <span style={{ fontSize: '12px', color: 'var(--accent-teal)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>ONLINE</span>
        </div>
      </div>
      
      <div style={{ flex: 1, overflowY: 'auto', padding: '24px', paddingBottom: '100px' }}>
        {!answer && !streaming && (
          <div style={{ 
            color: 'var(--text-muted)', 
            fontSize: '15px', 
            textAlign: 'center', 
            marginTop: '80px',
            fontFamily: 'var(--font-body)',
            padding: '40px 20px',
            background: 'var(--bg-secondary)',
            borderRadius: 'var(--radius-md)',
            border: '1px dashed var(--border-light)'
          }}>
            <div style={{ fontSize: '24px', marginBottom: '12px' }}>🧬</div>
            Ask a clinical question to monitor agent interactions and retrieval pathways in real-time.
          </div>
        )}

        {streaming && (
          <div style={{ 
            display: 'flex', gap: '12px', alignItems: 'center', 
            color: 'var(--accent-teal)', fontSize: '14px', 
            fontFamily: 'var(--font-mono)',
            padding: '16px', background: 'var(--accent-teal-light)',
            borderRadius: 'var(--radius-md)', border: '1px solid rgba(100, 255, 218, 0.2)'
          }}>
            <LoadingSpinner size={18} color="var(--accent-teal)" /> Agents active...
          </div>
        )}

        {answer && !streaming && (
          <div style={{
            background: 'var(--bg-secondary)',
            padding: '24px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border)',
            boxShadow: 'var(--shadow-sm)'
          }}>
            <div style={{ fontSize: '15px', lineHeight: 1.7, color: 'var(--text-primary)', marginBottom: '24px' }}>
              {answer.answer}
            </div>

            <div style={{ marginBottom: '24px' }}>
              <ConfidenceBar confidence={answer.confidence} />
            </div>

            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {answer.processing_time_ms && (
                <div style={{ 
                  color: 'var(--text-secondary)', fontSize: '12px', fontFamily: 'var(--font-mono)',
                  background: 'var(--bg-primary)', padding: '6px 10px', borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-light)'
                }}>
                  ⏱️ {(answer.processing_time_ms / 1000).toFixed(1)}s
                </div>
              )}
              {answer.cache_hit && (
                <div style={{ 
                  color: 'var(--accent-teal)', fontSize: '12px', fontFamily: 'var(--font-mono)',
                  background: 'var(--accent-teal-light)', padding: '6px 10px', borderRadius: 'var(--radius-sm)',
                  border: '1px solid rgba(100, 255, 218, 0.2)'
                }}>
                  ⚡ Cached
                </div>
              )}
              {answer.cycle_ran && (
                <div style={{ 
                  color: 'var(--warning)', fontSize: '12px', fontFamily: 'var(--font-mono)',
                  background: 'var(--warning-bg)', padding: '6px 10px', borderRadius: 'var(--radius-sm)',
                  border: '1px solid rgba(251, 191, 36, 0.2)'
                }}>
                  🔄 Autonomous Repair
                </div>
              )}
            </div>

            {answer.citations && answer.citations.length > 0 && (
              <div style={{ marginTop: '24px', borderTop: '1px solid var(--border)', paddingTop: '20px' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '16px', letterSpacing: '1px', fontWeight: 600 }}>Verified Sources</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {answer.citations.map((c, i) => (
                    <div key={i} style={{ 
                      fontSize: '13px', color: 'var(--text-secondary)', fontFamily: 'var(--font-body)',
                      background: 'var(--bg-primary)', padding: '12px', borderRadius: 'var(--radius-sm)',
                      borderLeft: '3px solid var(--accent-blue)'
                    }}>
                      <strong style={{ color: 'var(--text-primary)' }}>{c.citation}</strong> — {c.journal} ({c.year})
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div style={{ 
        padding: '24px', 
        background: 'linear-gradient(to top, var(--bg-card) 70%, transparent)',
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 10
      }}>
        <form onSubmit={handleSubmit}>
          <div style={{ position: 'relative' }}>
            <input 
              type="text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={streaming}
              placeholder="Query the biomedical knowledge graph..."
              style={{
                width: '100%',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-full)',
                color: 'var(--text-primary)',
                fontFamily: 'var(--font-body)',
                fontSize: '15px',
                padding: '16px 24px',
                paddingRight: '60px',
                outline: 'none',
                transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                boxShadow: 'var(--shadow-md)',
                boxSizing: 'border-box'
              }}
              onFocus={(e) => {
                e.target.style.borderColor = 'var(--accent-teal)';
                e.target.style.boxShadow = 'var(--accent-teal-glow)';
                e.target.style.background = 'var(--bg-card)';
              }}
              onBlur={(e) => {
                e.target.style.borderColor = 'var(--border)';
                e.target.style.boxShadow = 'var(--shadow-md)';
                e.target.style.background = 'var(--bg-secondary)';
              }}
            />
            <button
              type="submit"
              disabled={streaming || !text.trim()}
              style={{
                position: 'absolute',
                right: '8px',
                top: '50%',
                transform: 'translateY(-50%)',
                background: text.trim() ? 'var(--accent-teal)' : 'var(--bg-primary)',
                color: text.trim() ? '#000' : 'var(--text-muted)',
                border: 'none',
                borderRadius: '50%',
                width: '36px',
                height: '36px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: text.trim() && !streaming ? 'pointer' : 'not-allowed',
                transition: 'all 0.2s ease',
                boxShadow: text.trim() ? '0 2px 8px rgba(100, 255, 218, 0.4)' : 'none'
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

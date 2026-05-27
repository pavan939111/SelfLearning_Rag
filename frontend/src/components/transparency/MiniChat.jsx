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
    <div style={{ background: 'var(--bg-card)', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ 
        height: '60px', 
        background: 'var(--bg-card)', 
        borderBottom: '1px solid var(--border)', 
        padding: '0 24px', 
        display: 'flex', 
        alignItems: 'center', 
        flexShrink: 0 
      }}>
        <div style={{ fontFamily: 'var(--font-heading)', fontSize: '18px', color: 'var(--text-primary)' }}>Live Query</div>
      </div>
      
      <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
        {!answer && !streaming && (
          <div style={{ 
            color: 'var(--text-muted)', 
            fontSize: '14px', 
            textAlign: 'center', 
            marginTop: '60px',
            fontFamily: 'var(--font-body)'
          }}>
            Ask a clinical question to monitor agent interactions.
          </div>
        )}

        {streaming && (
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center', color: 'var(--accent-teal)', fontSize: '14px', fontFamily: 'var(--font-mono)' }}>
            <LoadingSpinner size={16} color="var(--accent-teal)" /> Agents working...
          </div>
        )}

        {answer && !streaming && (
          <div>
            <div style={{ fontSize: '15px', lineHeight: 1.6, color: 'var(--text-primary)', marginBottom: '16px' }}>
              {answer.answer}
            </div>

            <div style={{ marginBottom: '16px' }}>
              <ConfidenceBar confidence={answer.confidence} />
            </div>

            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {answer.processing_time_ms && (
                <div style={{ 
                  color: 'var(--text-secondary)', 
                  fontSize: '12px', 
                  fontFamily: 'var(--font-mono)',
                  background: 'var(--bg-secondary)',
                  padding: '4px 8px',
                  borderRadius: 'var(--radius-sm)'
                }}>
                  {(answer.processing_time_ms / 1000).toFixed(1)}s
                </div>
              )}
              {answer.cache_hit && (
                <div style={{ 
                  color: 'var(--accent-blue)', 
                  fontSize: '12px', 
                  fontFamily: 'var(--font-mono)',
                  background: 'var(--accent-blue-light)', 
                  padding: '4px 8px', 
                  borderRadius: 'var(--radius-sm)' 
                }}>
                  ⚡ Cached
                </div>
              )}
              {answer.cycle_ran && (
                <div style={{ 
                  color: 'var(--warning)', 
                  fontSize: '12px', 
                  fontFamily: 'var(--font-mono)',
                  background: 'var(--warning-bg)', 
                  padding: '4px 8px', 
                  borderRadius: 'var(--radius-sm)' 
                }}>
                  🔄 Repaired
                </div>
              )}
            </div>

            {answer.citations && answer.citations.length > 0 && (
              <div style={{ marginTop: '24px', borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '12px', letterSpacing: '0.5px', fontWeight: 600 }}>Sources</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {answer.citations.map((c, i) => (
                    <div key={i} style={{ fontSize: '12px', color: 'var(--text-secondary)', fontFamily: 'var(--font-body)' }}>
                      <strong>{c.citation}</strong> — {c.journal} ({c.year})
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div style={{ padding: '24px', borderTop: '1px solid var(--border)', background: 'var(--bg-primary)' }}>
        <form onSubmit={handleSubmit}>
          <input 
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={streaming}
            placeholder="Type your query..."
            style={{
              width: '100%',
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-body)',
              fontSize: '14px',
              padding: '14px 16px',
              outline: 'none',
              transition: 'all 0.2s ease',
              boxShadow: 'var(--shadow-sm)',
              boxSizing: 'border-box'
            }}
            onFocus={(e) => {
              e.target.style.borderColor = 'var(--accent-teal)';
              e.target.style.boxShadow = '0 0 0 3px var(--accent-teal-light)';
            }}
            onBlur={(e) => {
              e.target.style.borderColor = 'var(--border)';
              e.target.style.boxShadow = 'var(--shadow-sm)';
            }}
          />
        </form>
      </div>
    </div>
  )
}

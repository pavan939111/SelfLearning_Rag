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
    <div style={{ background: 'var(--bg2)', borderRight: '1px solid var(--border)', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ height: '48px', background: 'var(--bg2)', borderBottom: '1px solid var(--border)', padding: '0 20px', display: 'flex', alignItems: 'center', flexShrink: 0 }}>
        <div style={{ fontFamily: 'var(--display)', fontSize: '14px', color: 'var(--text)' }}>Query</div>
      </div>
      
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
        {!answer && !streaming && (
          <div style={{ color: 'var(--text3)', fontSize: '12px', textAlign: 'center', marginTop: '40px' }}>
            Ask a question to see the agents work
          </div>
        )}

        {streaming && (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', color: 'var(--cyan)', fontSize: '12px' }}>
            Agents working... <LoadingSpinner />
          </div>
        )}

        {answer && !streaming && (
          <div>
            <div style={{ fontSize: '13px', lineHeight: 1.8, color: 'var(--text)' }}>
              {answer.answer}
            </div>

            <div style={{ marginTop: '12px' }}>
              <ConfidenceBar confidence={answer.confidence} />
            </div>

            <div style={{ display: 'flex', gap: '8px', marginTop: '12px', flexWrap: 'wrap' }}>
              {answer.processing_time_ms && (
                <div style={{ color: 'var(--text3)', fontSize: '11px' }}>
                  {(answer.processing_time_ms / 1000).toFixed(1)}s
                </div>
              )}
              {answer.cache_hit && (
                <div style={{ color: 'var(--cyan)', fontSize: '11px', background: 'rgba(0,212,255,0.1)', padding: '2px 8px', borderRadius: '4px' }}>⚡ cached</div>
              )}
              {answer.cycle_ran && (
                <div style={{ color: 'var(--orange)', fontSize: '11px', background: 'rgba(255,140,66,0.1)', padding: '2px 8px', borderRadius: '4px' }}>🔄 repaired</div>
              )}
            </div>

            {answer.citations && answer.citations.length > 0 && (
              <div style={{ marginTop: '16px', borderTop: '1px solid var(--border)', paddingTop: '12px' }}>
                <div style={{ fontSize: '10px', color: 'var(--text3)', textTransform: 'uppercase', marginBottom: '8px' }}>Sources</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {answer.citations.map((c, i) => (
                    <div key={i} style={{ fontSize: '10px', color: 'var(--text3)' }}>
                      {c.citation} | {c.journal} | {c.year}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div style={{ padding: '16px', borderTop: '1px solid var(--border)' }}>
        <form onSubmit={handleSubmit}>
          <input 
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={streaming}
            placeholder="Type query and press Enter..."
            style={{
              width: '100%',
              background: 'var(--panel)',
              border: '1px solid var(--border)',
              borderRadius: '8px',
              color: 'var(--text)',
              fontFamily: 'var(--mono)',
              fontSize: '12px',
              padding: '10px 14px',
              outline: 'none',
              transition: 'border 0.2s',
              boxSizing: 'border-box'
            }}
            onFocus={(e) => e.target.style.borderColor = 'var(--cyan)'}
            onBlur={(e) => e.target.style.borderColor = 'var(--border)'}
          />
        </form>
      </div>
    </div>
  )
}

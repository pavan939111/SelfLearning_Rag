import { useState, useEffect } from 'react'

export function saveSessionToStorage(sessionObj) {
  try {
    const stored = localStorage.getItem('failurerag_sessions')
    let sessions = stored ? JSON.parse(stored) : []
    const existingIndex = sessions.findIndex(s => s.id === sessionObj.id)
    if (existingIndex >= 0) {
      sessions[existingIndex] = sessionObj
    } else {
      sessions.unshift(sessionObj)
    }
    localStorage.setItem('failurerag_sessions', JSON.stringify(sessions))
    window.dispatchEvent(new Event('failurerag_session_update'))
  } catch (e) {
    console.error("Failed to save session", e)
  }
}

export default function SessionSidebar({ currentSessionId, onNewSession, onSelectSession }) {
  const [sessions, setSessions] = useState(() => {
    try {
      const stored = localStorage.getItem('failurerag_sessions')
      return stored ? JSON.parse(stored) : []
    } catch {
      return []
    }
  })

  useEffect(() => {
    const handleStorage = () => {
      const stored = localStorage.getItem('failurerag_sessions')
      if (stored) setSessions(JSON.parse(stored))
    }
    window.addEventListener('failurerag_session_update', handleStorage)
    return () => window.removeEventListener('failurerag_session_update', handleStorage)
  }, [])

  const handleClear = () => {
    if (window.confirm("Are you sure you want to clear all session history?")) {
      localStorage.removeItem('failurerag_sessions')
      setSessions([])
      onNewSession()
    }
  }

  return (
    <div style={{
      width: '260px',
      height: '100%',
      borderRight: '1px solid var(--border)',
      background: 'var(--bg2)',
      display: 'flex',
      flexDirection: 'column'
    }}>
      <div style={{ padding: '20px 16px' }}>
        <button
          onClick={onNewSession}
          style={{
            width: '100%',
            padding: '10px',
            background: 'var(--panel)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            color: 'var(--cyan)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            transition: 'all 0.2s',
            fontWeight: 600
          }}
        >
          <span>+</span> New Session
        </button>
      </div>

      <div style={{
        padding: '0 16px 12px',
        fontSize: '10px',
        textTransform: 'uppercase',
        color: 'var(--text3)',
        letterSpacing: '1px',
        fontWeight: 600
      }}>
        Sessions
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '0 12px' }}>
        {sessions.map(s => {
          const isActive = s.id === currentSessionId
          return (
            <div
              key={s.id}
              onClick={() => onSelectSession(s.id)}
              style={{
                padding: '12px 14px',
                marginBottom: '8px',
                borderRadius: 'var(--radius-sm)',
                background: isActive ? 'var(--panel)' : 'transparent',
                borderLeft: isActive ? '2px solid var(--cyan)' : '2px solid transparent',
                cursor: 'pointer',
                transition: 'background 0.2s',
              }}
              onMouseEnter={(e) => {
                if (!isActive) e.currentTarget.style.background = 'var(--bg3)'
              }}
              onMouseLeave={(e) => {
                if (!isActive) e.currentTarget.style.background = 'transparent'
              }}
            >
              <div style={{ fontSize: '13px', color: isActive ? 'var(--text)' : 'var(--text2)', marginBottom: '4px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {s.firstMessage.length > 40 ? s.firstMessage.substring(0, 40) + '...' : s.firstMessage}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '11px', color: 'var(--text3)' }}>
                <span>{new Date(s.timestamp).toLocaleDateString()}</span>
                <span style={{ background: 'var(--bg)', padding: '2px 6px', borderRadius: '10px' }}>{s.messageCount} msg</span>
              </div>
            </div>
          )
        })}
      </div>

      <div style={{ padding: '16px' }}>
        <button
          onClick={handleClear}
          style={{
            width: '100%',
            padding: '8px',
            background: 'transparent',
            border: 'none',
            color: 'var(--text3)',
            fontSize: '11px',
            transition: 'color 0.2s'
          }}
          onMouseEnter={(e) => e.currentTarget.style.color = 'var(--red)'}
          onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text3)'}
        >
          Clear All Sessions
        </button>
      </div>
    </div>
  )
}

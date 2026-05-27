import { useEffect, useRef, useState } from 'react'
import SessionSidebar, { saveSessionToStorage } from '../components/chat/SessionSidebar'
import MessageBubble from '../components/chat/MessageBubble'
import QueryInput from '../components/chat/QueryInput'
import { useSession } from '../hooks/useSession'
import { useChat } from '../hooks/useChat'
import { Activity } from 'lucide-react'

export default function Chat() {
  const { sessionId, newSession } = useSession()
  const [activeSessionId, setActiveSessionId] = useState(sessionId)
  const { messages, loading, error, send, clearMessages } = useChat(activeSessionId)
  
  const messagesEndRef = useRef(null)

  useEffect(() => {
    setActiveSessionId(sessionId)
    clearMessages()
  }, [sessionId, clearMessages])

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  const handleSend = async (query) => {
    if (messages.length === 0) {
      saveSessionToStorage({
        id: activeSessionId,
        firstMessage: query,
        timestamp: new Date().toISOString(),
        messageCount: 1
      })
    } else {
      const stored = localStorage.getItem('selflearning_rag_sessions')
      if (stored) {
        const sessions = JSON.parse(stored)
        const idx = sessions.findIndex(s => s.id === activeSessionId)
        if (idx >= 0) {
          sessions[idx].messageCount = Math.floor(messages.length / 2) + 1
          localStorage.setItem('selflearning_rag_sessions', JSON.stringify(sessions))
          window.dispatchEvent(new Event('selflearning_rag_session_update'))
        }
      }
    }
    await send(query)
  }

  const handleSelectSession = (id) => {
    setActiveSessionId(id)
    clearMessages()
  }

  const [errorVisible, setErrorVisible] = useState(false)
  useEffect(() => {
    if (error) {
      setErrorVisible(true)
      const timer = setTimeout(() => setErrorVisible(false), 5000)
      return () => clearTimeout(timer)
    }
  }, [error])

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100%', overflow: 'hidden' }}>
      
      {/* Center Panel */}
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, backgroundColor: 'var(--bg-primary)', overflow: 'hidden' }}>
        {/* Header Bar */}
        <div style={{
          height: '72px',
          background: 'var(--bg-card)',
          borderBottom: '1px solid var(--border)',
          padding: '0 32px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          boxShadow: 'var(--shadow-sm)'
        }}>
          <div>
            <h2 style={{ fontFamily: 'var(--font-heading)', color: 'var(--text-primary)', fontSize: '20px', margin: 0 }}>
              Biomedical Research Chat
            </h2>
            <div style={{ color: 'var(--text-secondary)', fontSize: '12px', marginTop: '4px' }}>
              1,767 papers · Immunotherapy · Drug Interactions · Genomics
            </div>
          </div>
          <div style={{ 
            display: 'flex', alignItems: 'center', gap: '6px', 
            background: 'var(--success-bg)', color: 'var(--success)', 
            padding: '4px 10px', borderRadius: 'var(--radius-lg)', 
            fontSize: '12px', fontWeight: 600 
          }}>
            <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--success)' }} />
            Live
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {messages.length === 0 && !loading && (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              flex: 1,
              gap: '24px',
              padding: '40px',
              textAlign: 'center',
            }}>
              
              {/* Logo mark */}
              <div style={{
                width: '64px',
                height: '64px',
                borderRadius: '16px',
                background: 'var(--accent-blue-light)',
                color: 'var(--accent-blue)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '28px',
              }}>
                🧬
              </div>
              
              {/* Title */}
              <div>
                <h2 style={{
                  fontFamily: 'var(--font-heading)',
                  fontSize: '28px',
                  color: 'var(--text-primary)',
                  marginBottom: '8px',
                }}>
                  Clinical Intelligence
                </h2>
                <p style={{
                  color: 'var(--text-secondary)',
                  fontSize: '14px',
                  maxWidth: '380px',
                  lineHeight: 1.6,
                  margin: '0 auto'
                }}>
                  Self-healing biomedical research assistant.
                  Ask any question about immunotherapy,
                  drug interactions, or genomics.
                </p>
              </div>
            </div>
          )}

          {messages.map((m) => (
            <MessageBubble 
              key={m.id} 
              message={m} 
              sessionId={activeSessionId} 
              onSuggestionSelect={handleSend}
            />
          ))}
          
          {loading && (
            <MessageBubble message={{ loading: true }} sessionId={activeSessionId} />
          )}

          <div ref={messagesEndRef} />
        </div>

        {errorVisible && error && (
          <div style={{
            background: 'var(--danger-bg)',
            color: 'var(--danger)',
            padding: '12px 24px',
            fontSize: '13px',
            textAlign: 'center',
            fontWeight: 500,
            borderTop: '1px solid var(--danger)'
          }}>
            Error: {error}. Try again.
          </div>
        )}

        <QueryInput onSend={handleSend} loading={loading} />
      </div>

      {/* Right Panel - Session History */}
      <div style={{
        width: 'var(--right-panel-width)',
        backgroundColor: 'var(--bg-secondary)',
        borderLeft: '1px solid var(--border)',
        overflowY: 'auto',
      }}>
        <SessionSidebar 
          currentSessionId={activeSessionId}
          onNewSession={newSession}
          onSelectSession={handleSelectSession}
        />
      </div>
    </div>
  )
}

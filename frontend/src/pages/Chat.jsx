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
    <div style={{ display: 'flex', height: 'calc(100vh - 56px)', overflow: 'hidden' }}>
      <SessionSidebar 
        currentSessionId={activeSessionId}
        onNewSession={newSession}
        onSelectSession={handleSelectSession}
      />
      
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
        <div style={{
          height: '48px',
          background: 'var(--bg2)',
          borderBottom: '1px solid var(--border)',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div style={{ color: 'var(--text3)', fontSize: '11px' }}>
            Session: {activeSessionId.slice(0, 8)}...
          </div>
          <div style={{ color: 'var(--text3)', fontSize: '11px' }}>
            1,495 documents indexed
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
                background: 'rgba(0,212,255,0.1)',
                border: '1px solid rgba(0,212,255,0.3)',
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
                  fontFamily: 'var(--display)',
                  fontSize: '22px',
                  fontWeight: 800,
                  color: 'var(--text)',
                  marginBottom: '8px',
                  letterSpacing: '-0.5px',
                }}>
                  Self-Learning and Self-Healing RAG
                </h2>
                <p style={{
                  color: 'var(--text3)',
                  fontSize: '13px',
                  maxWidth: '340px',
                  lineHeight: 1.6,
                }}>
                  Self-healing biomedical research assistant.
                  Ask any question about immunotherapy,
                  drug interactions, or genomics.
                </p>
              </div>
              
              {/* Feature pills */}
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                width: '100%',
                maxWidth: '360px',
              }}>
                {[
                  { icon: '⚡', text: 'Semantic cache for instant repeat queries' },
                  { icon: '🔄', text: 'Self-healing repair cycle for better answers' },
                  { icon: '📡', text: 'Live PubMed fetch when corpus is stale' },
                  { icon: '🧠', text: 'Learns from every query via Agent 6' },
                ].map((f, i) => (
                  <div key={i} style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '10px 16px',
                    background: 'var(--panel)',
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                    fontSize: '12px',
                    color: 'var(--text2)',
                    textAlign: 'left',
                  }}>
                    <span style={{ fontSize: '16px' }}>{f.icon}</span>
                    {f.text}
                  </div>
                ))}
              </div>
            </div>
          )}

          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} sessionId={activeSessionId} />
          ))}
          
          {loading && (
            <MessageBubble message={{ loading: true }} sessionId={activeSessionId} />
          )}

          <div ref={messagesEndRef} />
        </div>

        {errorVisible && error && (
          <div style={{
            background: 'var(--red)',
            color: 'var(--bg)',
            padding: '8px 24px',
            fontSize: '12px',
            textAlign: 'center',
            fontWeight: 600
          }}>
            Error: {error}. Try again.
          </div>
        )}

        <QueryInput onSend={handleSend} loading={loading} />
      </div>
    </div>
  )
}

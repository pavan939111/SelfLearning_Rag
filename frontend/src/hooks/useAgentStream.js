import { useState, useCallback, useRef } from 'react'

export function useAgentStream() {
  const [events, setEvents] = useState([])
  const [answer, setAnswer] = useState(null)
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState(null)
  const esRef = useRef(null)

  const stream = useCallback((sessionId, query) => {
    // Close existing connection
    if (esRef.current) esRef.current.close()
    
    setEvents([])
    setAnswer(null)
    setError(null)
    setStreaming(true)

    const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    const apiKey = import.meta.env.VITE_API_KEY || ''
    const url = `${apiBase}/chat/stream?session_id=${encodeURIComponent(sessionId)}&query=${encodeURIComponent(query)}${apiKey ? `&api_key=${encodeURIComponent(apiKey)}` : ''}`
    const es = new EventSource(url)
    esRef.current = es

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        
        if (data.type === 'provenance') {
          setAnswer(prev => prev ? { ...prev, claim_provenance: data.provenance } : null)
          setStreaming(false)
          es.close()
        } else if (data.step === 'answer' && data.status === 'done') {
          setAnswer(data)
          // If no provenance extraction is pending, close the connection
          if (data.claim_provenance && data.claim_provenance.length > 0) {
            setStreaming(false)
            es.close()
          }
        } else if (data.step === 'error') {
          setError(data.detail)
          setStreaming(false)
          es.close()
        } else {
          setEvents(prev => [...prev, {
            ...data,
            id: Date.now() + Math.random(),
            receivedAt: new Date().toISOString()
          }])
        }
      } catch (err) {
        console.error('SSE parse error:', err)
      }
    }

    es.onerror = () => {
      setError('Connection lost. Please try again.')
      setStreaming(false)
      es.close()
    }
  }, [])

  const reset = useCallback(() => {
    if (esRef.current) esRef.current.close()
    setEvents([])
    setAnswer(null)
    setError(null)
    setStreaming(false)
  }, [])

  return { events, answer, streaming, error, stream, reset }
}

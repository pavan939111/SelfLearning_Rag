import { useState, useCallback } from 'react'
import { sendMessage } from '../api/chat'

export function useChat(sessionId) {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const send = useCallback(async (query) => {
    if (!query.trim()) return

    const userMsg = {
      id: Date.now(),
      role: 'user',
      content: query,
      timestamp: new Date().toISOString()
    }

    setMessages(prev => [...prev, userMsg])
    setLoading(true)
    setError(null)

    try {
      const data = await sendMessage(sessionId, query)

      const assistantMsg = {
        id: Date.now() + 1,
        role: 'assistant',
        content: data.answer,
        query: query,
        citations: data.citations || [],
        confidence: data.confidence,
        hasGaps: data.has_gaps,
        gapAcknowledgment: data.gap_acknowledgment,
        hasContradiction: data.has_contradiction,
        contradictionNote: data.contradiction_note,
        cycleRan: data.cycle_ran,
        cycleExitReason: data.cycle_exit_reason,
        cacheHit: data.cache_hit,
        processingTime: data.processing_time_ms,
        queryType: data.query_type,
        topicCluster: data.query_type,
        timestamp: new Date().toISOString()
      }

      setMessages(prev => [...prev, assistantMsg])
      return assistantMsg

    } catch (err) {
      setError('Failed to get response. Please try again.')
      return null
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  const clearMessages = useCallback(() => {
    setMessages([])
  }, [])

  return { messages, loading, error, send, clearMessages }
}

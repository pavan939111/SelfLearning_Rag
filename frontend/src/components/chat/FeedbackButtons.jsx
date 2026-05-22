import { useState } from 'react'
import { submitFeedback } from '../../api/chat'

export default function FeedbackButtons({ message, sessionId, onFeedback }) {
  const [rated, setRated] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  // Show only on assistant messages that are complete
  if (message.role !== 'assistant' || message.loading) {
    return null
  }

  const handleRate = async (ratingVal) => {
    if (rated || submitting) return
    
    setSubmitting(true)
    const ratingState = ratingVal === 1 ? 'up' : 'down'
    setRated(ratingState)
    
    await submitFeedback({
      session_id: sessionId,
      query: message.query || 'unknown_query',
      answer: message.content,
      rating: ratingVal,
      topic_cluster: message.topicCluster,
      confidence: message.confidence,
      cycle_ran: message.cycleRan || false,
      cache_hit: message.cacheHit || false
    })
    
    setSubmitting(false)
    if (onFeedback) onFeedback(ratingVal)
  }

  return (
    <div style={{
      display: 'flex',
      gap: '6px',
      marginTop: '10px',
      paddingTop: '10px',
      borderTop: '1px solid var(--border)',
      alignItems: 'center'
    }}>
      <span style={{
        fontSize: '10px',
        color: 'var(--text3)',
        marginRight: '4px'
      }}>
        Was this helpful?
      </span>

      {/* Thumbs Up Button */}
      <button
        onClick={() => handleRate(1)}
        disabled={rated !== null || submitting}
        style={{
          background: rated === 'up' ? 'rgba(0,229,160,0.15)' : 'transparent',
          border: rated === 'up' ? '1px solid var(--green)' : '1px solid var(--border)',
          color: rated === 'up' ? 'var(--green)' : 'var(--text3)',
          padding: '4px 10px',
          borderRadius: '6px',
          fontSize: '14px',
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          cursor: rated !== null ? 'default' : 'pointer',
          transition: 'all 0.2s ease',
          outline: 'none',
        }}
      >
        👍 {rated === 'up' && <span style={{ fontSize: '10px', fontWeight: 600 }}>Thanks!</span>}
      </button>

      {/* Thumbs Down Button */}
      <button
        onClick={() => handleRate(-1)}
        disabled={rated !== null || submitting}
        style={{
          background: rated === 'down' ? 'rgba(255,77,109,0.15)' : 'transparent',
          border: rated === 'down' ? '1px solid var(--red)' : '1px solid var(--border)',
          color: rated === 'down' ? 'var(--red)' : 'var(--text3)',
          padding: '4px 10px',
          borderRadius: '6px',
          fontSize: '14px',
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          cursor: rated !== null ? 'default' : 'pointer',
          transition: 'all 0.2s ease',
          outline: 'none',
        }}
      >
        👎 {rated === 'down' && <span style={{ fontSize: '10px', fontWeight: 600 }}>Thanks!</span>}
      </button>
    </div>
  )
}

import { motion } from 'framer-motion'
import ConfidenceBar from './ConfidenceBar'
import CitationTag from './CitationTag'
import LoadingSpinner from '../shared/LoadingSpinner'

export default function MessageBubble({ message }) {
  const isUser = message.role === 'user'

  const renderTextWithCitations = (text, citations) => {
    if (!citations || citations.length === 0) return text
    
    const parts = []
    let lastIndex = 0
    const regex = /\(([^)]+)\)/g
    let match
    
    while ((match = regex.exec(text)) !== null) {
      const citeKey = match[1]
      const detail = citations.find(c => c.citation === citeKey || c.citation === `(${citeKey})`)
      
      if (detail) {
        parts.push(text.substring(lastIndex, match.index))
        parts.push(
          <CitationTag key={match.index} citation={`(${citeKey})`} details={detail} />
        )
        lastIndex = match.index + match[0].length
      }
    }
    
    parts.push(text.substring(lastIndex))
    return parts.length > 0 ? parts : text
  }

  if (message.loading) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '16px 20px',
          background: 'var(--bg2)',
          border: '1px solid var(--border)',
          borderRadius: '10px 10px 10px 2px',
          width: 'fit-content',
          maxWidth: '120px',
        }}
      >
        {[0, 1, 2].map(i => (
          <motion.div
            key={i}
            animate={{ 
              scale: [1, 1.4, 1],
              opacity: [0.4, 1, 0.4]
            }}
            transition={{
              duration: 0.8,
              repeat: Infinity,
              delay: i * 0.15,
            }}
            style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              background: 'var(--cyan)',
            }}
          />
        ))}
      </motion.div>
    )
  }

  if (isUser) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        style={{
          alignSelf: 'flex-end',
          background: 'var(--panel)',
          border: '1px solid var(--border)',
          borderRadius: '10px 10px 2px 10px',
          padding: '12px 16px',
          fontSize: '13px',
          maxWidth: '70%',
          color: 'var(--text)'
        }}
      >
        {message.content}
      </motion.div>
    )
  }

  const isFallback = message.content.includes('unable to generate') || message.confidence === 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        alignSelf: 'flex-start',
        background: 'var(--bg2)',
        border: '1px solid var(--border)',
        borderLeft: isFallback ? '2px solid var(--yellow)' : undefined,
        borderRadius: '10px 10px 10px 2px',
        padding: '16px 20px',
        maxWidth: '85%'
      }}
    >
      <div style={{ fontSize: '13px', lineHeight: 1.8, color: isFallback ? 'var(--text2)' : 'var(--text)', whiteSpace: 'pre-wrap' }}>
        {renderTextWithCitations(message.content, message.citations)}
      </div>

      {isFallback && (
        <div style={{
          marginTop: '10px',
          padding: '8px 12px',
          background: 'rgba(255,214,10,0.05)',
          border: '1px solid rgba(255,214,10,0.2)',
          borderRadius: '6px',
          fontSize: '10px',
          color: 'var(--text3)',
        }}>
          ⚠ API quota exhausted. Try again in a few minutes.
        </div>
      )}

      <div style={{ display: 'flex', gap: '12px', marginTop: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
        <ConfidenceBar confidence={message.confidence} />
        
        {message.processingTime && (
          <div style={{ color: 'var(--text3)', fontSize: '11px' }}>
            {(message.processingTime / 1000).toFixed(1)}s
          </div>
        )}
        
        {message.cacheHit && (
          <div style={{ color: 'var(--cyan)', fontSize: '11px', background: 'rgba(0, 212, 255, 0.1)', padding: '2px 8px', borderRadius: '10px' }}>
            ⚡ cached
          </div>
        )}
        
        {message.cycleRan && (
          <div style={{ color: 'var(--orange)', fontSize: '11px', background: 'rgba(255, 140, 66, 0.1)', padding: '2px 8px', borderRadius: '10px' }}>
            🔄 repaired
          </div>
        )}
        
        {message.queryType && (
          <div style={{ color: 'var(--text3)', fontSize: '11px', border: '1px solid var(--border)', padding: '2px 8px', borderRadius: '10px' }}>
            {message.queryType}
          </div>
        )}
      </div>

      {message.hasGaps && message.gapAcknowledgment && (
        <div style={{
          marginTop: '12px',
          padding: '10px 12px',
          borderLeft: '3px solid var(--yellow)',
          background: 'var(--bg)',
          fontSize: '11px',
          color: 'var(--text2)'
        }}>
          {message.gapAcknowledgment}
        </div>
      )}

      {message.hasContradiction && message.contradictionNote && (
        <div style={{
          marginTop: '12px',
          padding: '10px 12px',
          borderLeft: '3px solid var(--orange)',
          background: 'var(--bg)',
          fontSize: '11px',
          color: 'var(--text2)'
        }}>
          {message.contradictionNote}
        </div>
      )}

      {message.citations && message.citations.length > 0 && (
        <div style={{ marginTop: '16px', borderTop: '1px solid var(--border)', paddingTop: '12px' }}>
          <div style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--text3)', marginBottom: '8px', fontWeight: 600 }}>
            Sources
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {message.citations.map((c, i) => (
              <div key={i} style={{ fontSize: '10px', color: 'var(--text3)' }}>
                {c.citation} | {c.journal} | {c.year}
              </div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  )
}

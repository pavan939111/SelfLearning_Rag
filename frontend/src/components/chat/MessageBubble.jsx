import { motion } from 'framer-motion'
import ConfidenceBar from './ConfidenceBar'
import CitationTag from './CitationTag'
import LoadingSpinner from '../shared/LoadingSpinner'
import FeedbackButtons from './FeedbackButtons'
import ClaimProvenancePanel from './ClaimProvenancePanel'
import QuerySuggestions from './QuerySuggestions'
import { submitFeedback } from '../../api/chat'

function parseMarkdownTable(text) {
  const lines = text.split('\n')
  const tableLines = lines.filter(l => l.trim().startsWith('|'))
  
  if (tableLines.length < 2) return null
  
  const headers = tableLines[0]
    .split('|')
    .filter(h => h.trim())
    .map(h => h.trim())
  
  // Skip separator row (---|---|---)
  const rows = tableLines.slice(2).map(row =>
    row.split('|')
       .filter(cell => cell.trim() !== '')
       .map(cell => cell.trim())
  ).filter(row => row.length > 0)
  
  return { headers, rows }
}

function parseMarkdownList(text) {
  const lines = text.split('\n')
  const items = lines
    .filter(l => /^\d+\./.test(l.trim()))
    .map(l => l.replace(/^\d+\.\s*/, '').trim())
  return items.length > 0 ? items : null
}

function renderTable(tableData) {
  if (!tableData) return null
  return (
    <div style={{
      overflowX: 'auto',
      margin: '12px 0',
      borderRadius: '8px',
      border: '1px solid var(--border)',
    }}>
      <table style={{
        width: '100%',
        borderCollapse: 'collapse',
        fontSize: '12px',
        minWidth: '400px',
      }}>
        <thead>
          <tr>
            {tableData.headers.map((h, i) => (
              <th key={i} style={{
                background: 'var(--panel)',
                color: i === 0 ? 'var(--text2)' : 'var(--cyan)',
                padding: '10px 14px',
                textAlign: 'left',
                borderBottom: '2px solid var(--border)',
                borderRight: '1px solid var(--border)',
                fontWeight: 600,
                whiteSpace: 'nowrap',
              }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tableData.rows.map((row, ri) => (
            <tr key={ri} style={{
              background: ri % 2 === 0 
                ? 'var(--bg2)' : 'var(--bg3)',
            }}>
              {row.map((cell, ci) => (
                <td key={ci} style={{
                  padding: '9px 14px',
                  borderBottom: '1px solid var(--border)',
                  borderRight: '1px solid var(--border)',
                  color: ci === 0 
                    ? 'var(--text)' : 'var(--text2)',
                  fontWeight: ci === 0 ? 600 : 400,
                  lineHeight: 1.5,
                }}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function renderList(items) {
  if (!items) return null
  return (
    <ol style={{
      margin: '12px 0',
      paddingLeft: '0',
      listStyle: 'none',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
    }}>
      {items.map((item, i) => (
        <li key={i} style={{
          display: 'flex',
          gap: '10px',
          padding: '8px 12px',
          background: 'var(--bg3)',
          borderRadius: '6px',
          border: '1px solid var(--border)',
          borderLeft: '3px solid var(--cyan)',
          fontSize: '12px',
          color: 'var(--text2)',
          lineHeight: 1.5,
        }}>
          <span style={{
            color: 'var(--cyan)',
            fontWeight: 700,
            flexShrink: 0,
            minWidth: '20px',
          }}>
            {i + 1}.
          </span>
          {item}
        </li>
      ))}
    </ol>
  )
}

export default function MessageBubble({ message, sessionId, onSuggestionSelect }) {
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
          background: 'var(--accent-blue)',
          borderRadius: '16px 16px 4px 16px',
          padding: '14px 18px',
          fontSize: '15px',
          maxWidth: '70%',
          color: '#FFFFFF'
        }}
      >
        {message.content}
      </motion.div>
    )
  }

  const isFallback = message.content.includes('unable to generate') || message.confidence === 0
  const isDomainRejected = message.domainRejected

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        alignSelf: 'flex-start',
        background: isDomainRejected ? 'var(--danger-bg)' : 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderLeft: isDomainRejected ? '4px solid var(--danger)' : (isFallback ? '3px solid var(--warning)' : undefined),
        borderRadius: '4px 16px 16px 16px',
        padding: '16px 20px',
        maxWidth: '80%',
        boxShadow: 'var(--shadow-sm)',
        fontSize: '15px'
      }}
    >
      <div style={{
        color: 'var(--accent-teal)',
        fontSize: '11px',
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.5px',
        marginBottom: '12px'
      }}>
        FailureRAG
      </div>
      {isDomainRejected && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          marginBottom: '12px',
          paddingBottom: '10px',
          borderBottom: '1px solid rgba(255,140,66,0.2)',
        }}>
          <span style={{ fontSize: '16px' }}>🔬</span>
          <span style={{
            fontSize: '12px',
            fontWeight: 600,
            color: 'var(--danger)',
            textTransform: 'uppercase',
            letterSpacing: '1px',
          }}>
            Biomedical Questions Only
          </span>
        </div>
      )}
      {message.proactiveContradictionDetected && (
        <div style={{
          background: 'rgba(255,140,66,0.08)',
          border: '1px solid rgba(255,140,66,0.3)',
          borderRadius: '6px',
          padding: '8px 12px',
          marginBottom: '10px',
          fontSize: '11px',
          color: 'var(--orange)'
        }}>
          ⚡ Contradicting evidence found in corpus. Multiple perspectives presented below.
        </div>
      )}

      {(() => {
        const format = message.outputFormat || 'prose'
        const content = message.content || ''
        
        if (format === 'table') {
          const tableData = parseMarkdownTable(content)
          if (tableData) {
            // Get text before and after table
            const lines = content.split('\n')
            const beforeTable = lines
              .slice(0, lines.findIndex(l => l.trim().startsWith('|')))
              .join('\n').trim()
            const afterTableStart = lines
              .findIndex((l, i) => 
                i > 0 && !l.trim().startsWith('|') && 
                lines[i-1].trim().startsWith('|')
              )
            const afterTable = afterTableStart > 0
              ? lines.slice(afterTableStart).join('\n').trim()
              : ''
            
            return (
              <div>
                {beforeTable && (
                  <p style={{ fontSize:'13px', color:'var(--text)', 
                              marginBottom:'8px', lineHeight:1.8 }}>
                    {renderTextWithCitations(beforeTable, message.citations)}
                  </p>
                )}
                {/* Notice we do not use renderTextWithCitations on table cells to avoid breaking layout or just let the tags sit as text */}
                {renderTable(tableData)}
                {afterTable && (
                  <p style={{ fontSize:'13px', color:'var(--text2)',
                              marginTop:'8px', lineHeight:1.8 }}>
                    {renderTextWithCitations(afterTable, message.citations)}
                  </p>
                )}
              </div>
            )
          }
        }
        
        if (format === 'list') {
          const items = parseMarkdownList(content)
          if (items) {
            const afterListMatch = content.match(/\n\n([^0-9].+)$/)
            const summary = afterListMatch ? afterListMatch[1] : ''
            return (
              <div>
                {renderList(items)}
                {summary && (
                  <p style={{ fontSize:'12px', color:'var(--text3)',
                              marginTop:'8px', lineHeight:1.6,
                              fontStyle:'italic' }}>
                    {renderTextWithCitations(summary, message.citations)}
                  </p>
                )}
              </div>
            )
          }
        }
        
        // Default prose rendering
        return (
          <div style={{
            fontSize: '15px',
            color: isFallback ? 'var(--text-secondary)' : 'var(--text-primary)',
            lineHeight: 1.6,
            whiteSpace: 'pre-wrap',
          }}>
            {renderTextWithCitations(content, message.citations)}
          </div>
        )
      })()}

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
        {!isDomainRejected && (
          <ConfidenceBar 
            confidence={message.confidence} 
            confidenceLower={message.confidenceLower}
            confidenceUpper={message.confidenceUpper}
          />
        )}
        
        {!isDomainRejected && message.processingTime && (
          <div style={{ color: 'var(--text3)', fontSize: '11px' }}>
            {(message.processingTime / 1000).toFixed(1)}s
          </div>
        )}
        
        {message.cacheHit && (
          <div style={{ color: 'var(--cyan)', fontSize: '11px', background: 'rgba(0, 212, 255, 0.1)', padding: '2px 8px', borderRadius: '10px' }}>
            ⚡ cached
          </div>
        )}
        
        {!isDomainRejected && message.cycleRan && (
          <div style={{ color: 'var(--orange)', fontSize: '11px', background: 'rgba(255, 140, 66, 0.1)', padding: '2px 8px', borderRadius: '10px' }}>
            🔄 repaired
          </div>
        )}
        
        {message.queryType && (
          <div style={{ color: 'var(--text3)', fontSize: '11px', border: '1px solid var(--border)', padding: '2px 8px', borderRadius: '10px' }}>
            {message.queryType}
          </div>
        )}
        
        {message.outputFormat && message.outputFormat !== 'prose' && (
          <span style={{
            padding: '2px 7px',
            background: 'rgba(168,85,247,0.1)',
            border: '1px solid rgba(168,85,247,0.3)',
            color: 'var(--purple)',
            borderRadius: '4px',
            fontSize: '9px',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          }}>
            {message.outputFormat}
          </span>
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

      {!isDomainRejected && message.citations && message.citations.length > 0 && (
        <div style={{ marginTop: '16px', borderTop: '1px solid var(--border-light)', paddingTop: '16px' }}>
          <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '8px', fontWeight: 600 }}>
            Sources
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {message.citations.map((c, i) => (
              <div key={i} style={{ 
                fontSize: '12px', 
                color: 'var(--text-secondary)',
                borderLeft: '3px solid var(--accent-teal)',
                padding: '6px 10px',
                background: 'var(--accent-teal-light)',
                borderRadius: '0 6px 6px 0',
                display: 'flex',
                flexDirection: 'column'
              }}>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{c.title || c.citation}</div>
                <div>{c.author || 'Authors'} · {c.year} · {c.journal}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!isDomainRejected && message.claimProvenance && message.claimProvenance.length > 0 && (
        <ClaimProvenancePanel provenance={message.claimProvenance} />
      )}

      {message.querySuggestions && message.querySuggestions.length > 0 && (
        (isDomainRejected || message.hasGaps) && (
          <QuerySuggestions 
            suggestions={message.querySuggestions} 
            onSelect={onSuggestionSelect} 
            label={isDomainRejected ? "Try asking:" : "You might also want to ask:"}
          />
        )
      )}

      {message.role === 'assistant' && !message.loading && (
        <FeedbackButtons
          message={message}
          sessionId={sessionId}
          onFeedback={(rating) => {
            console.log('Feedback submitted:', rating)
          }}
        />
      )}
    </motion.div>
  )
}

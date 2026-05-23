import React, { useState } from 'react';

export default function ClaimProvenancePanel({ provenance = [], visible = true }) {
  const [expanded, setExpanded] = useState(false);
  const [expandedQuoteIndices, setExpandedQuoteIndices] = useState(new Set());

  if (!visible || !provenance || provenance.length === 0) {
    return null;
  }

  const toggleQuote = (index) => {
    const newSet = new Set(expandedQuoteIndices);
    if (newSet.has(index)) {
      newSet.delete(index);
    } else {
      newSet.add(index);
    }
    setExpandedQuoteIndices(newSet);
  };

  return (
    <div style={{ marginTop: '12px' }}>
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'var(--bg3, #374151)',
          border: '1px solid var(--border, #4b5563)',
          borderRadius: '6px',
          padding: '8px 12px',
          fontSize: '11px',
          color: 'var(--text3, #9ca3af)',
          cursor: 'pointer',
          outline: 'none',
        }}
      >
        <span>View claim sources ({provenance.length} claims)</span>
        <span style={{ 
          transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
          transition: 'transform 0.2s ease'
        }}>
          ▼
        </span>
      </button>

      {expanded && (
        <div style={{ 
          marginTop: '8px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px'
        }}>
          {provenance.map((item, index) => (
            <div key={index} style={{
              padding: '12px',
              background: 'var(--bg2, #1f2937)',
              border: '1px solid var(--border, #4b5563)',
              borderRadius: '6px',
            }}>
              <div style={{
                color: 'var(--text2, #d1d5db)',
                fontStyle: 'italic',
                fontSize: '12px',
                marginBottom: '8px',
                lineHeight: 1.5
              }}>
                "{item.claim}"
              </div>
              
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '10px',
                color: 'var(--text3, #9ca3af)',
                marginBottom: '6px',
                flexWrap: 'wrap'
              }}>
                <span style={{ background: 'rgba(0,0,0,0.2)', padding: '2px 6px', borderRadius: '4px' }}>
                  ID: {item.chunk_id.substring(0, 8)}...
                </span>
                <span>
                  {item.journal} ({item.paper_year})
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  Conf: 
                  <div style={{ width: '30px', height: '4px', background: 'var(--bg3)', borderRadius: '2px', overflow: 'hidden' }}>
                    <div style={{ 
                      width: `${item.confidence * 100}%`, 
                      height: '100%', 
                      background: item.confidence > 0.8 ? 'var(--cyan)' : item.confidence > 0.5 ? 'var(--yellow)' : 'var(--red)'
                    }} />
                  </div>
                </span>
              </div>

              {item.quote && (
                <div style={{ marginTop: '8px' }}>
                  <button
                    onClick={() => toggleQuote(index)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--cyan, #06b6d4)',
                      fontSize: '11px',
                      cursor: 'pointer',
                      padding: 0,
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                  >
                    {expandedQuoteIndices.has(index) ? 'Hide' : 'Show'} source excerpt
                  </button>
                  
                  {expandedQuoteIndices.has(index) && (
                    <div style={{
                      marginTop: '6px',
                      padding: '8px 10px',
                      background: 'var(--bg3, #374151)',
                      borderLeft: '2px solid var(--border2, #6b7280)',
                      fontSize: '11px',
                      color: 'var(--text3, #9ca3af)',
                      lineHeight: 1.4
                    }}>
                      "{item.quote}"
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

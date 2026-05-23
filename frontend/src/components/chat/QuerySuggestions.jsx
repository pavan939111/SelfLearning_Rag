import React from 'react';

const QuerySuggestions = ({ suggestions, onSelect }) => {
  if (!suggestions || suggestions.length === 0) {
    return null;
  }

  return (
    <div style={{
      marginTop: '12px',
      paddingTop: '12px',
      borderTop: '1px solid var(--border)'
    }}>
      <div style={{
        fontSize: '10px',
        color: 'var(--text3)',
        textTransform: 'uppercase',
        letterSpacing: '1px',
        marginBottom: '8px'
      }}>
        You might also want to ask:
      </div>
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '6px'
      }}>
        {suggestions.map((suggestion, index) => (
          <button
            key={index}
            onClick={() => onSelect(suggestion)}
            style={{
              background: 'rgba(0,212,255,0.05)',
              border: '1px solid rgba(0,212,255,0.2)',
              color: 'var(--cyan)',
              padding: '5px 12px',
              borderRadius: '20px',
              fontSize: '11px',
              cursor: 'pointer',
              transition: 'all 0.2s ease'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'rgba(0,212,255,0.1)';
              e.currentTarget.style.borderColor = 'rgba(0,212,255,0.4)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'rgba(0,212,255,0.05)';
              e.currentTarget.style.borderColor = 'rgba(0,212,255,0.2)';
            }}
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
};

export default QuerySuggestions;

import React from 'react';

export default function PredictionsPanel({ predictions = [] }) {
  const urgencyColors = {
    high: 'var(--red, #ef4444)',
    medium: 'var(--yellow, #eab308)',
    info: 'var(--cyan, #06b6d4)'
  };

  return (
    <div style={{
      backgroundColor: 'var(--bg2, #1f2937)',
      border: '1px solid var(--border, #374151)',
      borderRadius: '12px',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column'
    }}>
      <div style={{ padding: '1.5rem', borderBottom: '1px solid var(--border, #374151)' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text1, #f9fafb)', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span>🔮</span> Predictions
        </h2>
        <p style={{ margin: '0.25rem 0 0', fontSize: '0.875rem', color: 'var(--text2, #9ca3af)' }}>
          Based on current learning trends
        </p>
      </div>

      <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {predictions.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text2, #9ca3af)', fontSize: '0.875rem', backgroundColor: 'rgba(0,0,0,0.1)', borderRadius: '8px' }}>
            Not enough data yet — predictions appear after one week of usage
          </div>
        ) : (
          predictions.map((pred, i) => (
            <div key={i} style={{
              display: 'flex',
              backgroundColor: 'var(--bg3, #374151)',
              borderRadius: '8px',
              overflow: 'hidden',
              boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
            }}>
              <div style={{
                width: '6px',
                backgroundColor: urgencyColors[pred.urgency] || urgencyColors.info,
                boxShadow: pred.urgency === 'high' ? `0 0 10px ${urgencyColors.high}` : 'none',
                animation: pred.urgency === 'high' ? 'pulse 2s infinite' : 'none'
              }} />
              <div style={{ padding: '1rem', flex: 1, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <span style={{
                    display: 'inline-block',
                    padding: '0.25rem 0.5rem',
                    backgroundColor: 'rgba(255,255,255,0.1)',
                    borderRadius: '4px',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    color: 'var(--text2, #9ca3af)'
                  }}>
                    {pred.type.replace(/_/g, ' ')}
                  </span>
                </div>
                <p style={{ margin: 0, color: 'var(--text1, #f9fafb)', fontSize: '0.95rem', lineHeight: 1.5 }}>
                  {pred.message}
                </p>
                <div style={{ marginTop: '0.5rem', padding: '0.75rem', backgroundColor: 'rgba(0,0,0,0.2)', borderRadius: '6px', fontSize: '0.875rem' }}>
                  <strong style={{ color: 'var(--text2, #9ca3af)' }}>Recommended Action:</strong>{' '}
                  <span style={{ color: 'var(--text1, #f9fafb)' }}>{pred.action}</span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <style>
        {`
          @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
            70% { box-shadow: 0 0 0 6px rgba(239, 68, 68, 0); }
            100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
          }
        `}
      </style>
    </div>
  );
}

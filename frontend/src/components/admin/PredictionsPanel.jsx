import React from 'react';

export default function PredictionsPanel({ predictions = [] }) {
  const urgencyColors = {
    high: 'var(--red, #ef4444)',
    medium: 'var(--yellow, #eab308)',
    info: 'var(--cyan, #06b6d4)'
  };

  return (
    <div style={{
      backgroundColor: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      boxShadow: 'var(--shadow-sm)'
    }}>
      <div style={{ padding: '24px', borderBottom: '1px solid var(--border-light)' }}>
        <h2 style={{ fontSize: '20px', fontFamily: 'var(--font-heading)', color: 'var(--text-primary)', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>🔮</span> Predictions
        </h2>
        <p style={{ margin: '4px 0 0', fontSize: '14px', color: 'var(--text-secondary)' }}>
          Based on current learning trends
        </p>
      </div>

      <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {predictions.length === 0 ? (
          <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)' }}>
            Not enough data yet — predictions appear after one week of usage
          </div>
        ) : (
          predictions.map((pred, i) => (
            <div key={i} style={{
              display: 'flex',
              backgroundColor: 'var(--bg-secondary)',
              borderRadius: 'var(--radius-md)',
              overflow: 'hidden',
              boxShadow: 'var(--shadow-sm)'
            }}>
              <div style={{
                width: '6px',
                backgroundColor: urgencyColors[pred.urgency] || urgencyColors.info,
                boxShadow: pred.urgency === 'high' ? `0 0 10px ${urgencyColors.high}` : 'none',
                animation: pred.urgency === 'high' ? 'pulse 2s infinite' : 'none'
              }} />
              <div style={{ padding: '16px', flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <span style={{
                    display: 'inline-block',
                    padding: '4px 8px',
                    backgroundColor: 'var(--bg-card)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '11px',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                    color: 'var(--text-secondary)'
                  }}>
                    {pred.type.replace(/_/g, ' ')}
                  </span>
                </div>
                <p style={{ margin: 0, color: 'var(--text1, #f9fafb)', fontSize: '0.95rem', lineHeight: 1.5 }}>
                  {pred.message}
                </p>
                <div style={{ marginTop: '0.5rem', padding: '0.75rem', backgroundColor: 'rgba(0,0,0,0.2)', borderRadius: '6px', fontSize: '0.875rem' }}>
                  <span style={{ color: 'var(--text-primary)' }}>{pred.action}</span>
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

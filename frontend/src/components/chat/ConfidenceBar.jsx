import React from 'react';

export default function ConfidenceBar({ confidence }) {
  const pct = Math.round((confidence || 0) * 100);
  
  let color = 'var(--danger)';
  let bg = 'var(--danger-bg)';
  if (confidence >= 0.75) {
    color = 'var(--success)';
    bg = 'var(--success-bg)';
  } else if (confidence >= 0.50) {
    color = 'var(--warning)';
    bg = 'var(--warning-bg)';
  }

  return (
    <div style={{
      display: 'inline-flex',
      alignItems: 'center',
      padding: '4px 10px',
      borderRadius: 'var(--radius-lg)',
      backgroundColor: bg,
      color: color,
      fontSize: '11px',
      fontWeight: 600,
      letterSpacing: '0.3px',
    }}>
      {pct}% confidence
    </div>
  )
}

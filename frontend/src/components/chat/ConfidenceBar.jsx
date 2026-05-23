import React, { useState } from 'react';

export default function ConfidenceBar({ confidence, confidenceLower, confidenceUpper, sampleSize = 0 }) {
  const [isHovered, setIsHovered] = useState(false);
  
  const centerPct = Math.round((confidence || 0) * 100);
  // Fallback to point estimate if interval is not provided
  const lower = confidenceLower !== undefined ? confidenceLower : confidence;
  const upper = confidenceUpper !== undefined ? confidenceUpper : confidence;
  
  const lowerPct = Math.max(0, Math.round((lower || 0) * 100));
  const upperPct = Math.min(100, Math.round((upper || 0) * 100));
  
  const color = confidence >= 0.75 ? 'var(--green)'
              : confidence >= 0.50 ? 'var(--yellow)'
              : 'var(--red)';
              
  const rgbColor = confidence >= 0.75 ? '16, 185, 129' // Tailwind green-500 approx
                 : confidence >= 0.50 ? '245, 158, 11' // Tailwind amber-500 approx
                 : '239, 68, 68'; // Tailwind red-500 approx

  return (
    <div 
      style={{ display: 'flex', flexDirection: 'column', gap: '4px', position: 'relative' }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div style={{
          width: '80px',
          height: '10px',
          background: 'var(--border)',
          borderRadius: '5px',
          position: 'relative',
        }}>
          {/* Interval Bar (behind) */}
          <div style={{
            position: 'absolute',
            left: `${lowerPct}%`,
            width: `${Math.max(1, upperPct - lowerPct)}%`,
            top: 0, bottom: 0,
            background: `rgba(${rgbColor}, 0.2)`,
            borderRadius: '5px',
          }} />
          
          {/* Point Estimate Bar (on top) */}
          <div style={{
            position: 'absolute',
            left: 0,
            width: `${centerPct}%`,
            top: 0, bottom: 0,
            background: color,
            borderRadius: '5px',
            opacity: 1,
          }} />
        </div>
      </div>
      
      {/* Labels Below */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        width: '80px',
        fontSize: '9px',
        color: 'var(--text3)'
      }}>
        <span>{lowerPct}%</span>
        <span style={{ color: color, fontWeight: 600 }}>{centerPct}%</span>
        <span>{upperPct}%</span>
      </div>

      {/* Tooltip */}
      {isHovered && (
        <div style={{
          position: 'absolute',
          bottom: '100%',
          left: '50%',
          transform: 'translateX(-50%)',
          marginBottom: '8px',
          background: 'var(--panel)',
          border: '1px solid var(--border)',
          padding: '8px 12px',
          borderRadius: '6px',
          fontSize: '11px',
          color: 'var(--text)',
          whiteSpace: 'nowrap',
          zIndex: 10,
          boxShadow: '0 4px 12px rgba(0,0,0,0.2)'
        }}>
          <div>Confidence: {centerPct}% (95% CI: {lowerPct}%-{upperPct}%)</div>
          <div style={{ color: 'var(--text3)', marginTop: '4px', fontSize: '10px' }}>
            Based on calibration sample size: {sampleSize > 0 ? sampleSize : 'fallback'}
          </div>
        </div>
      )}
    </div>
  )
}

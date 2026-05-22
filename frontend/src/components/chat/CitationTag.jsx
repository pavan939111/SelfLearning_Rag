import { useState } from 'react'

export default function CitationTag({ citation, details }) {
  const [showPopup, setShowPopup] = useState(false)

  return (
    <span style={{ position: 'relative', display: 'inline-block' }}>
      <span
        onClick={() => setShowPopup(!showPopup)}
        style={{
          background: 'rgba(0, 212, 255, 0.1)',
          border: '1px solid rgba(0, 212, 255, 0.3)',
          borderRadius: '4px',
          padding: '1px 6px',
          color: 'var(--cyan)',
          fontSize: '11px',
          cursor: 'pointer',
          margin: '0 2px'
        }}
      >
        {citation}
      </span>
      
      {showPopup && details && (
        <>
          <div 
            style={{ position: 'fixed', inset: 0, zIndex: 90 }} 
            onClick={() => setShowPopup(false)}
          />
          <div style={{
            position: 'absolute',
            bottom: '100%',
            left: '50%',
            transform: 'translateX(-50%)',
            marginBottom: '8px',
            width: '250px',
            background: 'var(--panel)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            padding: '12px',
            boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
            zIndex: 100,
            fontSize: '12px',
            color: 'var(--text)',
            textAlign: 'left'
          }}>
            <div style={{ fontWeight: 600, marginBottom: '6px', color: 'var(--cyan)' }}>
              {details.title || "Unknown Title"}
            </div>
            <div style={{ color: 'var(--text2)', fontSize: '11px', marginBottom: '2px' }}>
              Journal: {details.journal}
            </div>
            <div style={{ color: 'var(--text2)', fontSize: '11px', marginBottom: '2px' }}>
              Year: {details.year}
            </div>
            <div style={{ color: 'var(--text3)', fontSize: '10px', marginTop: '6px' }}>
              ID: {details.paper_id}
            </div>
          </div>
        </>
      )}
    </span>
  )
}

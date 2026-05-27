import { useState, useRef } from 'react'
import { ArrowRight } from 'lucide-react'
import LoadingSpinner from '../shared/LoadingSpinner'

export default function QueryInput({ onSend, loading, placeholder = "Ask a biomedical question..." }) {
  const [text, setText] = useState('')
  const [isFocused, setIsFocused] = useState(false)
  const textareaRef = useRef(null)

  const handleInput = (e) => {
    setText(e.target.value)
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const submit = () => {
    if (!text.trim() || loading) return
    onSend(text)
    setText('')
    if (textareaRef.current) {
      textareaRef.current.style.height = '52px'
    }
  }

  const handleChipClick = (query) => {
    setText(query)
    if (textareaRef.current) {
      textareaRef.current.focus()
    }
  }

  return (
    <div style={{
      background: 'var(--bg-card)',
      borderTop: '1px solid var(--border)',
      padding: '24px 32px',
      boxShadow: '0 -4px 16px rgba(15,31,53,0.06)',
      position: 'relative',
      zIndex: 10
    }}>
      <div style={{
        display: 'flex',
        background: 'var(--bg-primary)',
        border: `1px solid ${isFocused ? 'var(--accent-teal)' : 'var(--border)'}`,
        borderRadius: 'var(--radius-lg)',
        overflow: 'hidden',
        boxShadow: isFocused ? '0 0 0 3px var(--accent-teal-light)' : 'none',
        transition: 'all 0.2s'
      }}>
        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder="Ask about immunotherapy, drug interactions, genomics..."
          disabled={loading}
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-body)',
            fontSize: '15px',
            padding: '16px 20px',
            resize: 'none',
            minHeight: '56px',
            maxHeight: '140px'
          }}
        />
        <button
          onClick={submit}
          disabled={!text.trim() || loading}
          style={{
            width: '56px',
            background: (!text.trim() || loading) ? 'var(--border)' : 'var(--accent-teal)',
            color: '#FFFFFF',
            border: 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: (!text.trim() || loading) ? 'not-allowed' : 'pointer',
            transition: 'background 0.2s'
          }}
        >
          {loading ? <LoadingSpinner /> : <ArrowRight size={20} />}
        </button>
      </div>
      
      <div style={{ display: 'flex', gap: '8px', marginTop: '16px', flexWrap: 'wrap' }}>
        {[
          "Pembrolizumab mechanism",
          "CAR-T therapy",
          "Drug interactions with warfarin"
        ].map(q => (
          <div
            key={q}
            onClick={() => handleChipClick(q)}
            style={{
              fontSize: '12px',
              color: 'var(--text-secondary)',
              background: 'var(--bg-primary)',
              border: '1px solid var(--border)',
              padding: '6px 14px',
              borderRadius: 'var(--radius-lg)',
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--accent-teal)'
              e.currentTarget.style.borderColor = 'var(--accent-teal)'
              e.currentTarget.style.background = 'var(--accent-teal-light)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--text-secondary)'
              e.currentTarget.style.borderColor = 'var(--border)'
              e.currentTarget.style.background = 'var(--bg-primary)'
            }}
          >
            {q}
          </div>
        ))}
      </div>
    </div>
  )
}

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
      background: 'var(--bg2)',
      borderTop: '1px solid var(--border)',
      padding: '20px 24px'
    }}>
      <div style={{
        display: 'flex',
        background: 'var(--panel)',
        border: `1px solid ${isFocused ? 'var(--cyan)' : 'var(--border)'}`,
        borderRadius: '10px',
        overflow: 'hidden',
        boxShadow: isFocused ? '0 0 0 2px rgba(0,212,255,0.1)' : 'none',
        transition: 'all 0.2s'
      }}>
        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder={placeholder}
          disabled={loading}
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: 'var(--text)',
            fontFamily: 'var(--mono)',
            fontSize: '13px',
            padding: '14px 16px',
            resize: 'none',
            minHeight: '52px',
            maxHeight: '120px'
          }}
        />
        <button
          onClick={submit}
          disabled={!text.trim() || loading}
          style={{
            width: '44px',
            background: (!text.trim() || loading) ? 'var(--border)' : 'var(--cyan)',
            color: 'var(--bg)',
            border: 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: (!text.trim() || loading) ? 'not-allowed' : 'pointer',
            transition: 'background 0.2s'
          }}
        >
          {loading ? <LoadingSpinner /> : <ArrowRight size={18} />}
        </button>
      </div>
      
      <div style={{ display: 'flex', gap: '8px', marginTop: '12px', flexWrap: 'wrap' }}>
        {[
          "How does pembrolizumab work?",
          "Drug interactions with warfarin",
          "What is CRISPR-Cas9?"
        ].map(q => (
          <div
            key={q}
            onClick={() => handleChipClick(q)}
            style={{
              fontSize: '11px',
              color: 'var(--text3)',
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              padding: '4px 10px',
              borderRadius: '12px',
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--cyan)'
              e.currentTarget.style.borderColor = 'var(--cyan)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--text3)'
              e.currentTarget.style.borderColor = 'var(--border)'
            }}
          >
            {q}
          </div>
        ))}
      </div>
    </div>
  )
}

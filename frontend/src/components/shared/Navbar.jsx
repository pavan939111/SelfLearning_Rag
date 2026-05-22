import { useState } from 'react'
import { NavLink } from 'react-router-dom'

const navItems = [
  { path: '/chat', label: 'Chat' },
  { path: '/transparency', label: 'Transparency' },
  { path: '/admin', label: 'Admin' },
]

function NavItem({ path, label }) {
  const [hovered, setHovered] = useState(false)
  
  return (
    <NavLink
      to={path}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={({ isActive }) => ({
        padding: '6px 16px',
        borderRadius: '6px',
        fontSize: '12px',
        color: isActive ? '#0a0e1a' 
             : hovered ? 'var(--text)' 
             : 'var(--text2)',
        background: isActive ? 'var(--cyan)'
                  : hovered ? 'var(--panel)'
                  : 'transparent',
        fontWeight: isActive ? 600 : 400,
        letterSpacing: '0.5px',
        transition: 'all 0.15s ease',
        textDecoration: 'none',
        border: '1px solid',
        borderColor: isActive ? 'var(--cyan)'
                   : hovered ? 'var(--border)'
                   : 'transparent',
      })}
    >
      {label}
    </NavLink>
  )
}

export default function Navbar() {
  return (
    <nav style={{
      background: 'var(--bg2)',
      borderBottom: '1px solid var(--border)',
      padding: '0 32px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      height: '56px',
      position: 'sticky',
      top: 0,
      zIndex: 100,
      flexWrap: 'wrap',
      gap: '8px',
    }}>
      <div style={{
        fontFamily: 'var(--display)',
        fontSize: '18px',
        fontWeight: 800,
        color: 'var(--cyan)',
        letterSpacing: '-0.5px'
      }}>
        Self-Learning and Self-Healing RAG
      </div>
      <div style={{ display: 'flex', gap: '4px' }}>
        {navItems.map(item => (
          <NavItem key={item.path} path={item.path} label={item.label} />
        ))}
      </div>
      <div style={{
        fontSize: '10px',
        color: 'var(--text3)',
        letterSpacing: '1px'
      }} data-label="version">
        v2.1 — Biomedical RAG
      </div>
    </nav>
  )
}

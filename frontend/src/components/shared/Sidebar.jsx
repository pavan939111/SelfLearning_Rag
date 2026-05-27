import { NavLink } from 'react-router-dom'
import { useState, useEffect } from 'react'

const navItems = [
  { path: '/chat', label: 'Research Chat', icon: '🔬' },
  { path: '/transparency', label: 'Transparency', icon: '📊' },
  { path: '/admin', label: 'Admin Panel', icon: '⚙️' },
]

function StatusDot({ status }) {
  const color = status === 'connected' ? 'var(--success)' : 
                status === 'disconnected' ? 'var(--danger)' : 
                'var(--accent-blue)';
  return (
    <div style={{
      width: '8px', height: '8px', borderRadius: '50%',
      backgroundColor: color,
      boxShadow: status === 'checking' ? '0 0 8px var(--accent-blue)' : 'none',
      animation: status === 'checking' ? 'pulse 1.5s infinite' : 'none'
    }} />
  )
}

function DatabaseStatus({ name }) {
  const [status, setStatus] = useState('connected') // Simulate healthy status
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--text-muted)' }}>
      <StatusDot status={status} />
      <span>{name}</span>
      <span style={{ marginLeft: 'auto', fontSize: '11px', opacity: 0.7 }}>connected</span>
    </div>
  )
}

export default function Sidebar() {
  return (
    <aside style={{
      width: 'var(--sidebar-width)',
      backgroundColor: 'var(--bg-sidebar)',
      display: 'flex',
      flexDirection: 'column',
      borderRight: '1px solid rgba(255,255,255,0.05)',
      height: '100vh',
    }}>
      {/* Brand */}
      <div style={{ padding: '32px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '4px' }}>
          <span style={{ fontSize: '24px' }}>🧬</span>
          <h1 style={{
            fontFamily: 'var(--font-heading)',
            color: '#FFFFFF',
            fontSize: '24px',
            margin: 0,
            lineHeight: 1.2
          }}>
            FailureRAG
          </h1>
        </div>
        <div style={{
          color: 'var(--accent-teal)',
          fontSize: '12px',
          fontWeight: 600,
          letterSpacing: '0.5px',
          textTransform: 'uppercase'
        }}>
          Biomedical Research Assistant
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '0 16px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {navItems.map(item => (
          <NavLink
            key={item.path}
            to={item.path}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '12px 16px',
              color: isActive ? 'var(--text-sidebar-active)' : 'var(--text-sidebar)',
              backgroundColor: isActive ? 'var(--bg-sidebar-active)' : 'transparent',
              textDecoration: 'none',
              borderRadius: 'var(--radius-sm)',
              borderLeft: isActive ? '4px solid var(--accent-teal)' : '4px solid transparent',
              transition: 'var(--transition)',
              fontWeight: isActive ? 500 : 400
            })}
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer / Status */}
      <div style={{ padding: '24px', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '16px', textTransform: 'uppercase', letterSpacing: '1px' }}>
          System Status
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <DatabaseStatus name="Qdrant Vector" />
          <DatabaseStatus name="Supabase SQL" />
          <DatabaseStatus name="Neo4j Graph" />
          <DatabaseStatus name="Redis Cache" />
        </div>
      </div>
    </aside>
  )
}

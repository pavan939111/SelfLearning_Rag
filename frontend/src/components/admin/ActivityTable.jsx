import { useState, useEffect } from 'react'

export default function ActivityTable({ getPendingApprovals, approveRepair }) {
  const [approvals, setApprovals] = useState([])
  const [loading, setLoading] = useState(true)

  const fetchApprovals = async () => {
    setLoading(true)
    try {
      const data = await getPendingApprovals()
      setApprovals(data || [])
    } catch (err) {
      console.error("Failed to fetch approvals", err)
      setApprovals([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchApprovals()
  }, [])

  const handleAction = async (id, decision) => {
    try {
      await approveRepair(id, decision)
      fetchApprovals()
    } catch (e) {
      console.error(`Failed to ${decision} repair`, e)
    }
  }

  const getFailureClassBadge = (fc) => {
    switch(fc) {
      case 'A': return <span style={{ background: 'var(--danger-bg)', color: 'var(--danger)', padding: '2px 8px', borderRadius: 'var(--radius-sm)', fontSize: '11px', fontWeight: 600 }}>CLASS A</span>
      case 'B': return <span style={{ background: 'var(--warning-bg)', color: 'var(--warning)', padding: '2px 8px', borderRadius: 'var(--radius-sm)', fontSize: '11px', fontWeight: 600 }}>CLASS B</span>
      case 'C': return <span style={{ background: 'var(--accent-blue-light)', color: 'var(--accent-blue)', padding: '2px 8px', borderRadius: 'var(--radius-sm)', fontSize: '11px', fontWeight: 600 }}>CLASS C</span>
      default: return null
    }
  }

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      boxShadow: 'var(--shadow-sm)'
    }}>
      <div style={{
        padding: '24px',
        borderBottom: '1px solid var(--border-light)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <h2 style={{ fontFamily: 'var(--font-heading)', fontSize: '20px', color: 'var(--text-primary)' }}>
          Pending Repairs
        </h2>
        
        {approvals.length > 0 ? (
          <div style={{ background: 'var(--danger-bg)', color: 'var(--danger)', padding: '4px 12px', borderRadius: 'var(--radius-lg)', fontSize: '12px', fontWeight: 600 }}>
            {approvals.length} pending
          </div>
        ) : (
          <div style={{ color: 'var(--success)', fontSize: '13px', fontWeight: 600 }}>
            All clear
          </div>
        )}
      </div>

      {loading ? (
        <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text3)', fontSize: '12px' }}>
          Loading pending repairs...
        </div>
      ) : approvals.length === 0 ? (
        <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text3)', fontSize: '12px' }}>
          No pending repairs
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead style={{ background: 'var(--bg-secondary)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px', fontSize: '11px' }}>
              <tr>
                <th style={{ padding: '12px 24px', textAlign: 'left', fontWeight: 600 }}>Query</th>
                <th style={{ padding: '12px 24px', textAlign: 'left', fontWeight: 600 }}>Failure Class</th>
                <th style={{ padding: '12px 24px', textAlign: 'left', fontWeight: 600 }}>Root Cause</th>
                <th style={{ padding: '12px 24px', textAlign: 'left', fontWeight: 600 }}>Date</th>
                <th style={{ padding: '12px 24px', textAlign: 'left', fontWeight: 600 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {approvals.map((a, index) => (
                <tr key={a.id} style={{ 
                  borderBottom: '1px solid var(--border-light)', 
                  color: 'var(--text-secondary)',
                  backgroundColor: index % 2 === 0 ? 'var(--bg-card)' : 'var(--bg-primary)'
                }}>
                  <td style={{ padding: '16px 24px', color: 'var(--text-primary)', maxWidth: '200px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {a.query.length > 50 ? a.query.substring(0, 50) + '...' : a.query}
                  </td>
                  <td style={{ padding: '16px 24px' }}>{getFailureClassBadge(a.failure_class)}</td>
                  <td style={{ padding: '16px 24px', fontStyle: 'italic', color: 'var(--text-muted)' }}>{a.root_cause}</td>
                  <td style={{ padding: '16px 24px' }}>{new Date(a.date).toLocaleDateString()}</td>
                  <td style={{ padding: '16px 24px' }}>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button 
                        onClick={() => handleAction(a.id, 'approve')}
                        style={{ background: 'var(--accent-teal)', border: 'none', color: '#FFFFFF', padding: '6px 14px', borderRadius: 'var(--radius-sm)', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}
                      >
                        Approve
                      </button>
                      <button 
                        onClick={() => handleAction(a.id, 'reject')}
                        style={{ background: 'transparent', border: '1px solid var(--danger)', color: 'var(--danger)', padding: '6px 14px', borderRadius: 'var(--radius-sm)', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}
                      >
                        Reject
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

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
      case 'A': return <span style={{ background: 'rgba(255,77,109,0.1)', color: 'var(--red)', padding: '2px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: 600 }}>CLASS A</span>
      case 'B': return <span style={{ background: 'rgba(255,214,10,0.1)', color: 'var(--yellow)', padding: '2px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: 600 }}>CLASS B</span>
      case 'C': return <span style={{ background: 'rgba(255,140,66,0.1)', color: 'var(--orange)', padding: '2px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: 600 }}>CLASS C</span>
      default: return null
    }
  }

  return (
    <div style={{
      background: 'var(--bg2)',
      border: '1px solid var(--border)',
      borderRadius: '12px',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column'
    }}>
      <div style={{
        padding: '18px 20px',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <h2 style={{ fontFamily: 'var(--display)', fontSize: '15px', fontWeight: 700, color: 'var(--text)' }}>
          Pending Repairs
        </h2>
        
        {approvals.length > 0 ? (
          <div style={{ background: 'var(--red)', color: 'var(--bg)', padding: '2px 8px', borderRadius: '10px', fontSize: '11px', fontWeight: 600 }}>
            {approvals.length} pending
          </div>
        ) : (
          <div style={{ color: 'var(--green)', fontSize: '11px', fontWeight: 600 }}>
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
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px' }}>
            <thead style={{ background: 'var(--bg3)', color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '1px', fontSize: '10px' }}>
              <tr>
                <th style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 500 }}>Query</th>
                <th style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 500 }}>Failure Class</th>
                <th style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 500 }}>Root Cause</th>
                <th style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 500 }}>Date</th>
                <th style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 500 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {approvals.map(a => (
                <tr key={a.id} style={{ borderBottom: '1px solid var(--border)', color: 'var(--text2)' }}>
                  <td style={{ padding: '12px 16px', color: 'var(--text)', maxWidth: '200px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {a.query.length > 50 ? a.query.substring(0, 50) + '...' : a.query}
                  </td>
                  <td style={{ padding: '12px 16px' }}>{getFailureClassBadge(a.failure_class)}</td>
                  <td style={{ padding: '12px 16px', fontStyle: 'italic', color: 'var(--text3)' }}>{a.root_cause}</td>
                  <td style={{ padding: '12px 16px' }}>{new Date(a.date).toLocaleDateString()}</td>
                  <td style={{ padding: '12px 16px' }}>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button 
                        onClick={() => handleAction(a.id, 'approve')}
                        style={{ background: 'rgba(0,229,160,0.1)', border: '1px solid var(--green)', color: 'var(--green)', padding: '4px 12px', borderRadius: '4px', fontSize: '10px', cursor: 'pointer' }}
                      >
                        Approve
                      </button>
                      <button 
                        onClick={() => handleAction(a.id, 'reject')}
                        style={{ background: 'rgba(255,77,109,0.1)', border: '1px solid var(--red)', color: 'var(--red)', padding: '4px 12px', borderRadius: '4px', fontSize: '10px', cursor: 'pointer' }}
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

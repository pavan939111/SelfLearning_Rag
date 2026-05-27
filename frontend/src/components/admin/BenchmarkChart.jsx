import { useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { getBenchmarkTrend } from '../../api/admin'

export default function BenchmarkChart() {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchTrend() {
      try {
        const trendData = await getBenchmarkTrend()
        setData(trendData)
      } catch (err) {
        console.error("Failed to fetch benchmark trend", err)
      } finally {
        setLoading(false)
      }
    }
    fetchTrend()
  }, [])

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)',
      padding: '24px',
      marginTop: 0,
      boxShadow: 'var(--shadow-sm)'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontFamily: 'var(--font-heading)', fontSize: '20px', color: 'var(--text-primary)' }}>
            Benchmark Trend
          </h2>
          <div style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '4px' }}>
            Pass rate and confidence over time
          </div>
        </div>
        
        <div style={{
          background: 'var(--success-bg)',
          color: 'var(--success)',
          padding: '4px 12px',
          borderRadius: 'var(--radius-sm)',
          fontSize: '12px',
          fontWeight: 600
        }}>
          Baseline: 86.7% pass rate
        </div>
      </div>

      {loading ? (
        <div style={{ color: 'var(--text3)', fontSize: '12px', textAlign: 'center', padding: '40px 0' }}>
          Loading benchmark data...
        </div>
      ) : data && data.length > 1 ? (
        <div style={{ height: '200px', width: '100%' }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <XAxis dataKey="date" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} stroke="var(--border)" />
              <YAxis domain={[0, 1]} tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} stroke="var(--border)" tickFormatter={v => `${(v*100).toFixed(0)}%`} />
              <Tooltip 
                contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: 'var(--radius-sm)', boxShadow: 'var(--shadow-md)' }}
                itemStyle={{ fontSize: '13px' }}
                labelStyle={{ fontSize: '13px', marginBottom: '8px', color: 'var(--text-secondary)' }}
              />
              <Legend wrapperStyle={{ color: 'var(--text-secondary)', fontSize: '12px' }} />
              <Line type="monotone" dataKey="pass_rate" name="Pass Rate" stroke="var(--success)" strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} />
              <Line type="monotone" dataKey="confidence" name="Confidence" stroke="var(--accent-teal)" strokeWidth={2} dot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr 1fr',
            gap: '16px',
            padding: '24px 0',
          }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{
                fontFamily: 'var(--font-heading)',
                fontSize: '36px',
                color: 'var(--success)',
              }}>86.7%</div>
              <div style={{
                fontSize: '11px',
                color: 'var(--text-muted)',
                marginTop: '4px',
                textTransform: 'uppercase',
                letterSpacing: '1px',
                fontWeight: 600
              }}>Pass Rate</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{
                fontFamily: 'var(--font-heading)',
                fontSize: '36px',
                color: 'var(--accent-teal)',
              }}>0.67</div>
              <div style={{
                fontSize: '11px',
                color: 'var(--text-muted)',
                marginTop: '4px',
                textTransform: 'uppercase',
                letterSpacing: '1px',
                fontWeight: 600
              }}>Avg Confidence</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{
                fontFamily: 'var(--font-heading)',
                fontSize: '36px',
                color: 'var(--text-secondary)',
              }}>15</div>
              <div style={{
                fontSize: '11px',
                color: 'var(--text-muted)',
                marginTop: '4px',
                textTransform: 'uppercase',
                letterSpacing: '1px',
                fontWeight: 600
              }}>Questions</div>
            </div>
          </div>
          
          <div style={{
            textAlign: 'center',
            fontSize: '13px',
            color: 'var(--text-secondary)',
            marginTop: '16px',
            paddingTop: '16px',
            borderTop: '1px solid var(--border-light)',
          }}>
            Baseline established — weekly runs will track improvement
          </div>
        </div>
      )}
    </div>
  )
}

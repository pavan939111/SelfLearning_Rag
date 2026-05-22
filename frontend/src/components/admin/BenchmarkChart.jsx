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
      background: 'var(--bg2)',
      border: '1px solid var(--border)',
      borderRadius: '12px',
      padding: '24px',
      marginTop: 0
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontFamily: 'var(--display)', fontSize: '16px', fontWeight: 700, color: 'var(--text)' }}>
            Benchmark Trend
          </h2>
          <div style={{ color: 'var(--text3)', fontSize: '11px', marginTop: '4px' }}>
            Pass rate and confidence over time
          </div>
        </div>
        
        <div style={{
          background: 'rgba(0, 229, 160, 0.1)',
          border: '1px solid rgba(0, 229, 160, 0.3)',
          color: 'var(--green)',
          padding: '4px 10px',
          borderRadius: '4px',
          fontSize: '11px',
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
              <XAxis dataKey="date" tick={{ fill: 'var(--text3)', fontSize: 10 }} stroke="var(--border)" />
              <YAxis domain={[0, 1]} tick={{ fill: 'var(--text3)', fontSize: 10 }} stroke="var(--border)" tickFormatter={v => `${(v*100).toFixed(0)}%`} />
              <Tooltip 
                contentStyle={{ background: 'var(--panel)', border: '1px solid var(--border)', color: 'var(--text)' }}
                itemStyle={{ fontSize: '12px' }}
                labelStyle={{ fontSize: '12px', marginBottom: '8px' }}
              />
              <Legend wrapperStyle={{ color: 'var(--text2)', fontSize: '11px' }} />
              <Line type="monotone" dataKey="pass_rate" name="Pass Rate" stroke="var(--green)" strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} />
              <Line type="monotone" dataKey="confidence" name="Confidence" stroke="var(--cyan)" strokeWidth={2} dot={{ r: 4 }} />
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
                fontFamily: 'var(--display)',
                fontSize: '32px',
                fontWeight: 800,
                color: 'var(--green)',
              }}>86.7%</div>
              <div style={{
                fontSize: '11px',
                color: 'var(--text3)',
                marginTop: '4px',
                textTransform: 'uppercase',
                letterSpacing: '1px',
              }}>Pass Rate</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{
                fontFamily: 'var(--display)',
                fontSize: '32px',
                fontWeight: 800,
                color: 'var(--cyan)',
              }}>0.67</div>
              <div style={{
                fontSize: '11px',
                color: 'var(--text3)',
                marginTop: '4px',
                textTransform: 'uppercase',
                letterSpacing: '1px',
              }}>Avg Confidence</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{
                fontFamily: 'var(--display)',
                fontSize: '32px',
                fontWeight: 800,
                color: 'var(--text2)',
              }}>15</div>
              <div style={{
                fontSize: '11px',
                color: 'var(--text3)',
                marginTop: '4px',
                textTransform: 'uppercase',
                letterSpacing: '1px',
              }}>Questions</div>
            </div>
          </div>
          
          <div style={{
            textAlign: 'center',
            fontSize: '11px',
            color: 'var(--text3)',
            marginTop: '8px',
            paddingTop: '16px',
            borderTop: '1px solid var(--border)',
          }}>
            Baseline established — weekly runs will track improvement
          </div>
        </div>
      )}
    </div>
  )
}

import { useState, useEffect } from 'react'
import { useAdminStats } from '../hooks/useAdminStats'
import { getBenchmarkTrend, getLatestBenchmark, getPendingApprovals, approveRepair } from '../api/admin'
import HealthDot from '../components/admin/HealthDot'
import StatCard from '../components/admin/StatCard'
import BenchmarkChart from '../components/admin/BenchmarkChart'
import ActivityTable from '../components/admin/ActivityTable'
import InsightsList from '../components/admin/InsightsList'

export default function Admin() {
  const { health, stats, corpusHealth, loading, lastUpdated, refresh } = useAdminStats(30000)

  return (
    <div style={{
      maxWidth: '1200px',
      margin: '0 auto',
      padding: '32px 40px',
      overflowY: 'auto',
      height: 'calc(100vh - 56px)',
    }}>

      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        marginBottom: '28px',
      }}>
        <div>
          <h1 style={{
            fontFamily: 'var(--display)',
            fontSize: '26px',
            fontWeight: 800,
            color: 'var(--text)',
            letterSpacing: '-0.5px',
          }}>
            Admin Dashboard
          </h1>
          <p style={{
            color: 'var(--text3)',
            fontSize: '12px',
            marginTop: '4px',
          }}>
            FailureRAG System Health and Operations
          </p>
        </div>
        <div style={{display:'flex', gap:'10px', alignItems:'center'}}>
          {lastUpdated && (
            <span style={{color:'var(--text3)', fontSize:'11px'}}>
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={refresh}
            style={{
              background: 'var(--panel)',
              border: '1px solid var(--border)',
              color: 'var(--text2)',
              padding: '7px 16px',
              borderRadius: '6px',
              fontSize: '12px',
              cursor: 'pointer'
            }}
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Health Row */}
      <section style={{marginBottom: '24px'}}>
        <div style={{
          fontSize: '10px',
          letterSpacing: '2px',
          textTransform: 'uppercase',
          color: 'var(--text3)',
          marginBottom: '12px',
        }}>
          Database Health
        </div>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: '12px',
        }}>
          <HealthDot
            name="Qdrant Cloud"
            connected={health?.qdrant ?? false}
            detail="Vector store"
          />
          <HealthDot
            name="Supabase"
            connected={health?.supabase ?? false}
            detail="PostgreSQL logs"
          />
          <HealthDot
            name="Neo4j AuraDB"
            connected={health?.neo4j ?? false}
            detail="Knowledge graph"
          />
          <HealthDot
            name="Redis Upstash"
            connected={health?.redis ?? false}
            detail="Cache + queues"
          />
        </div>
      </section>

      {/* Corpus Stats Row */}
      <section style={{marginBottom: '24px'}}>
        <div style={{
          fontSize: '10px',
          letterSpacing: '2px',
          textTransform: 'uppercase',
          color: 'var(--text3)',
          marginBottom: '12px',
        }}>
          Corpus Statistics
        </div>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: '12px',
        }}>
          <StatCard
            label="Documents"
            value={stats?.qdrant_counts?.document?.toLocaleString() ?? '—'}
            sublabel="Full paper embeddings"
            color="var(--cyan)"
            icon="📄"
          />
          <StatCard
            label="Semantic Chunks"
            value={stats?.qdrant_counts?.semantic?.toLocaleString() ?? '—'}
            sublabel="Retrievable passages"
            color="var(--blue, #4a9eff)"
            icon="🔍"
          />
          <StatCard
            label="Propositions"
            value={stats?.qdrant_counts?.proposition?.toLocaleString() ?? '—'}
            sublabel="Atomic claims"
            color="var(--purple)"
            icon="⚡"
          />
          <StatCard
            label="Contradictions"
            value={corpusHealth?.chunks_with_contradictions ?? '0'}
            sublabel="Flagged for review"
            color="var(--orange)"
            icon="⚠️"
          />
        </div>
      </section>

      {/* Two column row */}
      <section style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '20px',
        marginBottom: '24px',
      }}>
        <InsightsList stats={stats} />
        <ActivityTable
          getPendingApprovals={getPendingApprovals}
          approveRepair={approveRepair}
        />
      </section>

      {/* Benchmark Chart */}
      <section style={{marginBottom: '24px'}}>
        <BenchmarkChart />
      </section>

    </div>
  )
}

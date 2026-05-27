import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronRight, BrainCircuit } from 'lucide-react';

export const ThoughtTraceCard = ({ trace }) => {
  const [expanded, setExpanded] = useState(false);

  // Map agents to readable names and colors
  const agentLabels = {
    'agent1': { name: 'Agent 1 (Retrieval)', color: 'var(--accent-blue)' },
    'agent2': { name: 'Agent 2 (Quality Gate)', color: 'var(--accent-teal)' },
    'agent3': { name: 'Agent 3 (Diagnosis)', color: 'var(--warning)' },
    'agent4a': { name: 'Agent 4A (Formulator)', color: 'var(--warning)' },
    'agent4b': { name: 'Agent 4B (Live Fetch)', color: 'var(--warning)' },
    'agent7': { name: 'Agent 7 (Generator)', color: 'var(--success)' },
  };

  const aLabel = agentLabels[trace.agent] || { name: trace.agent.toUpperCase(), color: 'var(--text-muted)' };

  return (
    <div style={{
      margin: '8px 0',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-sm)',
      backgroundColor: 'var(--bg-card)',
      overflow: 'hidden',
      fontSize: '13px',
      fontFamily: 'var(--font-mono)'
    }}>
      {/* Header */}
      <div 
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '8px 12px', cursor: 'pointer',
          borderBottom: expanded ? '1px solid var(--border)' : 'none',
          backgroundColor: expanded ? 'var(--bg-secondary)' : 'transparent',
          transition: 'background-color 0.2s'
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {expanded ? <ChevronDown size={14} color="var(--text-secondary)" /> : <ChevronRight size={14} color="var(--text-secondary)" />}
          <BrainCircuit size={14} color={aLabel.color} />
          <span style={{ fontWeight: 600, color: aLabel.color }}>{aLabel.name}</span>
          <span style={{ color: 'var(--text-muted)', padding: '0 8px', borderLeft: '1px solid var(--border)' }}>[{trace.step}]</span>
        </div>
        <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
          {trace.duration_ms}ms
        </div>
      </div>

      {/* Expandable Body */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{
              backgroundColor: 'var(--bg-primary)',
              padding: '12px',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px'
            }}
          >
            <div style={{ display: 'grid', gridTemplateColumns: '40px 1fr', gap: '8px' }}>
              <span style={{ fontWeight: 700, color: 'var(--warning)' }}>OBS</span>
              <span style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>{trace.obs}</span>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '40px 1fr', gap: '8px' }}>
              <span style={{ fontWeight: 700, color: 'var(--accent-teal)' }}>THK</span>
              <span style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>{trace.thk}</span>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '40px 1fr', gap: '8px' }}>
              <span style={{ fontWeight: 700, color: 'var(--danger)' }}>ACT</span>
              <span style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>{trace.act}</span>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '40px 1fr', gap: '8px' }}>
              <span style={{ fontWeight: 700, color: 'var(--success)' }}>OUT</span>
              <span style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>{trace.out}</span>
            </div>

            {trace.confidence > 0 && (
              <div style={{
                marginTop: '8px', paddingTop: '8px', borderTop: '1px solid var(--border)',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                fontSize: '11px'
              }}>
                <span style={{ color: 'var(--text-muted)' }}>Confidence</span>
                <span style={{ color: 'var(--accent-teal)', fontWeight: 600 }}>{(trace.confidence * 100).toFixed(0)}%</span>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

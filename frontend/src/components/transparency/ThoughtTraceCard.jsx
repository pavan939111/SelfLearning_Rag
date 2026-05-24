import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronRight, BrainCircuit } from 'lucide-react';

export const ThoughtTraceCard = ({ trace }) => {
  const [expanded, setExpanded] = useState(false);

  // Map agents to readable names and colors
  const agentLabels = {
    'agent1': { name: 'Agent 1 (Retrieval)', color: 'text-blue-400' },
    'agent2': { name: 'Agent 2 (Quality Gate)', color: 'text-emerald-400' },
    'agent3': { name: 'Agent 3 (Diagnosis)', color: 'text-amber-400' },
    'agent4a': { name: 'Agent 4A (Formulator)', color: 'text-purple-400' },
    'agent4b': { name: 'Agent 4B (Live Fetch)', color: 'text-purple-400' },
    'agent7': { name: 'Agent 7 (Generator)', color: 'text-indigo-400' },
  };

  const aLabel = agentLabels[trace.agent] || { name: trace.agent.toUpperCase(), color: 'text-gray-400' };

  return (
    <div className="my-2 border border-slate-700/50 rounded-md bg-slate-800/30 overflow-hidden text-sm font-mono">
      {/* Header */}
      <div 
        className="flex items-center justify-between p-2 cursor-pointer hover:bg-slate-700/30 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          {expanded ? <ChevronDown size={14} className="text-slate-400" /> : <ChevronRight size={14} className="text-slate-400" />}
          <BrainCircuit size={14} className={aLabel.color} />
          <span className={`font-semibold ${aLabel.color}`}>{aLabel.name}</span>
          <span className="text-slate-400 px-2 border-l border-slate-600">[{trace.step}]</span>
        </div>
        <div className="text-slate-500 text-xs">
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
            className="border-t border-slate-700/50 bg-slate-900/50 p-3 space-y-3"
          >
            <div className="grid grid-cols-[40px_1fr] gap-2">
              <span className="font-bold text-yellow-500">OBS</span>
              <span className="text-slate-300 leading-relaxed">{trace.obs}</span>
            </div>
            
            <div className="grid grid-cols-[40px_1fr] gap-2">
              <span className="font-bold text-cyan-500">THK</span>
              <span className="text-slate-300 leading-relaxed">{trace.thk}</span>
            </div>
            
            <div className="grid grid-cols-[40px_1fr] gap-2">
              <span className="font-bold text-orange-500">ACT</span>
              <span className="text-slate-300 leading-relaxed">{trace.act}</span>
            </div>
            
            <div className="grid grid-cols-[40px_1fr] gap-2">
              <span className="font-bold text-emerald-500">OUT</span>
              <span className="text-slate-300 leading-relaxed">{trace.out}</span>
            </div>

            {trace.confidence > 0 && (
              <div className="mt-2 pt-2 border-t border-slate-700/30 flex items-center justify-between text-xs">
                <span className="text-slate-500">Confidence</span>
                <span className="text-cyan-400">{(trace.confidence * 100).toFixed(0)}%</span>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

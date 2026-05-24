-- Run this in the Supabase SQL editor:
CREATE TABLE IF NOT EXISTS thought_traces (
    trace_id UUID PRIMARY KEY,
    session_id TEXT,
    agent TEXT,
    step TEXT,
    obs TEXT,
    thk TEXT,
    act TEXT,
    out TEXT,
    confidence FLOAT,
    duration_ms INT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_thought_traces_session ON thought_traces(session_id);
CREATE INDEX IF NOT EXISTS idx_thought_traces_agent ON thought_traces(agent);

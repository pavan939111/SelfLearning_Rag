# FailureRAG Demo Script

## Setup (before demo)
1. Start backend: uvicorn api.main:app --port 8000
2. Start frontend: cd frontend && npm run dev
3. Open http://localhost:5173
4. Ensure Gemini quota available (test with simple query)

## Demo Flow (7 minutes)

### Part 1 — Chat Interface (2 minutes)
Navigate to /chat
Query 1: "How does pembrolizumab work in treating lung cancer?"
  → Show: response with inline citations
  → Point out: confidence bar, processing time, cycle badge

Query 2 (same query): 
  → Show: ⚡ cached badge, much faster response
  → Explain: semantic hash cache, 3.4x speedup

### Part 2 — Transparency Mode (3 minutes)
Navigate to /transparency
Query: "What is the current standard treatment for NSCLC in 2024?"
  → Watch agent cards appear one by one
  → Point out: Agent 2 freshness check fails (temporal query)
  → Watch: Agent 3 diagnose knowledge_drift
  → Watch: Agent 4A trigger live PubMed fetch
  → Watch: merged chunks re-evaluated
  → Final answer appears with fresh citations

Explain each agent card as it appears.

### Part 3 — Admin Dashboard (2 minutes)
Navigate to /admin
  → Show: all 4 databases connected (green dots)
  → Show: 1,767 documents indexed
  → Show: 86.7% baseline benchmark pass rate
  → Show: Agent 6 coverage gaps detected
  → Explain: self-learning from query patterns

## Key Points to Emphasize
- System detects its own failures (Agent 2)
- Diagnoses root cause (Agent 3)
- Repairs itself in real time (Agent 4A)
- Learns from every query (Agent 6)
- Gets better over time (benchmark improvement)
- Zero hallucination risk (grounded generation only)

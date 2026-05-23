---
# FailureRAG

> **Self-healing, self-learning conversational RAG 
> system over biomedical research literature**

A nine-agent autonomous system that detects its own
retrieval failures, diagnoses root causes, repairs
itself in real time, and gets measurably smarter
with every query.

---

## System Architecture

```
                    USER QUERY
                        │
              ┌─────────▼─────────┐
              │   Redis Cache     │
              │   SimHash Check   │
              └────┬──────┬───────┘
                HIT│      │MISS
                   │      │
              ┌────▼──┐  ┌▼───────────────────┐
              │Agent 2│  │     Agent 1         │
              │Freshn.│  │  Query Classify     │
              │+Comp. │  │  Metadata Pre-Filter│
              │Check  │  │  Hybrid Retrieval   │
              └────┬──┘  │  RRF + MMR          │
                   │     └────────┬────────────┘
                   │              │
                   └──────┬───────┘
                          │
              ┌───────────▼───────────────┐
              │        Agent 2            │
              │  Pre-Generation Quality   │
              │  Gate — 5 Checks          │
              │  ① Retrieval Relevance    │
              │  ② Completeness Grounding │
              │  ③ Freshness              │
              │  ④ Calibration            │
              │  ⑤ Cross-Chunk Contrast   │
              └──────┬────────────┬───────┘
                  PASS│            │FAIL
                      │    ┌───────▼──────────────┐
                      │    │   A2→A3→A4A CYCLE    │
                      │    │                      │
                      │    │  Agent 3 diagnoses   │
                      │    │  Agent 4A formulates │
                      │    │  Agent 1 re-retrieves│
                      │    │  Chunks MERGED       │
                      │    │  Agent 2 re-evaluates│
                      │    │  Max 2 iterations    │
                      │    └───────────┬──────────┘
                      │                │
              ┌────────▼────────────────▼────────┐
              │           Agent 7                │
              │  Conversational Generator        │
              │  Structured Output               │
              │  Inline Citations                │
              │  Claim Provenance                │
              └──────────────┬───────────────────┘
                             │
                          RESPONSE
                             │
              ┌──────────────▼───────────────────┐
              │     POST-RESPONSE (async)        │
              │  Cache chunks • Agent 6 learn    │
              │  Supabase log • Queue 4B if A/B  │
              └──────────────────────────────────┘
```

---

## Nine Agents

| # | Agent | Role | Path |
|---|-------|------|------|
| 1 | Retrieval | Query classify → pre-filter → hybrid search → RRF → MMR | Hot |
| 2 | Quality Gate | 5 pre-generation checks on retrieved chunks | Hot |
| 3 | Root Cause | 5 diagnostic tests → Class A/B/C | Repair Cycle |
| 4A | Formulator | Gap analysis → targeted sub-queries → merge chunks | Repair Cycle |
| 4B | BG Repair | Re-chunking, re-embedding via Celery | Cold |
| 5A | Verification | 4-check gate + citation velocity before corpus entry | Cold |
| 5B | Ingestion | Hierarchical chunking + staging validation | Cold |
| 6 | Learning | Patterns, calibration, gaps, predictions, feedback | Cold |
| 7 | Generator | Structured output + claim provenance + citations | Hot |

---

## The Repair Cycle

```
Agent 2 FAIL
     │
     ▼
Agent 3 ──── Class A/B ──→ EXIT → Queue 4B async
     │                            Agent 7 with flag
     │ Class C
     ▼
Agent 4A
  • Gap analysis
  • Coverage mapping  
  • Targeted sub-query formulation
  • Strategy selection
     │
     ▼
Agent 1 re-retrieves missing pieces
     │
     ▼
MERGE + DEDUPLICATE new with original chunks
     │
     ▼
Agent 2 re-evaluates merged set
     │
  PASS → Agent 7
  FAIL (2nd time) → Agent 7 with honest flag
```

---

## Self-Learning Loops

```
Every query feeds Agent 6:

Query result → Pattern detection
            → Calibration curves (→ Agent 2)
            → Coverage gap map (→ Agent 5A priority)
            → Topic velocity (→ Cache TTL)

User feedback → Recalibrate confidence
             → Detect missed failures
             → Generate insights

Weekly benchmark → Track improvement over time
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Gemini 2.0 Flash |
| Embedding | pritamdeka/S-PubMedBert-MS-MARCO (768d) |
| Vector DB | Qdrant Cloud — 4-level hierarchical index |
| Relational | Supabase PostgreSQL — logs, calibration, benchmarks |
| Graph | Neo4j AuraDB — citation + contradiction graph |
| Cache | Upstash Redis — semantic cache + Celery queues |
| Backend | FastAPI + Celery + APScheduler |
| Frontend | Vite + React — Chat, Transparency, Admin |
| **Cost** | **₹0 — all free tier** |

---

## Four-Level Hierarchical Index

```
Paper
  └── L1: Document embedding (title + abstract)
        └── L2: Section chunks (IMRAD-aware)
              └── L3A: Semantic chunks (sentence boundaries)
                    └── L3B: Propositions (Gemini-extracted claims)

Current corpus: 1,767 papers
  Documents:    ~1,500 points
  Sections:     ~4,700 points
  Semantic:    ~10,900 points
  Propositions: ~5,500 points
```

---

## Evaluation Baseline

50 biomedical QA pairs across 5 question types:

| Metric | Baseline |
|--------|---------|
| Overall pass rate | **86.7%** |
| Average confidence | 0.67 |
| Average response time | 12.5s |
| Cache speedup | 3.4× |

Weekly automated benchmark tracks improvement over time.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/pavan939111/SelfLearning_Rag.git
cd SelfLearning_Rag

# 2. Install
pip install -r requirements.txt

# 3. Configure (copy and fill in your keys)
cp keys.txt.example keys.txt

# 4. Verify connections
python test_connections.py

# 5. Seed corpus (1-2 hours)
python run_ingestion.py

# 6. Start backend
uvicorn api.main:app --port 8000

# 7. Start frontend
cd frontend && npm install && npm run dev
```

Open http://localhost:5173

---

## Project Structure

```
failurerag/
├── agents/                 # Nine agent implementations
│   ├── models.py          # All Pydantic inter-agent contracts
│   ├── agent1_retrieval.py
│   ├── agent2_evaluator.py
│   ├── agent3_classifier.py
│   ├── agent4a_formulator.py
│   ├── agent4b_repair.py
│   ├── agent5a_verifier.py
│   ├── agent6_learning.py
│   ├── agent7_generator.py
│   ├── cache_manager.py
│   ├── conversation_memory.py
│   ├── live_fetcher.py
│   ├── live_fetch_ingester.py
│   ├── repair_cycle.py
│   └── stream_monitor.py
├── api/                    # FastAPI application
│   ├── main.py            # App + APScheduler
│   └── routes/
│       ├── chat.py        # POST /chat + SSE stream
│       ├── health.py
│       └── admin.py
├── database/              # Database clients
├── ingestion/             # Data pipeline
├── workers/               # Celery background workers
├── scripts/               # Utility scripts
├── tests/                 # Test suite
│   ├── unit/
│   ├── integration/
│   └── system/
├── frontend/              # Vite + React UI
│   └── src/
│       ├── pages/         # Chat, Transparency, Admin
│       ├── components/
│       ├── hooks/
│       └── api/
├── README.md
├── ARCHITECTURE.md
├── SETUP.md
├── CHANGELOG.md
├── requirements.txt
├── supabase_schema.sql
└── keys.txt.example
```

---

## Key Design Decisions

**Pre-generation evaluation** — Agent 2 evaluates chunks
BEFORE generation. Zero wasted LLM calls. Every answer
is grounded by construction.

**Merge-not-replace** — Agent 4A targets missing pieces.
New chunks merge with original good chunks. Agent 7
gets the most complete picture possible.

**Cache chunks not answers** — Answers adapt to
conversation context. Retrieval is the expensive part.
Agent 7 always generates fresh from cached chunks.

**Pydantic inter-agent contracts** — Type safety at
every agent boundary. ValidationError caught at the
source. LangGraph-ready for future migration.

---

## License

MIT — Pavan Kumar Kunukuntla — 2026

# Self-Learning and Self-Healing RAG

> **Self-healing, self-learning conversational RAG system
> over biomedical research literature**

A nine-agent autonomous system that detects its own 
retrieval failures, diagnoses root causes, repairs itself
in real time, and gets smarter with every query.

---

## Demo

**86.7% benchmark pass rate** on 50 biomedical QA pairs
out of the box — before any learning has occurred.

---

## What Makes This Different

Most RAG systems fail silently. Self-Learning and Self-Healing RAG fails loudly,
diagnoses why, and fixes itself.

| Problem | Self-Learning and Self-Healing RAG Solution |
|---------|-------------------|
| Stale knowledge | Agent 2 detects freshness failure → Agent 4A fetches live from PubMed |
| Bad retrieval | Agent 2 detects relevance failure → Agent 3 diagnoses → Agent 4A reformulates |
| Corpus gaps | Agent 6 tracks coverage gaps → Agent 5A prioritizes targeted ingestion |
| Confidence miscalibration | Agent 6 maintains calibration curves → Agent 2 adjusts scores |
| Contradicting sources | Agent 2 detects cross-chunk contradiction → Agent 7 surfaces explicitly |

---

## Architecture

### Nine Agents

| Agent | Role | Path |
|-------|------|------|
| Agent 1 | Agentic Retrieval — query classification, metadata pre-filter, hybrid search, RRF, MMR | Hot path |
| Agent 2 | Pre-Generation Quality Gate — 5 checks before any generation | Hot path |
| Agent 3 | Root Cause Classifier — 5 diagnostic tests, 3 failure classes | Repair cycle |
| Agent 4A | Gap Analysis + Retrieval Formulator — targeted sub-queries for missing pieces | Repair cycle |
| Agent 4B | Background Corpus Repair — re-chunking, re-embedding via Celery | Cold path |
| Agent 5A | Relevance Verification — 4-check gate before corpus entry | Cold path |
| Agent 5B | Selective Ingestion — hierarchical chunking + staging validation | Cold path |
| Agent 6 | Longitudinal Learning — patterns, calibration, coverage gaps | Cold path |
| Agent 7 | Conversational Response Generator — inline citations, conversation history | Hot path |

### The Repair Cycle

```
Agent 2 fails
     ↓
Agent 3 diagnoses root cause
     ↓
Agent 4A formulates targeted sub-queries
     ↓
Agent 1 re-retrieves missing pieces
     ↓
New chunks MERGED with original chunks
     ↓
Agent 2 re-evaluates merged set
     ↓
PASS → Agent 7 generates    FAIL (max 2x) → honest flag
```

### Tech Stack

**AI / ML**
- Gemini 2.0 Flash — classification, generation, reasoning
- Gemini 2.0 Flash Thinking — root cause diagnosis
- pritamdeka/S-PubMedBert-MS-MARCO — biomedical embeddings

**Databases (all free tier)**
- Qdrant Cloud — 4-level hierarchical vector index
- Supabase PostgreSQL — failure logs, calibration, benchmarks
- Neo4j AuraDB — citation and contradiction knowledge graph
- Upstash Redis — semantic cache, Celery queues, conversation memory

**Backend**
- FastAPI — async REST API with SSE streaming
- Celery — background repair workers
- APScheduler — weekly benchmarks, daily insights

**Frontend**
- Vite + React — dark theme UI
- Three pages: Chat, Transparency (live agent feed), Admin

---

## The Self-Healing Loop

```
User query → Agent 1 retrieves → Agent 2 evaluates
                                        ↓
                              FAIL: cycle runs
                              Agent 3 + 4A repair
                                        ↓
                              PASS: Agent 7 generates
                                        ↓
                              Agent 6 logs pattern
                                        ↓
                              Corpus grows smarter
                                        ↓
                              Same failure less likely
```

---

## Quick Start

### Prerequisites
- Python 3.13
- Node.js 18+
- Free accounts on:
  Qdrant Cloud, Supabase, Neo4j AuraDB,
  Upstash Redis, Google AI Studio

### Setup

1. Clone the repository
```bash
git clone https://github.com/yourusername/selflearning_rag.git
cd selflearning_rag
```

2. Create keys.txt with your API keys
```
QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_key
GEMINI_API_KEY=your_gemini_key
NEO4J_URI=neo4j+s://your_instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
REDIS_URL=rediss://your_upstash_endpoint:6379
REDIS_PASSWORD=your_password
```

3. Install Python dependencies
```bash
pip install -r requirements.txt
```

4. Test database connections
```bash
python test_connections.py
```

5. Seed the corpus (takes 1-2 hours)
```bash
python run_ingestion.py
```

6. Start the backend
```bash
uvicorn api.main:app --port 8000
```

7. Start the frontend
```bash
cd frontend
npm install
npm run dev
```

8. Open http://localhost:5173

---

## Project Structure

```
selflearning_rag/
├── agents/                 # Nine agent implementations
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
│   └── repair_cycle.py
├── api/                    # FastAPI application
│   ├── main.py
│   ├── routes/
│   │   ├── chat.py        # Chat + SSE streaming
│   │   ├── health.py
│   │   └── admin.py
│   └── models/
│       ├── requests.py
│       └── responses.py
├── database/               # Database clients
│   ├── qdrant_client.py
│   ├── supabase_client.py
│   ├── neo4j_client.py
│   └── redis_client.py
├── ingestion/              # Data pipeline
│   ├── fetcher.py         # PubMed fetcher
│   ├── chunker.py         # 4-level hierarchical chunker
│   ├── embedder.py        # S-PubMedBert embedder
│   └── pipeline.py        # Orchestrator
├── workers/                # Celery background workers
│   ├── celery_app.py
│   └── repair_tasks.py
├── scripts/                # Utility scripts
│   ├── backfill_neo4j.py
│   ├── build_contradiction_graph.py
│   ├── run_benchmark.py
│   ├── run_first_benchmark.py
│   ├── seed_benchmarks.py
│   └── verify_complete_system.py
├── frontend/               # Vite + React UI
│   ├── src/
│   │   ├── pages/         # Chat, Transparency, Admin
│   │   ├── components/    # All UI components
│   │   ├── hooks/         # React hooks
│   │   └── api/           # API client layer
│   └── package.json
├── utils/
│   └── logger.py
├── config.py
├── requirements.txt
├── run_ingestion.py
├── start_worker.py
├── test_connections.py
└── README.md
```

---

## Evaluation

Baseline benchmark (50 biomedical QA pairs):
- Pass rate: 86.7%
- Avg confidence: 0.67
- Avg response time: 12.5s

Run the benchmark yourself:
```bash
uvicorn api.main:app --port 8000
python scripts/run_first_benchmark.py
```

---

## Design Decisions

**Why pre-generation evaluation?**
Agent 2 evaluates retrieved chunks BEFORE generation.
No wasted LLM calls on bad evidence.
Generation is guaranteed to be grounded.

**Why merge chunks not replace?**
When Agent 4A finds missing pieces via live fetch or
sub-queries — new chunks are merged with original chunks.
Original good chunks are preserved.
Agent 7 gets the most complete picture possible.

**Why cache chunks not answers?**
Generated answers must adapt to conversation context.
What we cache is the expensive part — retrieval.
Agent 7 always generates fresh from cached chunks.

**Why Celery for repairs?**
Background repairs must never block the user response.
Celery with three priority queues ensures the hot path
(Agent 1 → Agent 2 → Agent 7) never waits for
corpus repairs.

---

## License

MIT

---

## Author

Built as a portfolio project demonstrating production-grade
agentic AI engineering — multi-agent orchestration,
self-healing systems, RAG evaluation, and observability.

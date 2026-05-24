# FailureRAG

> **Self-healing, self-learning conversational RAG system over biomedical research literature**

A nine-agent autonomous system that detects its own retrieval failures, diagnoses root causes, repairs itself in real time, and gets measurably smarter with every query.

**86.7% benchmark pass rate** on 50 biomedical QA pairs out of the box — before any learning has occurred.

---

## What Makes This Different

Most RAG systems fail silently. FailureRAG fails loudly, diagnoses why, and fixes itself.

| Problem | FailureRAG Solution |
|---------|-------------------|
| Bad retrieval → confident wrong answer | Agent 2 evaluates chunks **before** any generation |
| Stale knowledge | Agent 2 detects freshness failure → Agent 4A fetches live from PubMed |
| Corpus gaps | Agent 6 tracks what users ask → drives selective ingestion |
| Confidence miscalibration | Agent 6 calibration curves → Agent 2 adjusts dynamically |
| Contradicting sources | Agent 2 detects → Agent 7 surfaces explicitly with citations |
| Off-topic questions | QueryClassifier rejects non-biomedical queries in same LLM call |

---

## System Architecture

```mermaid
flowchart TD
    U([👤 User Query]) --> RC{Redis Cache\nSimHash Check}
    
    RC -->|HIT| A2H[Agent 2\nFreshness + Completeness\nOnly]
    RC -->|MISS| A1[Agent 1\nRetrieval]
    
    A1 -->|Query classify\nPre-filter\nHybrid search\nRRF + MMR| A2[Agent 2\nQuality Gate\n5 Pre-generation Checks]
    
    A2H -->|PASS| A7[Agent 7\nGenerator]
    A2H -->|FAIL| A1
    
    A2 -->|PASS| CACHE[Cache Chunks\nDynamic TTL]
    A2 -->|FAIL| A3[Agent 3\nRoot Cause\nClassifier]
    
    CACHE --> A7
    
    A3 -->|Class C\nQuery problem| A4A[Agent 4A\nGap Formulator]
    A3 -->|Class A/B\nData/Knowledge| A4B[Agent 4B\nCorpus Repair\nAsync]
    
    A4A -->|Re-retrieve\n+ Merge chunks| A2
    
    A7 -->|Answer + Citations\nClaim Provenance\nConfidence Interval| R([✓ Response])
    
    R --> A6[Agent 6\nLongitudinal\nLearning]
    
    A6 -.->|Calibration curves| A2
    A6 -.->|Dynamic TTL| RC
    A6 -.->|Ingestion priority| A5A[Agent 5A\nVerifier]
    
    A5A --> A5B[Agent 5B\nIngestion]
    A4B --> A5A

    style U fill:#0f2a1a,stroke:#00e5a0,color:#00e5a0
    style R fill:#0f2a1a,stroke:#00e5a0,color:#00e5a0
    style A1 fill:#1a2a4a,stroke:#4a9eff,color:#4a9eff
    style A2 fill:#1a3a4a,stroke:#00d4ff,color:#00d4ff
    style A2H fill:#1a3a4a,stroke:#00d4ff,color:#00d4ff
    style A3 fill:#2a2a1a,stroke:#ffd60a,color:#ffd60a
    style A4A fill:#2a1a0a,stroke:#ff8c42,color:#ff8c42
    style A4B fill:#2a1a2a,stroke:#a855f7,color:#a855f7
    style A5A fill:#1a2a3a,stroke:#60a5fa,color:#60a5fa
    style A5B fill:#1a3a3a,stroke:#34d399,color:#34d399
    style A6 fill:#3a1a3a,stroke:#e879f9,color:#e879f9
    style A7 fill:#1a3a1a,stroke:#00e5a0,color:#00e5a0
    style RC fill:#2a1a0a,stroke:#ff8c42,color:#ff8c42
    style CACHE fill:#2a1a0a,stroke:#ff8c42,color:#ff8c42
```

---

## The Repair Cycle — Core Innovation

```mermaid
flowchart LR
    FAIL([Agent 2\nFAIL]) --> A3

    subgraph CYCLE ["🔄 A2 → A3 → A4A Repair Cycle — Max 2 Iterations"]
        A3[Agent 3\nDiagnosis\n5 tests] -->|Class C| A4A[Agent 4A\nGap Analysis\nSub-queries]
        A4A -->|Re-retrieve\n+ MERGE| A2R[Agent 2\nRe-evaluate\nMerged Chunks]
    end

    A3 -->|Class A/B| EXIT[Exit Cycle\nQueue 4B async\nUser not blocked]
    A2R -->|PASS| GEN[Agent 7\nGenerate]
    A2R -->|FAIL x2| GEN2[Agent 7\nHonest Flag]

    style FAIL fill:#3a1a1a,stroke:#ff4d6d,color:#ff4d6d
    style A3 fill:#2a2a1a,stroke:#ffd60a,color:#ffd60a
    style A4A fill:#2a1a0a,stroke:#ff8c42,color:#ff8c42
    style A2R fill:#1a3a4a,stroke:#00d4ff,color:#00d4ff
    style EXIT fill:#2a1a2a,stroke:#a855f7,color:#a855f7
    style GEN fill:#1a3a1a,stroke:#00e5a0,color:#00e5a0
    style GEN2 fill:#2a2a1a,stroke:#ffd60a,color:#ffd60a
```

**Three exit conditions:**
1. Agent 2 passes → Agent 7 generates
2. Max 2 cycles → Agent 7 with honest gap flag
3. Class A/B diagnosis → exit immediately, queue Agent 4B async, user never waits

---

## Agent 2 — Five Pre-Generation Checks

```mermaid
flowchart TD
    IN[Retrieved Chunks] --> C1

    subgraph CHECKS ["Agent 2 — Quality Gate"]
        C1{① Retrieval\nRelevance} -->|FAIL| BLOCK1[BLOCKING\nEnter repair cycle]
        C1 -->|PASS| C2{② Completeness\nGrounding}
        C2 -->|FAIL| BLOCK2[BLOCKING\nEnter repair cycle]
        C2 -->|PASS| C3{③ Freshness\nCheck}
        C3 -->|FAIL| NB1[NON-BLOCKING\nSet live_fetch flag]
        C3 -->|PASS| C4{④ Calibration\nAgent 6 curves}
        NB1 --> C4
        C4 --> C5{⑤ Cross-Chunk\nContradiction}
        C5 -->|DETECTED| NB2[NON-BLOCKING\nFlag for Agent 7]
        C5 -->|CLEAR| OUT
        NB2 --> OUT
    end

    OUT[Agent 7\nGenerate with:\nCalibrated confidence\nContradiction note\nGap acknowledgment]

    style IN fill:#1a2a4a,stroke:#4a9eff,color:#4a9eff
    style C1 fill:#2a2a2a,stroke:#9aaac8,color:#e8eef8
    style C2 fill:#2a2a2a,stroke:#9aaac8,color:#e8eef8
    style C3 fill:#2a2a2a,stroke:#9aaac8,color:#e8eef8
    style C4 fill:#2a2a2a,stroke:#9aaac8,color:#e8eef8
    style C5 fill:#2a2a2a,stroke:#9aaac8,color:#e8eef8
    style BLOCK1 fill:#3a1a1a,stroke:#ff4d6d,color:#ff4d6d
    style BLOCK2 fill:#3a1a1a,stroke:#ff4d6d,color:#ff4d6d
    style NB1 fill:#2a1a0a,stroke:#ff8c42,color:#ff8c42
    style NB2 fill:#2a1a0a,stroke:#ff8c42,color:#ff8c42
    style OUT fill:#1a3a1a,stroke:#00e5a0,color:#00e5a0
```

---

## Agent 6 — Self-Learning Loops

```mermaid
flowchart LR
    QR[Every Query Result] --> A6
    UF[User Feedback\n👍 👎] --> A6
    BM[Weekly Benchmark] --> A6

    subgraph A6 ["Agent 6 — Longitudinal Learning"]
        OBS[Observe] --> PAT[Pattern\nDetection]
        OBS --> CAL[Calibration\nCurves]
        OBS --> GAP[Coverage\nGap Map]
        OBS --> VEL[Topic\nVelocity]
        OBS --> PRED[Predictions\n+ Forecasts]
    end

    CAL -->|expressed vs actual\nUser signal 2× weight| A2[Agent 2\nConfidence\nAdjustment]
    GAP -->|query_count\nper topic| A5A[Agent 5A\nIngestion\nPriority]
    VEL -->|immunotherapy 4hr\ndrug_interactions 24hr\ngenomics 7d| CACHE[Redis Cache\nDynamic TTL]
    PAT --> DASH[Admin\nDashboard\nInsights]
    PRED --> DASH

    style QR fill:#2a1a0a,stroke:#ff8c42,color:#ff8c42
    style UF fill:#1a3a1a,stroke:#00e5a0,color:#00e5a0
    style BM fill:#1a3a4a,stroke:#00d4ff,color:#00d4ff
    style A6 fill:#1a0a1a,stroke:#e879f9,color:#e879f9
    style A2 fill:#1a3a4a,stroke:#00d4ff,color:#00d4ff
    style A5A fill:#1a2a3a,stroke:#60a5fa,color:#60a5fa
    style CACHE fill:#2a1a0a,stroke:#ff8c42,color:#ff8c42
    style DASH fill:#2a2a2a,stroke:#9aaac8,color:#e8eef8
```

---

## Retrieval Architecture

```mermaid
flowchart TD
    Q[User Query] --> QC[Query Classifier\nGemini Flash\nDomain validation]
    
    QC -->|Rejected| REJ[Return helpful\nrejection message\nwith examples]
    QC -->|Accepted| MPF[Metadata Pre-Filter\nApplied BEFORE\nvector search]
    
    MPF --> STRAT{Query Type}
    
    STRAT -->|simple_factual| S1[Single Shot\nHybrid]
    STRAT -->|multi_hop| S2[Iterative\nDecomposed]
    STRAT -->|comparative| S3[Parallel\nComparative]
    STRAT -->|temporal| S4[Freshness\nPrioritized]
    STRAT -->|exploratory| S5[Broad\nThen Deep]
    
    S1 & S2 & S3 & S4 & S5 --> DENSE[Dense Search\nS-PubMedBert\n768 dimensions]
    S1 & S2 & S3 & S4 & S5 --> SPARSE[Sparse Search\nBM25 Keyword]
    
    DENSE & SPARSE --> RRF[RRF Fusion\nReciprocal\nRank Fusion]
    RRF --> MMR[MMR Reranking\nDiversity λ=0.7]
    MMR --> GE[Graph Expansion\nNeo4j Citation\nNeighbors]
    GE --> TOP5[Top-5 Chunks\nTo Agent 2]
    
    MPF -->|< 3 chunks| RELAX[Auto-relax filter\nand retry]
    RELAX --> STRAT

    style Q fill:#1a2a4a,stroke:#4a9eff,color:#4a9eff
    style QC fill:#1a2a4a,stroke:#4a9eff,color:#4a9eff
    style REJ fill:#3a1a1a,stroke:#ff4d6d,color:#ff4d6d
    style MPF fill:#1a3a4a,stroke:#00d4ff,color:#00d4ff
    style RRF fill:#2a2a1a,stroke:#ffd60a,color:#ffd60a
    style MMR fill:#2a2a1a,stroke:#ffd60a,color:#ffd60a
    style GE fill:#1a1a3a,stroke:#4a9eff,color:#4a9eff
    style TOP5 fill:#1a3a1a,stroke:#00e5a0,color:#00e5a0
    style RELAX fill:#2a1a0a,stroke:#ff8c42,color:#ff8c42
```

---

## Data Architecture

```mermaid
flowchart LR
    subgraph QDRANT ["Qdrant Cloud — Vector Store"]
        Q1[document\n~1,500 pts\nL1 full paper]
        Q2[section\n~4,700 pts\nL2 IMRAD]
        Q3[semantic\n~10,900 pts\nL3A chunks]
        Q4[proposition\n~5,500 pts\nL3B claims]
        Q5[staging × 4\nrepair validation]
    end

    subgraph SUPA ["Supabase PostgreSQL — Relational"]
        S1[ingestion_logs\nagent_failures]
        S2[repair_history\nrepair_queue]
        S3[agent6_patterns\nagent6_gaps\nagent6_calibration\nagent6_insights]
        S4[benchmark_questions\nbenchmark_results]
        S5[user_feedback\nuser_profiles\nstrategy_recommendations]
        S6[thought_traces\nReAct audit log]
    end

    subgraph NEO ["Neo4j AuraDB — Knowledge Graph"]
        N1[Paper nodes\n1,767 papers]
        N2[TopicCluster\n3 clusters]
        N3[CONTRADICTS\nedge]
        N4[SUPERSEDES\nedge]
        N1 -->|BELONGS_TO| N2
        N1 -->|CONTRADICTS| N3
        N1 -->|SUPERSEDES| N4
    end

    subgraph REDIS ["Upstash Redis — Cache + Queues"]
        R1[session:id\n2hr TTL\n6 turns verbatim]
        R2[cache:simhash\n4hr-7d TTL\n3.4x speedup]
        R3[topic_model:id\nsession bias]
        R4[Celery queues\nhigh/medium/low]
    end

    style QDRANT fill:#0a1a2a,stroke:#00d4ff
    style SUPA fill:#0a1a0a,stroke:#00e5a0
    style NEO fill:#0a0a1a,stroke:#4a9eff
    style REDIS fill:#1a0a0a,stroke:#ff8c42
```

---

## ReAct Thought Traces — NEW in v2.1

Every agent now emits structured reasoning in OBS/THK/ACT/OUT format. Visible in transparency mode when "REASONING ON" toggle is active.

```mermaid
sequenceDiagram
    participant Q as User Query
    participant A1 as Agent 1
    participant A2 as Agent 2
    participant A3 as Agent 3
    participant A4A as Agent 4A
    participant A7 as Agent 7

    Q->>A1: query + session_id
    Note over A1: OBS: Query received<br/>THK: simple_factual detected<br/>ACT: Apply cluster filter<br/>OUT: 5 chunks retrieved

    A1->>A2: chunks + classification
    Note over A2: OBS: 5 chunks, avg score 0.91<br/>THK: Relevance OK, checking completeness<br/>ACT: Run all 5 checks<br/>OUT: FAIL on freshness

    A2->>A3: failed check + chunks
    Note over A3: OBS: Freshness failed, 2021 data<br/>THK: Query asks about 2024 state<br/>ACT: Classify as knowledge_drift<br/>OUT: Class B → route to 4A

    A3->>A4A: diagnosis Class B
    Note over A4A: OBS: knowledge_drift diagnosed<br/>THK: Live PubMed fetch needed<br/>ACT: Fetch 2024 papers, merge chunks<br/>OUT: 3 fresh papers merged

    A4A->>A2: merged chunks
    Note over A2: OBS: 8 merged chunks, fresh 2024<br/>THK: Freshness now satisfied<br/>ACT: Re-evaluate all 5 checks<br/>OUT: PASS → route to Agent 7

    A2->>A7: verified chunks + confidence
    Note over A7: OBS: 8 chunks, confidence 0.81<br/>THK: Good evidence, generate response<br/>ACT: Generate with citations<br/>OUT: Response ready, 4 citations
```

---

## Nine Agents Reference

| Agent | Role | Path | File |
|-------|------|------|------|
| 1 | Agentic Retrieval — classify, pre-filter, hybrid search, RRF, MMR | Hot | `agents/agent1_retrieval.py` |
| 2 | Pre-Generation Quality Gate — 5 checks before any LLM call | Hot | `agents/agent2_evaluator.py` |
| 3 | Root Cause Classifier — 5 diagnostic tests, Class A/B/C | Repair | `agents/agent3_classifier.py` |
| 4A | Gap Formulator — gap analysis, sub-queries, chunk merge | Repair | `agents/agent4a_formulator.py` |
| 4B | Background Corpus Repair — rechunk, reembed via Celery | Cold | `agents/agent4b_repair.py` |
| 5A | Relevance Verification — 4 checks + citation velocity | Cold | `agents/agent5a_verifier.py` |
| 5B | Selective Ingestion — hierarchical chunking + staging | Cold | `ingestion/pipeline.py` |
| 6 | Longitudinal Learning — patterns, calibration, gaps, predictions | Cold | `agents/agent6_learning.py` |
| 7 | Conversational Generator — structured output, claim provenance | Hot | `agents/agent7_generator.py` |

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| LLM | Gemini 2.0 Flash | Classification, generation, diagnosis |
| Embedding | S-PubMedBert-MS-MARCO 768d | Biomedical semantic search |
| Vector DB | Qdrant Cloud | 4-level hierarchical index |
| Relational | Supabase PostgreSQL | Logs, calibration, benchmarks |
| Graph | Neo4j AuraDB | Citation + contradiction graph |
| Cache | Upstash Redis | Semantic cache + Celery queues |
| Backend | FastAPI + Celery + APScheduler | API + workers + scheduled jobs |
| Frontend | Vite + React | Chat, Transparency, Admin pages |
| **Cost** | **₹0 / month** | **All free tier** |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/pavan939111/SelfLearning_Rag.git
cd SelfLearning_Rag

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure (copy and fill in your API keys)
cp keys.txt.example keys.txt

# 4. Verify all 4 database connections
python test_connections.py

# 5. Seed the corpus (1-2 hours, checkpointed)
python run_ingestion.py

# 6. Start backend
uvicorn api.main:app --port 8000

# 7. Start frontend
cd frontend && npm install && npm run dev
```

Open **http://localhost:5173**

See [SETUP.md](SETUP.md) for detailed cloud service configuration.

---

## Evaluation

50 biomedical QA pairs across 5 question types and 4 difficulty levels.

| Metric | Value |
|--------|-------|
| Overall pass rate | **86.7%** |
| Average confidence | 0.67 |
| Average response time | 12.5s |
| Cache speedup | 3.4× |
| Total chunks indexed | 22,600+ |

Weekly automated benchmark tracks improvement as Agent 6 learns.

---

## Project Structure

```
failurerag/
├── agents/
│   ├── models.py              # All Pydantic inter-agent contracts
│   ├── agent1_retrieval.py    # QueryClassifier + HybridRetriever
│   ├── agent2_evaluator.py    # 5 pre-generation checks
│   ├── agent3_classifier.py   # Root cause diagnosis
│   ├── agent4a_formulator.py  # Gap analysis + live fetch
│   ├── agent4b_repair.py      # Celery corpus repair
│   ├── agent5a_verifier.py    # Selective ingestion gate
│   ├── agent6_learning.py     # Longitudinal learning
│   ├── agent7_generator.py    # Structured output + provenance
│   ├── cache_manager.py       # SimHash + dynamic TTL
│   ├── conversation_memory.py # Session topic model
│   ├── repair_cycle.py        # A2→A3→A4A orchestrator
│   └── stream_monitor.py      # Daily corpus sweep
├── api/
│   ├── main.py                # FastAPI + APScheduler
│   └── routes/
│       ├── chat.py            # POST /chat + SSE stream
│       ├── health.py
│       └── admin.py
├── database/                  # Qdrant, Supabase, Neo4j, Redis
├── ingestion/                 # Fetcher, chunker, embedder, pipeline
├── workers/                   # Celery tasks
├── utils/
│   └── thought_logger.py      # ReAct OBS/THK/ACT/OUT traces
├── scripts/                   # Benchmark, verify, backfill
├── tests/
│   ├── unit/
│   ├── integration/
│   └── system/
├── frontend/                  # Vite + React
│   └── src/
│       ├── pages/             # Chat, Transparency, Admin
│       ├── components/
│       └── hooks/
├── linkedin/                  # Architecture diagrams
├── README.md
├── ARCHITECTURE.md
├── SETUP.md
├── CHANGELOG.md
├── requirements.txt
└── keys.txt.example
```

---

## Key Design Decisions

**Pre-generation evaluation** — Agent 2 runs before any LLM generation call. Zero wasted tokens on bad evidence. Every answer is grounded by construction.

**Merge-not-replace** — Agent 4A finds missing pieces via targeted sub-queries. New chunks are merged with original good chunks. Agent 7 gets the most complete picture possible.

**Cache chunks not answers** — Generated answers must adapt to conversation context. We cache the expensive part — retrieval. Agent 7 always generates fresh from cached chunks.

**Pydantic inter-agent contracts** — Every agent boundary has type-validated Pydantic models. ValidationError caught at the source. LangGraph-ready for future migration.

**ReAct thought traces** — Every key decision emits OBS/THK/ACT/OUT. Full reasoning audit trail in Supabase. Visible in transparency mode for demo and debugging.

**Single LLM call for domain + classification** — The QueryClassifier uses one Gemini call to both validate the domain and classify the query type. No extra API calls for domain checking.

---

## License

MIT — Pavan Kumar Kunukuntla — 2026

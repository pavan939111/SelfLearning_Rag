# FailureRAG — System Architecture

## Overview

FailureRAG is a nine-agent self-healing self-learning
conversational RAG system over biomedical research 
literature. Two parallel loops never block each other.

**Hot Path** — synchronous, user-facing, under 8s P95
**Cold Path** — async Celery workers, corpus healing

## The Nine Agents

| Agent | Role | Path | File |
|-------|------|------|------|
| Agent 1 | Agentic Retrieval — query classification, metadata pre-filter, hybrid search (dense+sparse), RRF, MMR, sufficiency evaluation | Hot | agents/agent1_retrieval.py |
| Agent 2 | Pre-Generation Chunk Quality Gate — 5 checks before any generation | Hot | agents/agent2_evaluator.py |
| Agent 3 | Root Cause Classifier — 5 diagnostic tests, Class A/B/C | Repair Cycle | agents/agent3_classifier.py |
| Agent 4A | Gap Analysis + Retrieval Formulator — identifies missing pieces, formulates targeted sub-queries, merges new chunks | Repair Cycle | agents/agent4a_formulator.py |
| Agent 4B | Background Corpus Repair — re-chunking, re-embedding via Celery | Cold | agents/agent4b_repair.py |
| Agent 5A | Relevance Verification — 4-check gate, citation velocity | Cold | agents/agent5a_verifier.py |
| Agent 5B | Selective Ingestion — hierarchical chunking, staging validation | Cold | agents/agent5b_ingestion (pipeline.py) |
| Agent 6 | Longitudinal Learning — patterns, calibration, gaps, predictions | Cold | agents/agent6_learning.py |
| Agent 7 | Conversational Response Generator — structured output, claim provenance, inline citations | Hot | agents/agent7_generator.py |

## Hot Path — Step by Step

```
User message arrives
        ↓
Load conversation history from Redis
Last 6 turns verbatim + older summary (Gemini Flash)
        ↓
Embed query → 32-bit SimHash → Redis cache check
        ↓
CACHE HIT → retrieve cached chunks
  Agent 2 — freshness + completeness checks only
  PASS → Agent 7 generates fresh response
  FAIL → treat as cache miss
        ↓
CACHE MISS:
  Agent 1 — Query classification (5 types)
  Agent 1 — Metadata pre-filter (before vector search)
  Agent 1 — Hybrid retrieval → RRF → MMR → top 5
        ↓
Agent 2 — All 5 pre-generation checks
  PASS → cache chunks → Agent 7 generates
  FAIL → A2→A3→A4A Repair Cycle
        ↓
REPAIR CYCLE (max 2 iterations):
  Agent 3 diagnoses root cause
  Agent 4A formulates targeted sub-queries
  Agent 1 re-retrieves missing pieces
  New chunks MERGED with original chunks
  Agent 2 re-evaluates merged set
  EXIT CONDITIONS:
    (1) Agent 2 passes → Agent 7
    (2) Max cycles → Agent 7 with honest flag
    (3) Class A/B → exit + queue Agent 4B async
        ↓
Agent 7 — Generates conversational response
  Structured output: table/list/summary/prose
  Inline citations: (Author Year)
  Claim-level provenance
  Query suggestions if gaps found
  Confidence interval not point estimate
        ↓
Post-response (non-blocking):
  Cache chunks with dynamic TTL
  Agent 6 observes result
  Supabase logging
```

## A2→A3→A4A Repair Cycle

The core intelligence loop. Three exit conditions.

```
Agent 2 FAIL
    ↓
Agent 3 — 5 diagnostic tests
  T1: Existence test (Class B if fails)
  T2: Chunking boundary test (Class A)
  T3: Embedding space test (Class A)
  T4: Query processing test (Class C)
  T5: Metadata filter test (Class C)
    ↓
Class A/B → EXIT immediately
  Queue Agent 4B via Redis
  Agent 7 with confidence flag
  User not blocked
    ↓
Class C → Agent 4A
  Gap analysis
  Coverage mapping
  Targeted sub-query formulation
  Strategy selection per sub-query
  Filter adjustment per sub-query
    ↓
Agent 1 re-retrieves with formulation
New chunks MERGED + DEDUPLICATED with original
    ↓
Agent 2 re-evaluates merged chunks
Max 2 cycles total
```

## PipelineState

Single Pydantic model flowing through hot path.
Defined in agents/models.py.

```python
class PipelineState(BaseModel):
    query: str
    session_id: str
    user_id: str = ''
    classification: Optional[QueryClassification] = None
    filter_config: Optional[FilterConfig] = None
    retrieval_results: list[RetrievalResult] = []
    agent2_result: Optional[Agent2Result] = None
    cycle_result: Optional[CycleResult] = None
    response: Optional[GeneratedResponse] = None
    cache_hit: bool = False
    live_fetch_used: bool = False
    follow_up_resolved: bool = False
    graph_expansion_used: bool = False
    processing_start_ms: float = 0.0
```

## Agent 2 — Five Pre-Generation Checks

All checks run on retrieved CHUNKS before generation.
Nothing reaches Agent 7 without passing all checks.

| Check | What It Tests | Blocking? | LLM? |
|-------|--------------|-----------|------|
| Retrieval Relevance | Are chunks actually about the query? | YES | Gemini Flash |
| Completeness Grounding | Can query be fully answered from chunks? | YES | Gemini Flash |
| Freshness | Are chunks current enough for topic velocity? | NO (sets live_fetch flag) | None — metadata |
| Calibration | Historical accuracy from Agent 6 curves | NO (sets confidence) | None — Supabase |
| Cross-Chunk Contradiction | Do chunks conflict with each other? | NO (flags for Agent 7) | Gemini Flash |

## Agent 6 — Learning Feedback Loops

Agent 6 never acts directly on corpus.
Observes and recommends. Humans approve changes.

**Four output channels:**

1. **Failure patterns** → Admin dashboard insights
2. **Calibration curves** → Agent 2 reads dynamically
3. **Coverage gap map** → Agent 5A ingestion priority
4. **Topic velocity** → CacheManager dynamic TTL

**Additional inputs (v2.1):**

5. **User feedback** → thumbs up/down recalibrates confidence
6. **Strategy recommendations** → specific parameter changes for admin approval
7. **Predictions** → forecasts freshness decline, query volume growth

## Semantic Hash Cache

Stores retrieved CHUNKS only — not generated answers.
Agent 7 always generates fresh from cached chunks.

```
Query embedding → 32-bit SimHash (seed=42)
  → Redis key: cache:{8-char-hex}
  
Cache hit → Agent 2 checks (freshness + completeness)
  PASS → Agent 7 generates fresh response
  FAIL → full retrieval pipeline

Dynamic TTL from Agent 6 topic velocity:
  High velocity (immunotherapy): 4 hours
  Medium velocity (drug_interactions): 24 hours
  Low velocity (genomics): 7 days
```

## Selective Ingestion Rules (Agent 5A)

New papers only enter corpus when they meet
at least one of these criteria:

1. Directly contradicts existing knowledge
2. Fills Agent 6 coverage gap (query_count >= 3)
3. High citation velocity (50+ citations total,
   or 10+ citations if year >= 2021)
4. Matches high-traffic query patterns
5. High quality recent paper (RCT/review, year >= 2021)

## Data Architecture

### Qdrant Collections

| Collection | Level | Content | Points |
|-----------|-------|---------|--------|
| failurerag_document | L1 | Full paper embedding | ~1,500 |
| failurerag_section | L2 | IMRAD section chunks | ~4,700 |
| failurerag_semantic | L3A | Sentence-boundary chunks | ~10,900 |
| failurerag_proposition | L3B | Atomic claims (Gemini) | ~5,500 |
| *_staging variants | Repair | Agent 4B validation | Variable |

### Supabase Tables

| Table | Purpose |
|-------|---------|
| ingestion_logs | Paper ingestion provenance |
| agent_failures | Repair cycle failure log |
| repair_history | Completed repairs with scores |
| repair_queue | Pending admin approvals |
| agent6_patterns | Detected failure patterns |
| agent6_gaps | Coverage gaps by query count |
| agent6_calibration | Per-cluster calibration curves |
| agent6_insights | Actionable recommendations |
| strategy_recommendations | Parameter change proposals |
| benchmark_questions | 50 QA pairs |
| benchmark_results | Weekly benchmark runs |
| user_feedback | Thumbs up/down ratings |
| user_profiles | Per-user learning data |

### Redis Keys

| Key Pattern | Content | TTL |
|------------|---------|-----|
| session:{id} | Conversation history | 2 hours |
| cache:{simhash} | Retrieved chunks | Dynamic (4h-7d) |
| topic_model:{id} | Session topic model | 2 hours |
| monitor:* | Stream monitor stats | 24 hours |
| Celery queues | high/medium/low_priority | — |

### Neo4j Graph

| Node/Relationship | Purpose |
|------------------|---------|
| (Paper) | All corpus papers with metadata |
| [:BELONGS_TO] → (TopicCluster) | Cluster membership |
| [:CONTRADICTS] | Detected contradictions |
| [:SUPERSEDES] | When new paper updates old |

## Advanced Features (v2.1)

### Conversation-Aware Retrieval
- SessionTopicModel extracts medical entities per session
- Retrieval biased toward session topics
- Topic change detection resets bias
- FollowUpResolver rewrites references using context

### Citation-Aware Retrieval
- GraphExpansionRetriever uses Neo4j citation graph
- Retrieves chunks from citation neighbors
- Graph-sourced chunks get 0.85 score penalty
- Falls back gracefully if Neo4j offline

### Structured Output Mode
- comparative query → comparison table
- list query → numbered list with citations
- summary query → KEY FINDING / EVIDENCE / LIMITATIONS
- default → conversational prose

### Claim-Level Provenance
- Every fact linked to exact source chunk
- Paper ID, year, journal per claim
- Confidence score per claim
- Source quote excerpt

### Confidence Intervals
- Wilson score interval for n >= 30
- Simple approximation for n >= 10
- Wide interval (±0.20) for n < 10
- Displayed as range bar in UI

### Multi-User Isolation
- Personal learning separate from global
- preferred_cluster per user_id
- Blended confidence: 70% global + 30% personal
- Requires user_id in ChatRequest

## Production Configuration

### Rate Limits
| Endpoint | Limit | Window |
|---------|-------|--------|
| /chat | 60 requests | 60 seconds |
| /admin | 100 requests | 60 seconds |
| /chat/stream | 20 requests | 60 seconds |

### Scheduled Jobs (APScheduler)
| Job | Schedule | Purpose |
|-----|---------|---------|
| Weekly benchmark | Sunday 2am | Track improvement |
| Daily insights | Daily 6am | Agent 6 generation |
| Freshness sweep | Every 3 days | Detect stale clusters |
| Daily monitor | Daily 4am | New paper detection |
| Gap sweep | Sunday 3am | Gap-targeted ingestion |

## Evaluation

### Baseline Benchmark (50 QA pairs)
- Overall pass rate: 86.7%
- Average confidence: 0.67
- Average response time: 12.5 seconds
- Question types: factual_recall, multi_hop,
  comparative, temporal, exploratory, adversarial

### Metrics tracked weekly
- Pass rate by question type
- Pass rate by difficulty
- Cache hit rate
- Cycle trigger rate
- Average confidence per cluster

# Self-Learning and Self-Healing RAG Architecture

## System Boundaries

Two parallel loops never block each other:

**Hot Path** (synchronous, user-facing):
User → Agent 1 → Agent 2 → [Repair Cycle] → Agent 7 → User

**Cold Path** (async, Celery workers):
Agent 4B, Agent 5A, Agent 5B, Agent 6

## Hot Path Detail

### Cache Check
Before Agent 1 runs:
- Embed query with S-PubMedBert
- Generate 32-bit SimHash from embedding
- Check Redis for cached chunks
- HIT: Agent 2 freshness+completeness only → Agent 7
- MISS: Full retrieval pipeline

### Agent 1 — Retrieval
1. QueryClassifier — Gemini Flash → 5 query types
2. MetadataPreFilter — pre-filter before vector search
3. HybridRetriever — dense + sparse → RRF → MMR
4. SufficiencyEvaluator — auto-relax if <3 chunks

### Agent 2 — Quality Gate (5 checks)
1. Retrieval Relevance — LLM per-chunk classification
2. Completeness Grounding — can query be fully answered?
3. Freshness — metadata analysis, triggers live fetch
4. Calibration — historical accuracy from Supabase
5. Cross-Chunk Contradiction — do chunks conflict?

All pre-generation. Nothing reaches Agent 7 without passing.

### Repair Cycle (A2→A3→A4A)
Max 2 iterations. 3 exit conditions:
1. Agent 2 passes → Agent 7
2. Max cycles → Agent 7 with honest flag
3. Class A/B diagnosis → exit immediately → queue 4B

### Agent 3 — Diagnosis
5 diagnostic tests:
1. Existence — does information exist in corpus?
2. Chunking Boundary — info split across chunks?
3. Embedding Space — BM25 vs vector gap?
4. Query Processing — expansion/strategy failure?
5. Metadata Filter — filters removed valid chunks?

### Agent 4A — Formulator
For Class C (query problems):
- Gap analysis: what aspects not covered?
- Coverage mapping: likely in corpus or not?
- Retrieval formulation: targeted sub-queries per gap
- Strategy selection: right strategy per sub-query
- Filter adjustment: tighten/loosen per sub-query

For knowledge_drift specifically:
- Live PubMed fetch via E-utilities API
- Papers queued for permanent ingestion via Celery

### Agent 7 — Generator
Receives from Agent 2:
- Verified chunks with quality scores
- Coverage map (which chunk covers which query aspect)
- Freshness per chunk
- Contradiction flags
- Calibration confidence recommendation

Receives from Redis:
- Last 6 conversation turns verbatim
- Older turns summarized by Gemini Flash

Generates:
- Natural conversational response
- Inline citations: (Chen 2023)
- Contradiction surfacing if chunks conflict
- Honest gap acknowledgment if aspects unanswerable

## Cold Path Detail

### Agent 4B — Background Repair
Triggered when Agent 3 diagnoses Class A/B failure.
Three repair types:
- rechunk — alternative chunking strategies
- reembed — synonym-augmented indexing
- metadata — fix contradiction flags and freshness scores

Always writes to staging collection first.
Validates with 3 test queries (avg score > 0.5).
Promotes to production only after validation.
Admin approval required if >50 papers affected.

### Agent 5A — Relevance Verification
4-check gate before any paper enters corpus:
1. Domain filter — biomedical relevance
2. Corpus relationship — contradiction/gap/recency
3. Evidence quality — assigns evidence level
4. Citation velocity — Semantic Scholar integration

Selective ingestion rules (any one sufficient):
- Contradicts existing knowledge
- Fills Agent 6 coverage gap
- High citation velocity (50+ citations)
- Matches high-traffic query patterns
- High quality recent paper (RCT/review, year >= 2021)

### Agent 6 — Longitudinal Learning
Observes every query result via observe_query_result().
Never acts directly on corpus.

Four outputs:
1. Failure patterns → admin insights
2. Calibration curves → Agent 2 confidence adjustment
3. Coverage gap map → Agent 5A ingestion priority
4. Topic velocity → CacheManager dynamic TTL

## Data Architecture

### Qdrant Collections
- selflearning_rag_document — L1: full paper embedding
- selflearning_rag_section — L2: IMRAD section chunks
- selflearning_rag_semantic — L3A: sentence-boundary chunks
- selflearning_rag_proposition — L3B: Gemini-extracted claims
- *_staging variants — for Agent 4B repair validation

### Supabase Tables
- ingestion_logs — paper ingestion provenance
- agent_failures — repair cycle failure log
- repair_history — completed repairs with scores
- repair_queue — pending admin approvals
- agent6_patterns — detected failure patterns
- agent6_gaps — coverage gaps by query count
- agent6_calibration — per-cluster calibration curves
- agent6_insights — actionable recommendations
- benchmark_questions — 15 QA pairs
- benchmark_results — weekly benchmark runs

### Redis Keys
- session:{id} — conversation history (2hr TTL)
- cache:{simhash} — retrieved chunks (dynamic TTL)
- Celery queues: high_priority, medium_priority, low_priority

### Neo4j Graph
- (Paper) nodes with all metadata
- [:BELONGS_TO] → (TopicCluster)
- [:CONTRADICTS] with confidence and topic
- [:SUPERSEDES] when new paper updates old

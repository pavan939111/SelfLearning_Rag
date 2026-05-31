# Changelog

## v2.3.1 — May 2026

### Robustness & Production-Grade Stabilization
- **Lazy HF Model Weight Initializations** — Converted `SentenceTransformer` (BiomedicalEmbedder) and `CrossEncoder` (LocalReranker) weight loading into lazy on-demand operations, dropping container cold-start footprint from **~650MB to ~42MB RAM** to prevent Cloud OOM killer risks.
- **Neo4j Connection Pool Optimization** — Promoted `Neo4jManager` to a module-level thread-safe singleton, reusing connection pools across multiple endpoints and evaluators to completely prevent socket leaks and connection exhaustion in `/chat` and `/chat/stream`.
- **LangGraph State Collision Resolution** — Renamed the node `"diagnosis"` to `"diagnose_failure"` in the StateGraph compilation to resolve state key namespace collisions.
- **Agent 7 Backwards Compatibility** — Added default `None` values for key parameters (`agent2_result`, `cycle_result`, etc.) inside `Agent7Generator.generate()` to prevent argument missing crashes in speculatively bypassed query execution pathways.
- **Robust Exception Handling in SSE Stream Endpoint** — Separated complex f-strings and dictionary structures in `/chat/stream` endpoints to bypass strict Python f-string compile constraints and format quotes cleanly.
- **Celery Worker Import Stabilizations** — Resolved verification framework imports by swapping `workers.celery_worker` with `workers.celery_app`.

## v2.3.0 — May 2026

### Latency & Concurrency Optimizations
- **Proactive Semantic Cache Lookup** — Lookup cache instantly before query classification, saving ~600ms on cache hits.
- **Speculative Parallel Retrieval** — Concurrently classify queries and retrieve unfiltered speculative chunks, hiding vector retrieval latency completely.
- **In-Memory Filter Matching** — Match speculative chunks against classification criteria in memory, bypassing secondary filtered retrievals for standard queries.
- **Concurrent Neo4j Prefetching** — Asynchronously prefetch paper metadata in parallel with Agent 2 Quality Gate LLM checks, hiding sequential Neo4j database latency completely (~150ms saved).
- **Stream-First Claim Provenance** — Decoupled conversational answer streaming from claim provenance computation. Conversational answer text streams instantly to `/chat/stream` SSE with 0s perceived latency, while citations and source references overlay dynamically a split-second later via background thread execution.

### Citation & Quality Gate Improvements
- **Unified Paper Authors Mapping** — Carried over paper authors list from original ingestion papers to chunk dataclasses, Qdrant payloads, Neo4j node properties, and final retrieval results.
- **First-Word Journal Citation Fallback** — Replaced generic `(Unknown 2020)` citation keys with premium first-word journal fallbacks (e.g. `(Lancet 2020)`).
- **Automated Suffix Disambiguation** — Automatically disambiguates duplicate citation keys (e.g. `Smith 2020a`, `Smith 2020b`) for papers in the same response.
- **Normalized Claim Provenance Matching** — Enhanced LLM-to-chunk UUID matching to safely resolve varied LLM formatting (e.g., brackets, spaces, casing).
- **Fast-Track Skip Quality Gate Bypassing** — Dynamically routes to Agent 7 generation when relevance is $\ge 70\%$ and completeness passes, avoiding diagnostic cycles when evidence is sufficient.

## v2.2.0 — May 2026

### New Features
- **ReAct Thought Traces** — every key agent decision now emits OBS/THK/ACT/OUT reasoning. Stored in Supabase. Visible in transparency mode with "REASONING ON" toggle.
- **Domain Validation** — QueryClassifier rejects non-biomedical questions in the same Gemini call that does classification. No extra API calls.
- **LinkedIn Diagrams** — 5 professional architecture diagrams generated and saved to `linkedin/` folder.

### Improvements
- README rewritten with Mermaid diagrams that render on GitHub
- All markdown files updated with correct information
- React Router v7 future flags added (suppresses console warnings)

---

## v2.1.0 — May 2026

### Architecture
- All inter-agent contracts migrated to Pydantic BaseModel
- PipelineState object flows through entire hot path
- Nine agents with clean single responsibilities

### New Features
- Structured output: table/list/summary/prose auto-detected per query type
- Claim-level provenance — every fact linked to exact source chunk
- User feedback loop (thumbs up/down) feeds Agent 6 calibration
- Conversation-aware retrieval with SessionTopicModel
- Citation-aware retrieval via Neo4j graph expansion
- Continuous stream monitor — checks for new papers daily
- Predictive analytics in admin dashboard
- Proactive contradiction surfacing
- Query suggestions when corpus has gaps
- Confidence intervals — Wilson score, not point estimates
- Multi-user isolation with personal learning
- Production rate limiting via Redis

### Evaluation
- Benchmark expanded from 15 to 50 QA pairs
- 5 question types + adversarial category added
- Baseline: 86.7% pass rate, 0.67 avg confidence

---

## v2.0.0 — April 2026

### Initial Release
- Nine-agent architecture
- Ingestion pipeline for 1,767 PubMed papers
- Hybrid retrieval: dense + sparse + RRF + MMR
- Pre-generation quality gate (Agent 2)
- A2→A3→A4A repair cycle
- Semantic hash cache (3.4× speedup)
- Conversational memory with Redis sessions
- Agent 6 longitudinal learning
- FastAPI backend with SSE streaming
- Vite + React frontend: Chat, Transparency, Admin pages

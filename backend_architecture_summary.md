# FailureRAG Backend Architecture Summary

## Quick Reference

**Entry point:** uvicorn api.main:app --port 8000
**Workers:** python start_worker.py
**Ingestion:** python run_ingestion.py

## API Endpoints

### Chat
POST /chat
  Body: {session_id, query, top_k, user_id}
  Returns: {answer, citations, confidence,
            confidence_lower, confidence_upper,
            output_format, claim_provenance,
            cache_hit, cycle_ran, live_fetch_used,
            query_suggestions, processing_time_ms}

POST /chat/feedback
  Body: {session_id, query, answer, rating,
         topic_cluster, confidence, cycle_ran}
  Returns: {success: true}

GET /chat/stream?session_id=X&query=Y
  Returns: SSE stream of agent activity events
  Event types: cache, agent1, agent2, agent3,
               agent4a, agent7, system

### Health
GET /health
  Returns: {status, databases, agents, system}

### Admin
GET  /admin/stats
GET  /admin/corpus-health
GET  /admin/pending-approvals
POST /admin/approve-repair/{id}
GET  /admin/benchmark-trend
GET  /admin/latest-benchmark
GET  /admin/strategy-recommendations
POST /admin/approve-strategy/{id}
GET  /admin/repair-history

## Key Design Decisions

### Why pre-generation evaluation?
Agent 2 evaluates chunks BEFORE generation.
Zero wasted LLM calls on bad evidence.
Generation is guaranteed to be grounded.

### Why merge-not-replace in repair cycle?
Agent 4A finds missing pieces via targeted sub-queries.
New chunks merged with original good chunks.
Agent 7 gets most complete picture possible.

### Why cache chunks not answers?
Generated answers must adapt to conversation context.
Cache the expensive part — retrieval.
Agent 7 always generates fresh from cached chunks.

### Why Celery for repairs?
Background repairs must never block the user.
Three priority queues ensure hot path
never waits for corpus repairs.

### Why Pydantic for inter-agent communication?
Type safety at agent boundaries.
ValidationError caught immediately at source.
Automatic Redis serialization (model_dump_json).
LangGraph-ready for future migration.

## File Structure

agents/
  models.py           — All Pydantic inter-agent contracts
  agent1_retrieval.py — QueryClassifier, MetadataPreFilter,
                        HybridRetriever, GraphExpansionRetriever
  agent2_evaluator.py — Agent2Evaluator (5 checks)
  agent3_classifier.py — Agent3Classifier (5 diagnostic tests)
  agent4a_formulator.py — Agent4AFormulator + knowledge_drift
  agent4b_repair.py   — Agent4BRepair (Celery queue interface)
  agent5a_verifier.py — Agent5AVerifier (citation velocity)
  agent6_learning.py  — Agent6Learning (all learning loops)
  agent7_generator.py — Agent7Generator (structured output)
  cache_manager.py    — CacheManager (SimHash + dynamic TTL)
  conversation_memory.py — ConversationMemory + SessionTopicModel
  live_fetcher.py     — LiveFetcher (PubMed E-utilities)
  live_fetch_ingester.py — LiveFetchIngester
  repair_cycle.py     — RepairCycle (A2→A3→A4A)
  stream_monitor.py   — StreamMonitor (daily sweep)

api/
  main.py             — FastAPI app + APScheduler
  routes/
    chat.py           — POST /chat + SSE /chat/stream
    health.py         — GET /health
    admin.py          — All /admin/* endpoints
  models/
    requests.py       — ChatRequest, AdminApprovalRequest
    responses.py      — ChatResponse, HealthResponse

database/
  qdrant_client.py    — QdrantManager (4 collections + staging)
  supabase_client.py  — SupabaseManager (all tables)
  neo4j_client.py     — Neo4jManager (graph operations)
  redis_client.py     — RedisManager (cache + queues)

ingestion/
  fetcher.py          — PubMedFetcher, PaperRecord
  chunker.py          — HierarchicalChunker (4 levels)
  embedder.py         — BiomedicalEmbedder (S-PubMedBert)
  pipeline.py         — IngestionPipeline + IngestionStats

workers/
  celery_app.py       — Celery config (3 priority queues)
  repair_tasks.py     — rechunk, reembed, metadata,
                        live_fetch_papers, log_failure

scripts/
  run_ingestion.py    — Full corpus ingestion
  run_benchmark.py    — Benchmark runner
  seed_benchmarks.py  — Seed 50 QA pairs
  backfill_neo4j.py   — Populate Neo4j from corpus
  verify_all_phases.py — Complete system verification

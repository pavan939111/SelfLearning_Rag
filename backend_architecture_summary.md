# FailureRAG Backend Architecture & Current State

## 1. Core Databases
- **Qdrant**: Vector database storing document, section, semantic, and proposition level embeddings (768 dimensions) using `BiomedicalEmbedder`. Includes Staging collections for safe chunk repair testing before production promotion.
- **Supabase**: PostgreSQL database storing relational data, including `benchmark_results`, `agent6_insights`, `repair_queue` (pending admin approvals), and `agent_failures`.
- **Neo4j AuraDB**: Graph database linking Papers and Entities/Topics for citation velocity and graph-based retrieval.
- **Redis**: Serves as the high-speed Semantic Cache (using SimHash for fast retrieval) and as the message broker for background Celery tasks.

## 2. Multi-Agent Pipeline

### Agent 1: Retrieval
- **QueryClassifier**: Extracts user intents, main topics, and medical entities.
- **MetadataPreFilter**: Generates Qdrant filters for precise, focused search.
- **HybridRetriever**: Pulls relevant chunks from the hierarchical Qdrant collections.

### Agent 2: Quality Gate (Evaluator)
- Evaluates retrieved chunks for **Freshness**, **Completeness/Grounding**, and **Calibration**. 
- If chunks fail any test (e.g., the chunks are outdated or don't fully answer the query), it halts generation and escalates the query to Agent 3.

### Agent 3: Diagnostic Classifier
- Determines the exact root cause of the retrieval failure (e.g., "query too narrow", "knowledge gap", "chunking boundary error").
- Classifies the failure into severity classes (A, B, C) and routes to either Agent 4A or 4B.

### Agent 4A & 4B: Repair Cycle
- **Agent 4A (Runtime Repair)**: Immediately modifies the query or prompts a re-retrieval (e.g., expanding or narrowing search terms).
- **Agent 4B (Corpus Repair)**: Identifies structural issues (e.g., poor chunking). If a fix affects > 50 papers, it routes a request to the Admin `repair_queue`. It promotes repaired chunks to a Qdrant **Staging Collection** first, validates them using test queries (avg_score > 0.5), and only then promotes to Production.

### Agent 5A: Selective Ingestion
- Evaluates new papers before they enter the corpus.
- Employs strict ingestion rules:
  1. Contradiction Detection (avoids duplicating or conflicting with existing knowledge).
  2. Fills known Agent 6 coverage gaps.
  3. Matches high-traffic query patterns.
  4. High citation velocity / Recency constraints.

### Agent 6: Continuous Learning
- Observes the results of the multi-agent pipeline globally.
- Writes findings to `agent6_insights` in Supabase.
- Maps knowledge coverage gaps and tracks topic query velocity to dynamically tune Redis cache TTLs.

### Agent 7: Generator
- The final step in the hot path. Generates clinical responses using the successfully retrieved (or repaired) chunks.
- Injects explicit citation markers, confidence scores, and necessary "gap acknowledgments" if the answer is incomplete.

## 3. APIs and Infrastructure
- **FastAPI**: Main backend running on port 8000. Includes `/api/chat` for the hot path and `/admin` endpoints for system stats and repair approvals.
- **Celery & Celery Beat**: Manages asynchronous background workers like `live_fetch_ingester` and `rechunk_documents`.
- **Semantic Cache (`CacheManager`)**: Maps similar query embeddings to saved retrieval chunks to bypass Qdrant and LLM execution entirely for repeat queries, granting massive speedups.

## 4. Next Steps for Frontend Integration
To proceed with the frontend build, your UI will interact directly with these established boundaries:

- **Chat Interface**: Needs to POST to `/api/chat` with `{ "session_id": "...", "query": "..." }`. The frontend must parse the response to display the `answer`, `citations`, `confidence`, and whether a `cycle_ran` (to show the user that the agent had to "think harder" and perform a self-repair).
- **Admin Dashboard**: Needs to GET `/admin/stats` and GET `/admin/pending-approvals` to display system health and allow administrators to click "Approve" or "Reject" on large-scale Agent 4B structural repairs.
- **Graph Visualization**: Future integration with Neo4j to visualize topic clusters and paper citations directly in the browser.

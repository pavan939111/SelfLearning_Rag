# Changelog

## v2.2.0 — May 2026

### ReAct Thought Traces
- ThoughtTrace Pydantic model in agents/models.py
- ThoughtLogger utility in utils/thought_logger.py
- All 5 hot-path agents emit OBS/THK/ACT/OUT traces
- thought_traces table in Supabase for audit log
- SSE stream emits trace events with type='thought'
- ThoughtTraceCard component in transparency mode
- "REASONING ON/OFF" toggle in AgentFeed
- Default OFF — users opt in to see reasoning

### Domain Validation
- QueryClassifier detects off-topic queries
- Single Gemini call handles both domain check
  AND query classification — no extra API calls
- domain_rejected field in QueryClassification
  and ChatResponse
- Helpful rejection message with biomedical examples
- Clickable query suggestion chips in UI

## v2.1.0 — May 2026

### Architecture
- All inter-agent contracts migrated to Pydantic BaseModel
- PipelineState flows through entire hot path
- Nine agents with clean single responsibilities
- 32-bit SimHash semantic cache (vs 8-bit in v2.0)

### New Agents
- Agent 7 — Conversational Response Generator
  (previously generation was inside Agent 1)

### New Features — Generation
- Structured output: table/list/summary/prose auto-detected
- Claim-level provenance — every fact linked to source chunk
- Confidence intervals (Wilson score, not point estimates)
- Query suggestions when corpus has coverage gaps
- Proactive contradiction surfacing from Neo4j graph

### New Features — Retrieval
- Conversation-aware retrieval with SessionTopicModel
- Follow-up question resolution before retrieval
- Citation-aware retrieval via Neo4j graph expansion
- GraphExpansionRetriever adds citation neighbors

### New Features — Learning
- User feedback loop (thumbs up/down → Agent 6)
- Feedback-weighted calibration (user signal 2× weight)
- Strategy recommendations with admin approval workflow
- Config override system for approved parameter changes
- Predictive analytics (freshness forecasts, volume trends)

### New Features — Ingestion
- Citation velocity via Semantic Scholar API
- Continuous stream monitor (daily sweep)
- Gap-targeted weekly sweep
- Admin approval workflow for large corpus changes
- Staging validation before production promotion

### New Features — Multi-User
- user_id in ChatRequest (optional)
- Personal learning separate from global
- Blended confidence: 70% global + 30% personal

### New Features — Production
- Redis-based rate limiting (replaces in-memory)
- Structured health endpoint with latency metrics
- Request ID in all responses for traceability
- APScheduler: 5 scheduled jobs

### Evaluation
- Benchmark expanded: 15 → 50 QA pairs
- 5 question types + adversarial category
- Baseline: 86.7% pass rate, 0.67 avg confidence
- Weekly automated benchmark tracking

## v2.0.0 — April 2026

### Initial Release
- 9-agent architecture designed
- Core ingestion pipeline (1,767 PubMed papers)
- Hybrid retrieval: dense + sparse + RRF + MMR
- Pre-generation quality gate (Agent 2)
- A2→A3→A4A repair cycle
- Semantic hash cache
- Conversational memory (Redis sessions)
- Agent 6 longitudinal learning
- FastAPI backend
- Vite + React frontend (Chat, Transparency, Admin)
- SSE streaming for transparency mode
- Baseline benchmark: 86.7% on 15 QA pairs

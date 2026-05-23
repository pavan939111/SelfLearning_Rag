# Changelog

## v2.1.0 — May 2026

### Architecture
- Migrated all inter-agent contracts to Pydantic BaseModel
- Added PipelineState flowing through hot path
- Nine agents: Retrieval, Quality Gate, Diagnosis,
  Formulator, Background Repair, Verification,
  Ingestion, Learning, Generator

### New Features
- Structured output mode (table/list/summary/prose)
- Claim-level provenance for every fact
- User feedback loop (thumbs up/down)
- Conversation-aware retrieval with session topic model
- Citation-aware retrieval via Neo4j graph expansion
- Continuous stream monitor for daily corpus updates
- Predictive admin analytics
- Proactive contradiction surfacing
- Query suggestions from coverage gap map
- Confidence intervals (not just point estimates)
- Multi-user isolation with personal learning
- Production hardening: auth, rate limiting, observability

### Self-Healing Improvements
- A2→A3→A4A repair cycle with merge-not-replace
- Agent 4A handles knowledge_drift via live PubMed fetch
- Agent 4B staging validation before production promotion
- Admin approval workflow for large corpus changes

### Self-Learning Improvements
- Agent 6 observes user feedback signals
- Dynamic cache TTL from topic velocity
- Calibration curves read by Agent 2 dynamically
- Strategy recommendations with approval workflow
- Coverage gap map drives selective ingestion

### Evaluation
- Expanded benchmark: 50 QA pairs across 5 types
- Baseline pass rate: 86.7%
- Weekly automated benchmark tracking improvement

## v2.0.0 — Initial Release
- Core ingestion pipeline (1,767 PubMed papers)
- Hybrid retrieval (dense + sparse + RRF + MMR)
- Pre-generation quality gate
- Basic repair cycle
- Conversational memory
- FastAPI backend
- Vite + React frontend

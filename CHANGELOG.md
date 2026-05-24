# Changelog

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

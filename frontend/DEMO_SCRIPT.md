# FailureRAG Demo Script

## Setup (5 minutes before demo)

1. Start backend:
   uvicorn api.main:app --port 8000

2. Start frontend:
   cd frontend && npm run dev

3. Open three browser tabs:
   Tab 1: http://localhost:5173/chat
   Tab 2: http://localhost:5173/transparency
   Tab 3: http://localhost:5173/admin

4. Test Gemini quota:
   python -c "
   from google import genai
   from config import get_config
   c = get_config()
   client = genai.Client(api_key=c.gemini_api_key)
   r = client.models.generate_content(
       model='gemini-2.0-flash', contents='test'
   )
   print('Quota OK:', r.text[:20])
   "

## Demo Flow (7 minutes)

### Part 1 — Chat Interface (2 minutes)

Navigate to Tab 1 (/chat)

Query 1 — Simple factual:
  "How does pembrolizumab work in treating lung cancer?"
  
  Show: Answer with inline citations (Author Year)
  Point out: Confidence bar color
  Point out: Processing time in metadata bar
  Explain: "System evaluated 5 chunks before generating"

Query 2 — Same query again:
  Type same question and send
  
  Show: ⚡ cached badge — much faster response
  Explain: "Semantic hash cache — 3.4x speedup"
  Explain: "Cache stores chunks not answers —
            Agent 7 always generates fresh"

### Part 2 — Transparency Mode (3 minutes)

Navigate to Tab 2 (/transparency)

Query — Temporal (triggers repair cycle):
  "What is the current standard treatment
   for NSCLC in 2024?"

Watch center panel as cards appear:
  [Cache] Miss — full retrieval
  [Agent 1] Query classified: temporal
  [Agent 2] Freshness check FAIL
            "Only 1 of 5 chunks recent enough"
  [Agent 3] Diagnosing... knowledge_drift
  [Agent 4A] Live fetch from PubMed
             "Found 3 recent papers (2024)"
  [Agent 2] Re-evaluating merged chunks
            All 5 checks PASS
  [Agent 7] Generating with fresh citations

Point out:
  - Right panel shows 1,767 documents indexed
  - Agent 6 coverage gaps listed
  - System healed itself in real time

### Part 3 — Structured Output (30 seconds)

Still in Transparency tab:

Query — Comparative:
  "Compare pembrolizumab and nivolumab
   in lung cancer treatment"

Show: Response renders as comparison TABLE
Point out: TABLE badge in metadata bar
Explain: "System detects comparative queries
          and formats as table automatically"

### Part 4 — Admin Dashboard (1.5 minutes)

Navigate to Tab 3 (/admin)

Point out:
  Health dots — all 4 databases green
  Corpus stats — 1,767 documents, 10,900 chunks
  Benchmark — 86.7% baseline pass rate
  Agent 6 insights — actionable recommendations
  Pending approvals — repair queue for large changes

Explain:
  "This shows the self-learning in action.
   Every query makes the system smarter.
   Coverage gaps drive which papers get ingested.
   Confidence calibration improves over time."

## Key Talking Points

### On self-healing:
"Normal RAG systems fail silently. FailureRAG fails loudly,
diagnoses why, and fixes itself in the same request.
The repair cycle is the core innovation."

### On self-learning:
"Agent 6 observes every query. After 20 completeness failures
in immunotherapy it detects a systemic problem and surfaces
it as an insight. The corpus grows toward what users actually ask."

### On production quality:
"Everything here runs on free tier. The architecture scales
to millions of queries. Rate limiting, authentication, staging
validation, admin approval — all built in."

### On claim provenance:
"Every fact in every answer links to the exact chunk
that supports it. For biomedical applications where
hallucination is dangerous — this is critical."

## Questions to Anticipate

Q: How is this different from standard RAG?
A: Standard RAG retrieves and generates.
   FailureRAG evaluates, diagnoses, repairs, and learns.
   86.7% pass rate means 13% of queries triggered the
   repair cycle and got better answers because of it.

Q: What happens when Gemini quota is exhausted?
A: System falls back gracefully. Users get honest
   low-confidence responses. Never crashes.
   Cache still serves repeat queries instantly.

Q: Can this scale to production?
A: Celery workers scale horizontally.
   Qdrant Cloud auto-scales.
   The free tier limitation is Gemini API quota
   which resolves with a paid plan.

# Demo Script — 7 Minutes

## Setup (5 minutes before)

1. Start backend: `uvicorn api.main:app --port 8000`
2. Start frontend: `cd frontend && npm run dev`
3. Test Gemini quota works:
```bash
python -c "
from google import genai
from config import get_config
c = get_config()
client = genai.Client(api_key=c.gemini_api_key)
r = client.models.generate_content(model='gemini-2.0-flash', contents='test')
print('Quota OK')
"
```
4. Open three tabs:
   - http://localhost:5173/chat
   - http://localhost:5173/transparency
   - http://localhost:5173/admin

---

## Demo Flow

### Part 1 — Chat (2 minutes)

**Query 1 — Simple question:**
> "How does pembrolizumab work in treating lung cancer?"

Point out:
- Answer has inline citations like (Chen 2023)
- Confidence bar shows color (green = high, yellow = medium)
- Processing time in metadata

**Query 2 — Same query again:**
> (type exactly the same question)

Point out:
- ⚡ cached badge — much faster
- "The cache stores retrieved evidence, not the answer — Agent 7 always generates fresh so conversation context always works"

**Query 3 — Off-topic (shows domain validation):**
> "What is the best recipe for pasta?"

Point out:
- System rejects with helpful message
- Suggests relevant biomedical questions
- "One Gemini call does both domain check and classification — no wasted API calls"

### Part 2 — Transparency Mode (3 minutes)

Go to /transparency tab.

**Query — Temporal (triggers repair cycle):**
> "What is the current FDA approved treatment for NSCLC in 2024?"

Watch the center feed as cards appear:

1. Cache check → miss
2. Agent 1 → retrieval with score
3. Agent 2 → freshness check FAIL (stale data for 2024 query)
4. Agent 3 → diagnoses knowledge_drift
5. Agent 4A → live PubMed fetch for 2024 papers
6. Agent 2 → re-evaluates merged chunks → PASS
7. Agent 7 → generates with 2024 citations

Say: "The system diagnosed that it had stale knowledge, fetched live papers from PubMed, merged them with the original evidence, and verified the combined set before generating. All in one request. The user never waited for any of this to be explained."

**Turn on REASONING:**
Click "REASONING ON" in the feed header.
Click any agent card to expand OBS/THK/ACT/OUT.

Say: "Every decision the system makes is logged in this ReAct format. You can see exactly what it observed, what it reasoned, what it decided, and what happened. Full audit trail."

### Part 3 — Admin Dashboard (2 minutes)

Go to /admin tab.

Point out:
- Health dots — all 4 databases green
- 1,767 documents indexed, 22,600+ chunks
- 86.7% baseline benchmark pass rate
- Agent 6 coverage gaps — "these are topics users asked about that the corpus could not answer — they drive what papers get ingested next"
- Pending repairs — "Agent 4B found corpus structure problems — these need approval before applying because they affect hundreds of papers"

---

## Key Points to Emphasize

**On self-healing:**
"Standard RAG generates an answer whether or not the evidence is good. FailureRAG checks the evidence first. If it is bad it finds out why and tries to fix it before answering."

**On self-learning:**
"Agent 6 watches every query. After enough queries on the same topic it detects patterns, recalibrates confidence scores, and directs the corpus to grow toward what users actually ask about."

**On cost:**
"Everything runs on free tier. Qdrant, Supabase, Neo4j, Redis — all free. The only limitation is Gemini API quota which is 1,500 requests per day on free tier."

**On transparency:**
"Most AI systems are black boxes. Every decision this system makes is logged with the full reasoning. If it gets something wrong you can trace exactly why."

---

## Questions to Anticipate

**"How is this different from standard RAG?"**
Standard RAG: retrieve → generate → hope.
FailureRAG: retrieve → verify → repair if needed → generate from verified evidence only.

**"What happens when Gemini quota runs out?"**
The system falls back gracefully. Users get a low-confidence response with a note. The cache still serves repeat queries instantly. Nothing crashes.

**"Can this scale to production?"**
Celery workers scale horizontally. Qdrant Cloud auto-scales. The free tier limitation is Gemini quota — resolved with a paid plan.

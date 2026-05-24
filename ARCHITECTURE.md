# Self-Learning and Self-Healing RAG — Architecture

Technical reference for engineers who want to understand exactly how the system works.

---

## System Overview

Two parallel loops run at all times:

**Hot path** — synchronous, handles your query in real time (target: under 15 seconds)

**Cold path** — asynchronous Celery workers, keeps the corpus healthy in the background

```mermaid
flowchart LR
    subgraph HOT ["⚡ Hot Path — your query"]
        H1[Agent 1\nRetrieval] --> H2[Agent 2\nQuality Gate]
        H2 -->|pass| H7[Agent 7\nGenerator]
        H2 -->|fail| H3[Agent 3\nDiagnosis]
        H3 --> H4A[Agent 4A\nFormulator]
        H4A --> H1
    end

    subgraph COLD ["🌙 Cold Path — background workers"]
        C4B[Agent 4B\nCorpus Repair]
        C5A[Agent 5A\nVerification]
        C5B[Agent 5B\nIngestion]
        C6[Agent 6\nLearning]
    end

    H2 -->|Class A/B failure| C4B
    H7 --> C6
    C6 -.->|calibration| H2
    C6 -.->|TTL settings| CACHE[(Redis Cache)]
    CACHE -.->|cache hit| H2

    style HOT fill:#0a1a2a,stroke:#00d4ff
    style COLD fill:#1a0a2a,stroke:#a855f7
```

---

## Query Classification and Domain Check

The first thing that happens when you ask a question. One Gemini call does both jobs simultaneously.

```mermaid
flowchart TD
    Q["User query"] --> GEMINI["Gemini Flash\nSingle API call"]

    GEMINI --> DOM{"Is it\nbiomedical?"}
    DOM -->|No| REJ["Return rejection\nwith examples\ndomain_rejected=True"]
    DOM -->|Yes| TYPE{"Query type?"}

    TYPE -->|simple_factual| T1["Single concept\nstraight lookup"]
    TYPE -->|multi_hop| T2["Connect multiple\nconcepts"]
    TYPE -->|comparative| T3["Side by side\ncomparison → table output"]
    TYPE -->|temporal| T4["Current state\ntighter freshness filter"]
    TYPE -->|exploratory| T5["Open ended\nbroader search"]

    style GEMINI fill:#1a2a4a,stroke:#4a9eff,color:#4a9eff
    style REJ fill:#3a1a1a,stroke:#ff4d6d,color:#ff4d6d
    style T3 fill:#1a3a1a,stroke:#00e5a0,color:#00e5a0
```

---

## Agent 1 — Retrieval

```mermaid
flowchart TD
    CLASS[Query Classification] --> FILTER

    FILTER["Metadata Pre-Filter\napplied BEFORE vector search\nnot after"]

    FILTER -->|temporal query| TF["Year >= 2022\nfreshness > 0.5\ntopic cluster match"]
    FILTER -->|simple factual| SF["Topic cluster match\nno date restriction"]
    FILTER -->|exploratory| EF["Minimal filter\nbroad search"]

    TF & SF & EF --> SEARCH

    subgraph SEARCH ["Hybrid Search"]
        DENSE["Dense Search\nS-PubMedBert 768d\nMeaning-based"]
        SPARSE["Sparse Search\nBM25 keyword\nTerm-based"]
        DENSE & SPARSE --> RRF["RRF Fusion\nCombines both scores"]
        RRF --> MMR["MMR Reranking\nDiversity + relevance\nλ = 0.7"]
    end

    MMR --> GE["Graph Expansion\nNeo4j citation neighbors\n0.85× score penalty"]
    GE --> SAFE["Safeguard\nFewer than 3 chunks?\nAuto-relax filter and retry"]
    SAFE --> OUT["Top 5 chunks\nto Agent 2"]

    style FILTER fill:#1a3a4a,stroke:#00d4ff,color:#00d4ff
    style RRF fill:#2a2a1a,stroke:#ffd60a,color:#ffd60a
    style MMR fill:#2a2a1a,stroke:#ffd60a,color:#ffd60a
    style SAFE fill:#2a1a0a,stroke:#ff8c42,color:#ff8c42
    style OUT fill:#1a3a1a,stroke:#00e5a0,color:#00e5a0
```

---

## Agent 2 — Quality Gate

The most important agent. Nothing reaches Agent 7 without passing here.

| Check | Method | Blocking? | On fail |
|-------|--------|-----------|---------|
| Relevance | Gemini Flash scores each chunk | Yes | Enter repair cycle |
| Completeness | Gemini Flash checks full coverage | Yes | Enter repair cycle |
| Freshness | Metadata analysis, no LLM | No | Set live_fetch flag |
| Calibration | Read Agent 6 curves from Supabase | No | Adjust confidence |
| Contradiction | Gemini Flash compares chunks | No | Flag for Agent 7 |

**Calibration detail:**
- Reads actual pass rate history from Supabase per topic cluster
- User thumbs up/down weighted 2× vs agent signal
- Returns confidence interval not just a point estimate
- Falls back to corpus-size tiers if no history yet

---

## Agent 3 — Root Cause Classifier

Runs when Agent 2 fails. Five diagnostic tests:

```mermaid
flowchart TD
    FAIL["Agent 2 FAIL\nwhich check failed?"] --> T1

    T1["Test 1 — Existence\nDoes information exist\nin corpus at all?\n8 query variations"] -->|Not found| CA["Class B\nKnowledge gap"]
    T1 -->|Found| T2

    T2["Test 2 — Chunking\nIs info split across\nchunk boundaries?"] -->|Split| CB["Class A\nData problem"]
    T2 -->|Not split| T3

    T3["Test 3 — Embedding\nBig gap between\nBM25 and vector scores?"] -->|Big gap| CC["Class A\nEmbedding mismatch"]
    T3 -->|No gap| T4

    T4["Test 4 — Query\nWas the search strategy\nwrong for this query?"] -->|Wrong strategy| CD["Class C\nQuery problem"]
    T4 -->|Strategy OK| T5

    T5["Test 5 — Filter\nDid metadata filter\nremove good chunks?"] -->|Over-filtered| CE["Class C\nFilter problem"]

    CA & CB & CC --> ROUTE4B["Route to Agent 4B\nbg corpus repair\nExit immediately"]
    CD & CE --> ROUTE4A["Route to Agent 4A\nRepair this query\nRight now"]

    style CA fill:#3a1a1a,stroke:#ff4d6d,color:#ff4d6d
    style CB fill:#3a1a1a,stroke:#ff4d6d,color:#ff4d6d
    style CC fill:#3a1a1a,stroke:#ff4d6d,color:#ff4d6d
    style CD fill:#2a1a0a,stroke:#ff8c42,color:#ff8c42
    style CE fill:#2a1a0a,stroke:#ff8c42,color:#ff8c42
    style ROUTE4B fill:#2a1a2a,stroke:#a855f7,color:#a855f7
    style ROUTE4A fill:#2a1a0a,stroke:#ff8c42,color:#ff8c42
```

---

## Agent 4A — Formulator

Handles Class C failures (query problems). Gets another chance to find the right evidence.

```mermaid
flowchart LR
    IN["Class C diagnosis\n+ original chunks"] --> GAP

    GAP["Gap Analysis\nWhat aspects of the\nquery are not covered\nby existing chunks?"]

    GAP --> FORM["Formulate sub-queries\nOne targeted query\nper missing aspect"]

    FORM --> FETCH{"knowledge_drift\ndiagnosis?"}
    FETCH -->|Yes| LIVE["Live PubMed fetch\nGet papers from\nlast 30 days\nQueue for permanent ingestion"]
    FETCH -->|No| NORMAL["Re-retrieve\nfrom corpus with\nbetter strategy"]

    LIVE & NORMAL --> MERGE["Merge + Deduplicate\nnew chunks with\noriginal chunks"]
    MERGE --> OUT["Back to Agent 2\nfor re-evaluation"]

    style GAP fill:#2a1a0a,stroke:#ff8c42,color:#ff8c42
    style LIVE fill:#1a2a3a,stroke:#60a5fa,color:#60a5fa
    style MERGE fill:#2a2a1a,stroke:#ffd60a,color:#ffd60a
    style OUT fill:#1a3a4a,stroke:#00d4ff,color:#00d4ff
```

---

## Agent 6 — Learning Architecture

```mermaid
flowchart TD
    subgraph IN ["Every query feeds Agent 6"]
        I1["Query result\n✓ or ✗"]
        I2["User feedback\n👍 👎"]
        I3["Weekly benchmark"]
    end

    IN --> OBS["Observe and record\nin Supabase tables"]

    OBS --> P1["Pattern detection\nSame failure type\n5+ times = pattern\n20+ times = high severity"]
    OBS --> P2["Calibration tracking\nExpressed confidence\nvs actual pass rate\nper topic cluster"]
    OBS --> P3["Gap map\nWhich topics get\nasked but not answered?"]
    OBS --> P4["Topic velocity\nHow fast is this\ntopic changing?"]

    P1 --> D1["Admin dashboard\nactionable insights"]
    P2 --> D2["Agent 2 reads\ncalibration dynamically\nmore honest scores"]
    P3 --> D3["Agent 5A priority\ncorpus grows toward\nwhat users actually need"]
    P4 --> D4["Cache TTL\nimmu 4hr · drug 24hr\ngenomics 7 days"]

    style OBS fill:#3a1a3a,stroke:#e879f9,color:#e879f9
```

---

## Agent 7 — Generator

Produces the final answer. Receives everything the pipeline discovered.

**Inputs from pipeline:**
- Verified chunks with quality scores
- Coverage map — which chunk answers which part of the query
- Freshness score per chunk
- Contradiction flags
- Calibrated confidence with interval
- Conversation history (last 6 turns verbatim + summary of older turns)
- Gap acknowledgment if some aspects not covered

**Output format detection:**

```mermaid
flowchart LR
    Q["Query type\n+ keywords"] --> DET

    DET{"Detect\nformat"}
    DET -->|comparative + 2 entities| TABLE["Table format\nFeature comparison"]
    DET -->|list · what are · side effects| LIST["Numbered list\nEach item cited"]
    DET -->|summarize · overview · explain| SUMMARY["Structured summary\nFinding + Evidence\n+ Limitations"]
    DET -->|everything else| PROSE["Prose\nConversational\nwith citations"]

    style TABLE fill:#1a3a1a,stroke:#00e5a0,color:#00e5a0
    style LIST fill:#1a3a1a,stroke:#00e5a0,color:#00e5a0
    style SUMMARY fill:#1a3a1a,stroke:#00e5a0,color:#00e5a0
    style PROSE fill:#1a3a1a,stroke:#00e5a0,color:#00e5a0
```

**Claim provenance:** After generating, Agent 7 uses Gemini to link every specific fact in the answer back to the exact chunk that supports it. Each claim shows paper ID, year, journal, and a source quote.

---

## Semantic Cache

```mermaid
flowchart LR
    Q["Query embedding\n768 dimensions"] --> HASH["32-bit SimHash\nseed=42\nconsistent hash"]
    HASH --> KEY["Redis key\ncache:{8-char-hex}"]
    KEY --> CHECK{"Cache hit?"}
    CHECK -->|Hit| VERIFY["Agent 2\nfreshness + completeness\nonly — 2 checks"]
    CHECK -->|Miss| FULL["Full pipeline\nAll 9 agents"]
    VERIFY -->|Pass| A7["Agent 7\ngenerates fresh\nfrom cached chunks"]
    VERIFY -->|Fail| FULL
    FULL --> STORE["Store chunks\nnot answers\nAgent 7 always\ngenerates fresh"]

    style HASH fill:#2a1a0a,stroke:#ff8c42,color:#ff8c42
    style VERIFY fill:#1a3a4a,stroke:#00d4ff,color:#00d4ff
    style A7 fill:#1a3a1a,stroke:#00e5a0,color:#00e5a0
```

**Important:** The cache stores retrieved chunks not generated answers. Agent 7 always generates fresh. This means context-aware conversation always works correctly.

---

## ReAct Thought Traces

Every key decision in every agent is logged in OBS/THK/ACT/OUT format:

- **OBS** — what the agent observed (data, scores, counts)
- **THK** — what it reasoned (why this matters, what it implies)
- **ACT** — what action it decided to take
- **OUT** — what the outcome was

Stored in Supabase `thought_traces` table. Visible in transparency mode with "REASONING ON" toggle.

---

## Data Models — Pydantic

All inter-agent data uses Pydantic BaseModel for type safety. Defined in `agents/models.py`.

Key models:

| Model | Used by | Purpose |
|-------|---------|---------|
| PipelineState | Hot path | Flows through all agents |
| QueryClassification | Agent 1 | Query type + domain check |
| RetrievalResult | Agent 1→2 | Single retrieved chunk |
| Agent2Result | Agent 2→3/7 | 5 check results + confidence |
| DiagnosisResult | Agent 3→4A | Root cause + failure class |
| FormulationResult | Agent 4A→1 | Sub-queries + live fetch |
| CycleResult | Repair→7 | Final merged chunks |
| GeneratedResponse | Agent 7→API | Answer + citations + provenance |
| ThoughtTrace | All agents | OBS/THK/ACT/OUT record |

---

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | /chat | Main chat endpoint |
| POST | /chat/feedback | Thumbs up/down |
| GET | /chat/stream | SSE live agent feed |
| GET | /health | System health check |
| GET | /admin/stats | Corpus + learning data |
| GET | /admin/corpus-health | Collection sizes |
| GET | /admin/pending-approvals | Repair queue |
| POST | /admin/approve-repair/{id} | Approve or reject |
| GET | /admin/benchmark-trend | Weekly scores |
| GET | /admin/latest-benchmark | Most recent run |
| GET | /admin/strategy-recommendations | Parameter suggestions |

---

## Scheduled Jobs

| Job | Schedule | Purpose |
|-----|---------|---------|
| Weekly benchmark | Sunday 2am | Track improvement over time |
| Daily Agent 6 insights | Daily 6am | Generate recommendations |
| Freshness sweep | Every 3 days | Flag stale clusters |
| Daily paper monitor | Daily 4am | Check for new relevant papers |
| Gap-targeted sweep | Sunday 3am | Find papers for known gaps |

# Self-Learning and Self-Healing RAG — Architecture

Technical reference for engineers who want to understand exactly how the system works.

---

## System Overview

Two parallel loops run at all times:

**Hot path** — synchronous, handles your query in real time (target: under 15 seconds)

**Cold path** — asynchronous Celery workers, keeps the corpus healthy in the background

```mermaid
flowchart LR
    subgraph HOT ["⚡ Synchronous Hot Path (Real-time Query Resolution)"]
        H1["Agent 1 (Retrieval)\nVector & BM25 Search"] --> H2["Agent 2 (Quality Gate)\n5-Step Evidence Verification"]
        H2 -->|"Passes Verification"| H7["Agent 7 (Generator)\nFormats Prose/Table/List"]
        H2 -->|"Fails Verification"| H3["Agent 3 (Diagnosis)\nRoot Cause Analysis"]
        H3 --> H4A["Agent 4A (Formulator)\nQuery Expansion & Live Fetch"]
        H4A -->|"Retries Search"| H1
    end

    subgraph COLD ["🌙 Asynchronous Cold Path (Background Maintenance)"]
        C4B["Agent 4B (Repair)\nFixes structural corpus issues"]
        C5A["Agent 5A (Verification)\nValidates PubMed papers"]
        C5B["Agent 5B (Ingestion)\nChunks & embeds papers"]
        C6["Agent 6 (Learning)\nAnalyzes telemetry & patterns"]
    end

    H2 -.->|"Triggers Class A/B Repair"| C4B
    H7 -.->|"Logs Query Telemetry"| C6
    C6 -.->|"Updates Topic Calibration"| H2
    C6 -.->|"Adjusts Cache Expiry (TTL)"| CACHE[("Redis Semantic Cache")]
    CACHE -.->|"Bypasses Retrieval on Hit"| H2
```

---

## Query Classification and Domain Check

The first thing that happens when you ask a question. One Gemini call does both jobs simultaneously.

```mermaid
flowchart TD
    Q["User Query\n(Raw Input)"] --> GEMINI["Gemini Flash\nSingle Zero-Shot API call"]

    GEMINI --> DOM{"Domain Check:\nIs it biomedical?"}
    DOM -->|"No"| REJ["Rejection Handler\nReturns 'domain_rejected=True'\nSuggests sample medical queries"]
    DOM -->|"Yes"| TYPE{"Query Type Classification"}

    TYPE -->|"simple_factual"| T1["Factual Retrieval\nSingle concept lookup"]
    TYPE -->|"multi_hop"| T2["Multi-Hop Retrieval\nConnects multiple concepts"]
    TYPE -->|"comparative"| T3["Comparative Retrieval\nOptimized for side-by-side Table output"]
    TYPE -->|"temporal"| T4["Temporal Retrieval\nApplies tighter freshness metadata filter"]
    TYPE -->|"exploratory"| T5["Exploratory Retrieval\nBroadest search parameters"]
```

---

## Agent 1 — Retrieval

```mermaid
flowchart TD
    CLASS["Query Classification"] --> FILTER

    FILTER["Metadata Pre-Filter\nApplied BEFORE vector search for exact match"]

    FILTER -->|"temporal query"| TF["Year >= 2022\nFreshness > 0.5\nTopic Cluster Match"]
    FILTER -->|"simple factual"| SF["Topic Cluster Match\nNo date restriction"]
    FILTER -->|"exploratory"| EF["Minimal filter\nBroad search"]

    TF & SF & EF --> SEARCH

    subgraph SEARCH ["Hybrid Search Execution"]
        DENSE["Dense Vector Search\nS-PubMedBert 768d\n(Semantic Meaning)"]
        SPARSE["Sparse BM25 Search\n(Exact Keyword Match)"]
        DENSE & SPARSE --> RRF["RRF Fusion\nCombines rank scores"]
        RRF --> MMR["MMR Reranking\nMaximizes diversity & relevance\nLambda = 0.7"]
    end

    MMR --> GE["Graph Expansion\nFetches Neo4j citation neighbors\nApplies 0.85x score penalty"]
    GE --> SAFE["Safeguard Check\nFewer than 3 chunks found?\nAuto-relax filters and retry"]
    SAFE --> OUT["Top 5 Chunks\nPassed to Agent 2"]
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
    FAIL["Agent 2 Blocking Failure"] --> T1

    T1["Test 1: Existence\nDoes information exist in corpus at all?\nTests 8 query variations"] -->|"Not found"| CA["Class B Error\n(Knowledge Gap)"]
    T1 -->|"Found"| T2

    T2["Test 2: Chunking\nIs info split across chunk boundaries?"] -->|"Split"| CB["Class A Error\n(Data Chunking Problem)"]
    T2 -->|"Not split"| T3

    T3["Test 3: Embedding\nIs there a big gap between BM25 and Vector scores?"] -->|"Big gap"| CC["Class A Error\n(Embedding Mismatch)"]
    T3 -->|"No gap"| T4

    T4["Test 4: Query\nWas the search strategy wrong for this query?"] -->|"Wrong strategy"| CD["Class C Error\n(Query Strategy Problem)"]
    T4 -->|"Strategy OK"| T5

    T5["Test 5: Filter\nDid metadata filters accidentally remove good chunks?"] -->|"Over-filtered"| CE["Class C Error\n(Filter Problem)"]

    CA & CB & CC --> ROUTE4B["Route to Agent 4B\n(Background Corpus Repair)\nExit hot path immediately"]
    CD & CE --> ROUTE4A["Route to Agent 4A\n(Repair this query right now)"]
```

---

## Agent 4A — Formulator

Handles Class C failures (query problems). Gets another chance to find the right evidence.

```mermaid
flowchart LR
    IN["Class C Diagnosis\n+ Original Chunks"] --> GAP

    GAP["Gap Analysis\nIdentify exactly what query aspects\nwere missing from retrieved chunks"]

    GAP --> FORM["Sub-Query Formulation\nGenerate one highly targeted query\nper missing aspect"]

    FORM --> FETCH{"Diagnosis:\nIs Knowledge Drift detected?"}
    FETCH -->|"Yes"| LIVE["Live PubMed API Fetch\nGet papers from last 30 days\nQueue for permanent ingestion"]
    FETCH -->|"No"| NORMAL["Standard Re-retrieval\nQuery corpus with better strategy"]

    LIVE & NORMAL --> MERGE["Merge & Deduplicate\nCombine new chunks with original chunks"]
    MERGE --> OUT["Back to Agent 2\n(Re-evaluation)"]
```

---

## Agent 6 — Learning Architecture

```mermaid
flowchart TD
    subgraph IN ["Data Streams (Every query feeds Agent 6)"]
        I1["Query Result (Pass/Fail)"]
        I2["User Feedback (👍/👎)"]
        I3["Weekly Benchmark Iteration"]
    end

    IN --> OBS["Record to Supabase PostgreSQL"]

    OBS --> P1["Pattern Detection\nSame failure type >5 times = Pattern\n>20 times = High Severity"]
    OBS --> P2["Calibration Tracking\nExpressed Confidence vs Actual Pass Rate"]
    OBS --> P3["Gap Mapping\nIdentify topics asked but not answered"]
    OBS --> P4["Topic Velocity\nCalculate how fast topics evolve"]

    P1 --> D1["Admin Dashboard\nActionable Insights Panel"]
    P2 --> D2["Agent 2 Dynamically Reads Calibration\nProvides honest Wilson Score intervals"]
    P3 --> D3["Agent 5A Priority Targeting\nIngest new papers based on real user gaps"]
    P4 --> D4["Cache TTL Tuning\nImmunotherapy = 4hr\nDrug Interactions = 24hr\nGenomics = 7 days"]
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
    Q["Query Type & Keywords"] --> DET

    DET{"Detect Best Output Format"}
    DET -->|"comparative + 2 entities"| TABLE["Table Format\nSide-by-side feature comparison"]
    DET -->|"list / what are / side effects"| LIST["Numbered List\nEach item explicitly cited"]
    DET -->|"summarize / overview / explain"| SUMMARY["Structured Summary\nKey Finding + Evidence + Limitations"]
    DET -->|"everything else"| PROSE["Conversational Prose\nFluent text with inline citations"]
```

**Claim provenance:** After generating, Agent 7 uses Gemini to link every specific fact in the answer back to the exact chunk that supports it. Each claim shows paper ID, year, journal, and a source quote.

---

## Semantic Cache

```mermaid
flowchart LR
    Q["Query Embedding\n768 dimensions"] --> HASH["SimHash Algorithm\n32-bit consistent hash\nseed=42"]
    HASH --> KEY["Redis Key\ncache:{8-char-hex}"]
    KEY --> CHECK{"Cache Hit?"}
    CHECK -->|"Hit"| VERIFY["Agent 2 (Fast Path)\nChecks Freshness & Completeness only"]
    CHECK -->|"Miss"| FULL["Full 9-Agent Pipeline Execution"]
    VERIFY -->|"Pass"| A7["Agent 7\nGenerates fresh text from cached chunks"]
    VERIFY -->|"Fail"| FULL
    FULL --> STORE["Store retrieved chunks in Redis\n(Answers are NEVER cached)"]
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

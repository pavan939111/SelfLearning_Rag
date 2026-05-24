# Self-Learning and Self-Healing RAG — Architecture

Technical reference for engineers who want to understand exactly how the system works.

---

## 1. Holistic System Architecture

This is the complete bird's-eye view of the system, showing how the frontend, backend, 9 autonomous agents, and 4 specialized databases interact.

```mermaid
flowchart TB
    USER(("👤 User")) -->|1. Asks Medical Question| UI["React Frontend\n(Chat UI & Transparency Panel)"]
    
    UI -->|2. POST /chat| API["FastAPI Backend\n(Orchestration Layer)"]
    API -.->|"3. Streams Thought Traces (SSE)"| UI
    
    subgraph HOT ["⚡ Hot Path (Real-Time Retrieval & Generation)"]
        direction TB
        A1["🔍 Agent 1 (Finder)\nHybrid Search + Graph Expansion"] --> A2{"⚖️ Agent 2 (Inspector)\nRelevance & Freshness Gate"}
        A2 -->|"Passes"| A7["✍️ Agent 7 (Writer)\nFormats Output & Citations"]
        A2 -->|"Fails"| A3["🩺 Agent 3 (Detective)\nRoot Cause Diagnosis"]
        A3 --> A4A["🎯 Agent 4A (Formulator)\nQuery Rewrite & Live Fetch"]
        A4A -->|"Retries Search"| A1
    end

    subgraph COLD ["🌙 Cold Path (Asynchronous Maintenance)"]
        direction TB
        A4B["🔧 Agent 4B (Repair)\nFixes structural data issues"]
        A5A["✅ Agent 5A (Verifier)\nValidates PubMed quality"]
        A5B["📥 Agent 5B (Ingester)\nChunks and vectorizes"]
        A6["🧠 Agent 6 (Learning)\nAdjusts system parameters"]
    end

    subgraph DATABASES ["🗄️ Core Data Infrastructure"]
        direction LR
        REDIS[("⚡ Upstash Redis\nSemantic Cache & Celery Task Queues")]
        QDRANT[("🧠 Qdrant Cloud\nVector Embeddings (Hybrid Search)")]
        NEO4J[("🕸️ Neo4j AuraDB\nCitation Knowledge Graph")]
        SUPA[("📊 Supabase PostgreSQL\nSQL Telemetry & ReAct Thought Traces")]
    end

    API -->|4. Checks Cache| REDIS
    REDIS -->|"5a. Cache Miss"| HOT
    REDIS -.->|"5b. Cache Hit (Bypasses Agent 1)"| A2
    
    A1 <--> QDRANT
    A1 <--> NEO4J
    HOT <--> SUPA
    
    A3 -.->|"Triggers Background Repair"| REDIS
    REDIS -.->|"Dispatches Task"| COLD
    COLD <--> QDRANT
    COLD <--> SUPA
    
    A7 -->|6. Final Answer| API
```

---

## 2. Frontend to Backend Data Flow (Sequence Diagram)

This diagram illustrates how the system streams ReAct thought traces to the UI in real-time before generating the final answer.

```mermaid
sequenceDiagram
    actor User
    participant React as React Frontend
    participant FastAPI as FastAPI Backend
    participant Agents as 9-Agent Pipeline
    participant Redis as Redis Cache
    participant DB as Qdrant/Supabase

    User->>React: Sends Question (e.g., "How does CRISPR work?")
    React->>FastAPI: POST /chat {query}
    FastAPI->>Redis: Check SimHash Semantic Cache
    
    alt Cache Hit
        Redis-->>FastAPI: Returns Cached Evidence Chunks
        FastAPI->>Agents: Trigger Fast-Path (Agent 2 & Agent 7)
    else Cache Miss
        FastAPI->>Agents: Trigger Full 9-Agent Hot Path Pipeline
    end
    
    par Real-time Thought Stream
        Agents-->>React: SSE (Server-Sent Events) Stream
        React-->>User: Displays OBS/THK/ACT/OUT Live Agent Traces
    and Answer Generation
        Agents->>DB: Fetch/Store Data
        DB-->>Agents: Return Evidence
        Agents-->>FastAPI: Final Answer Generated
        FastAPI-->>React: Complete JSON Response
        React-->>User: Renders Formatted Answer + Citations
    end
```

---

## 3. Query Classification and Domain Check

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

## 4. Agent 1 — Hybrid Retrieval Mechanics (RRF + MMR)

Agent 1 uses a sophisticated hybrid search to guarantee high-quality retrieval.

```mermaid
flowchart TD
    Q["User Query\n(Text)"] --> EM["S-PubMedBert-MS-MARCO\nGenerates 768d Vector"]
    
    subgraph HYBRID ["Hybrid Search Engine (Qdrant Cloud)"]
        EM --> DENSE["Dense Vector Search\nFinds contextual semantic meaning\n(e.g., matching 'cancer' to 'oncology')"]
        Q --> SPARSE["Sparse BM25 Search\nFinds exact keyword matches\n(e.g., specific drug names)"]
        
        DENSE --> RRF["Reciprocal Rank Fusion (RRF)\nMerges and re-ranks both lists based on rank position\nscore = 1 / (k + rank)"]
        SPARSE --> RRF
    end

    RRF --> MMR["Maximal Marginal Relevance (MMR)\nLambda = 0.7\nFilters out redundant chunks to maximize diversity"]
    
    MMR --> OUT["Top 5 High-Diversity,\nHigh-Relevance Chunks passed to Agent 2"]
```

---

## 5. Neo4j Knowledge Graph Expansion

During retrieval, Agent 1 utilizes Neo4j to find hidden connections via citation networks.

```mermaid
flowchart TD
    START["Agent 1 Retrieves Top Chunks"] --> CHUNK["Target Chunk\n(Belongs to Paper A)"]
    
    CHUNK --> N4J{"Query Neo4j Graph\nFind 1-hop citations"}
    
    subgraph GRAPH ["Knowledge Graph Expansion"]
        N4J -->|"Cites"| REF["Reference Paper\n(Older foundational work)"]
        N4J -->|"Cited By"| CIT["Citing Paper\n(Newer follow-up work)"]
        N4J -->|"Contradicts"| CON["Contradicting Paper\n(Opposing findings)"]
    end
    
    REF --> EXTRACT["Extract chunks from neighboring papers"]
    CIT --> EXTRACT
    CON --> EXTRACT
    
    EXTRACT --> PENALTY["Apply 0.85x Score Penalty\n(Prioritizes direct matches, but surfaces hidden links)"]
    PENALTY --> MERGE["Merge into final retrieval set"]
```

---

## 6. Agent 2 — Quality Gate

The most important agent. Nothing reaches Agent 7 without passing here.

| Check | Method | Blocking? | On fail |
|-------|--------|-----------|---------|
| Relevance | Gemini Flash scores each chunk | Yes | Enter repair cycle |
| Completeness | Gemini Flash checks full coverage | Yes | Enter repair cycle |
| Freshness | Metadata analysis, no LLM | No | Set live_fetch flag |
| Calibration | Read Agent 6 curves from Supabase | No | Adjust confidence |
| Contradiction | Gemini Flash compares chunks | No | Flag for Agent 7 |

---

## 7. Agent 3 — Root Cause Classifier

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

## 8. Celery Worker Queue Architecture (The Cold Path)

How background tasks are handled using Redis and Celery without blocking the user.

```mermaid
flowchart LR
    subgraph PRODUCERS ["Task Producers (FastAPI Hot Path)"]
        A3["Agent 3 (Diagnosis)\nFinds Class A/B Error"] -->|Queue Task| R[("Upstash Redis\nMessage Broker")]
        A4A["Agent 4A (Formulator)\nFetches Live PubMed"] -->|Queue Task| R
        A6["Agent 6 (Learning)\nDetects Knowledge Gap"] -->|Queue Task| R
    end

    subgraph REDIS ["Redis Queues"]
        R --> Q1["Queue: 'repair_tasks'"]
        R --> Q2["Queue: 'ingestion_tasks'"]
        R --> Q3["Queue: 'learning_tasks'"]
    end

    subgraph CONSUMERS ["Celery Worker Nodes (Cold Path)"]
        Q1 --> W1["Worker 1 (Agent 4B)\nExecutes Deep Corpus Repair"]
        Q2 --> W2["Worker 2 (Agent 5B)\nEmbeds & Indexes New Papers"]
        Q3 --> W3["Worker 3 (Agent 6)\nRuns Weekly Benchmarks"]
    end
    
    W1 -.-> DB[("Supabase / Qdrant\nCloud Databases")]
    W2 -.-> DB
    W3 -.-> DB
```

---

## 9. Agent 4A — Formulator

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

## 10. Agent 6 — Learning Architecture

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

## 11. Agent 7 — Generator

Produces the final answer. Receives everything the pipeline discovered.

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

---

## 12. Semantic Cache

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

---

## Data Models — Pydantic

All inter-agent data uses Pydantic BaseModel for type safety. Defined in `agents/models.py`.

---

## Scheduled Jobs

| Job | Schedule | Purpose |
|-----|---------|---------|
| Weekly benchmark | Sunday 2am | Track improvement over time |
| Daily Agent 6 insights | Daily 6am | Generate recommendations |
| Freshness sweep | Every 3 days | Flag stale clusters |
| Daily paper monitor | Daily 4am | Check for new relevant papers |
| Gap-targeted sweep | Sunday 3am | Find papers for known gaps |

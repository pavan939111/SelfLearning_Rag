# Self-Learning and Self-Healing RAG — Architecture

Technical reference for engineers who want to understand exactly how the system works.

---

## 1. Holistic System Architecture

This is the complete bird's-eye view of the system, showing how the frontend, backend, 9 autonomous agents, and 4 specialized databases interact.

```mermaid
flowchart TD
    classDef user fill:#f3e5f5,stroke:#ab47bc,stroke-width:2px,color:#000,rx:10px
    classDef frontend fill:#e3f2fd,stroke:#42a5f5,stroke-width:2px,color:#000,rx:10px
    classDef gateway fill:#fff3e0,stroke:#ffa726,stroke-width:2px,color:#000
    classDef hotpath fill:#e8f5e9,stroke:#66bb6a,stroke-width:2px,color:#000,rx:5px
    classDef coldpath fill:#ede7f6,stroke:#7e57c2,stroke-width:2px,color:#000,rx:5px
    classDef database fill:#eceff1,stroke:#78909c,stroke-width:2px,color:#000,rx:10px
    classDef rejection fill:#ffebee,stroke:#ef5350,stroke-width:2px,color:#000

    USER(("👤 User")):::user -->|"Asks Medical Question"| UI["💻 React Frontend\n(Chat UI & Traces)"]:::frontend
    
    UI -->|"POST /chat"| API["🚦 API Gateway (FastAPI)"]:::gateway
    API -.->|"SSE Live Thought Traces"| UI
    
    API --> CLASS{"🧠 Query Classifier\n(Domain Check)"}:::gateway
    CLASS -->|"Out of Scope"| REJ["❌ Early Rejection"]:::rejection
    REJ -.->|"Alert Message"| UI
    
    CLASS -->|"Valid Query"| CACHE{"⚡ Semantic Cache\n(Redis)"}:::database
    
    subgraph HOT ["⚡ Hot Path (Real-Time Synchronous Pipeline)"]
        direction TB
        A1["🔍 Agent 1 (Finder)\n• Parses Query Intent\n• Executes BM25 Sparse Search\n• Executes S-PubMedBert Dense Search\n• Expands via Neo4j Citation Graph\n• RRF/MMR Merging"]:::hotpath
        
        A2{"⚖️ Agent 2 (Inspector)\n• Evaluates Relevance (LLM)\n• Evaluates Completeness (LLM)\n• Checks Freshness Metadata\n• Calculates Calibration Score\n• Detects Contradictions"}:::hotpath
        
        A7["✍️ Agent 7 (Writer)\n• Triggers on A2 Approval\n• Selects Output Format (Table/List/Prose)\n• Generates Final Answer\n• Embeds Specific Inline Citations"]:::hotpath
        
        A3["🩺 Agent 3 (Detective)\n• Triggers on A2 Rejection\n• Checks Corpus for Knowledge Gap (Class B)\n• Checks for Chunking/Embedding Mismatches (Class A)\n• Checks for Search Strategy Failures (Class C)"]:::hotpath
        
        A4A["🎯 Agent 4A (Formulator)\n• Triggers on Class C Error\n• Generates Sub-Queries for Missing Gaps\n• Triggers Live PubMed API Fetch if Stale\n• Re-queries Corpus & Merges Results"]:::hotpath
        
        A1 --> A2
        A2 -->|"Passes"| A7
        A2 -->|"Fails"| A3
        A3 -->|"Class C Error"| A4A
        A4A -->|"Retries Search"| A1
    end

    CACHE -->|"Cache Miss"| A1
    CACHE -.->|"Cache Hit\n(Bypasses Agent 1)"| A2
    
    subgraph COLD ["🌙 Cold Path (Asynchronous Background Maintenance)"]
        direction TB
        A4B["🔧 Agent 4B (Corpus Repair)\n• Triggers on Class A/B Error\n• Asynchronous Background Worker\n• Resolves Deep Structural Knowledge Gaps"]:::coldpath
        
        A5A["✅ Agent 5A (PubMed Verifier)\n• Scans External Literature\n• Validates Biomedical Domain\n• Checks Peer-Review / RCT Status\n• Filters by High Citation Velocity"]:::coldpath
        
        A5B["📥 Agent 5B (Data Ingester)\n• Runs on A5A Approval\n• Splits Papers (Doc->Sec->Chunk->Claim)\n• Generates S-PubMedBert Vectors\n• Promotes to Production Qdrant Database"]:::coldpath
        
        A6["🧠 Agent 6 (Learning Engine)\n• Analyzes Pass/Fail & User Telemetry\n• Identifies Frequent Missing Topics\n• Tunes Agent 2 Confidence Calibration\n• Adjusts Redis Cache TTL dynamically"]:::coldpath
    end

    A3 -.->|"Schedules Repair (Class A/B)"| A4B
    A7 -->|"Final Verified Answer"| UI
    A7 -.->|"Logs Query Telemetry"| A6
    A6 -.->|"Updates Calibration"| A2
    
    subgraph DB ["🗄️ Core Data Infrastructure"]
        direction LR
        REDIS[("⚡ Upstash Redis\n(Cache & Celery Queues)")]:::database
        QDRANT[("🧠 Qdrant Cloud\n(Vector Embeddings)")]:::database
        NEO4J[("🕸️ Neo4j AuraDB\n(Citation Knowledge Graph)")]:::database
        SUPA[("📊 Supabase PostgreSQL\n(SQL Telemetry & Thought Traces)")]:::database
    end
    
    HOT <-->|"Reads/Writes"| DB
    COLD <-->|"Reads/Writes"| DB
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
    classDef input fill:#e3f2fd,stroke:#42a5f5,stroke-width:2px,color:#000,rx:5px
    classDef process fill:#f3e5f5,stroke:#ab47bc,stroke-width:2px,color:#000,rx:5px
    classDef fail fill:#ffebee,stroke:#ef5350,stroke-width:2px,color:#000,rx:5px
    classDef route fill:#e8f5e9,stroke:#66bb6a,stroke-width:2px,color:#000,rx:5px

    Q["User Query\n(Raw Input)"]:::input --> GEMINI["Gemini Flash\nSingle Zero-Shot API call"]:::process

    GEMINI --> DOM{"Domain Check:\nIs it biomedical?"}:::process
    DOM -->|"No"| REJ["Rejection Handler\nReturns 'domain_rejected=True'\nSuggests sample medical queries"]:::fail
    DOM -->|"Yes"| TYPE{"Query Type Classification"}:::process

    TYPE -->|"simple_factual"| T1["Factual Retrieval\nSingle concept lookup"]:::route
    TYPE -->|"multi_hop"| T2["Multi-Hop Retrieval\nConnects multiple concepts"]:::route
    TYPE -->|"comparative"| T3["Comparative Retrieval\nOptimized for side-by-side Table output"]:::route
    TYPE -->|"temporal"| T4["Temporal Retrieval\nApplies tighter freshness metadata filter"]:::route
    TYPE -->|"exploratory"| T5["Exploratory Retrieval\nBroadest search parameters"]:::route
```

---

## 4. Agent 1 — Hybrid Retrieval Mechanics (RRF + MMR)

Agent 1 uses a sophisticated hybrid search to guarantee high-quality retrieval.

```mermaid
flowchart TD
    classDef query fill:#e3f2fd,stroke:#42a5f5,stroke-width:2px,color:#000,rx:5px
    classDef db fill:#eceff1,stroke:#78909c,stroke-width:2px,color:#000,rx:10px
    classDef process fill:#f3e5f5,stroke:#ab47bc,stroke-width:2px,color:#000,rx:5px
    classDef result fill:#e8f5e9,stroke:#66bb6a,stroke-width:2px,color:#000,rx:5px

    Q["👤 User Query"]:::query --> PARSE["⚙️ Agent 1: Query Parsing"]:::process

    subgraph SEARCH ["Hybrid Search Execution"]
        direction LR
        PARSE --> DENSE["🧠 Dense Search\n(S-PubMedBert)"]:::process
        PARSE --> SPARSE["📝 Sparse Search\n(BM25)"]:::process
        
        DENSE --> QDRANT[("🗄️ Qdrant Cloud")]:::db
        SPARSE --> QDRANT
    end

    subgraph FUSION ["Ranking & Expansion"]
        direction TB
        QDRANT --> RRF["🧮 Reciprocal Rank Fusion\n(Merges Dense & Sparse)"]:::process
        RRF --> NEO4J[("🕸️ Neo4j AuraDB\nCitation Graph")]:::db
        NEO4J -->|"Applies +20% score to highly cited\nApplies -15% to contradicted"| MMR["🎯 MMR Re-ranking\n(Removes duplicates)"]:::process
    end

    MMR --> OUT["✅ Top 5 Verified Chunks\n(Passed to Agent 2)"]:::result
```

---

## 5. Neo4j Knowledge Graph Expansion

During retrieval, Agent 1 utilizes Neo4j to find hidden connections via citation networks.

```mermaid
flowchart TD
    classDef start fill:#e3f2fd,stroke:#42a5f5,stroke-width:2px,color:#000,rx:5px
    classDef kg fill:#eceff1,stroke:#78909c,stroke-width:2px,color:#000,rx:5px
    classDef process fill:#fff3e0,stroke:#ffa726,stroke-width:2px,color:#000,rx:5px
    classDef result fill:#e8f5e9,stroke:#66bb6a,stroke-width:2px,color:#000,rx:5px

    START["Agent 1 Retrieves Top Chunks"]:::start --> CHUNK["Target Chunk\n(Belongs to Paper A)"]:::start
    
    CHUNK --> N4J{"Query Neo4j Graph\nFind 1-hop citations"}:::process
    
    subgraph GRAPH ["Knowledge Graph Expansion"]
        N4J -->|"Cites"| REF["Reference Paper\n(Older foundational work)"]:::kg
        N4J -->|"Cited By"| CIT["Citing Paper\n(Newer follow-up work)"]:::kg
        N4J -->|"Contradicts"| CON["Contradicting Paper\n(Opposing findings)"]:::kg
    end
    
    REF --> EXTRACT["Extract chunks from neighboring papers"]:::process
    CIT --> EXTRACT
    CON --> EXTRACT
    
    EXTRACT --> PENALTY["Apply 0.85x Score Penalty\n(Prioritizes direct matches, but surfaces hidden links)"]:::process
    PENALTY --> MERGE["Merge into final retrieval set"]:::result
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
    classDef fail fill:#ffebee,stroke:#ef5350,stroke-width:2px,color:#000,rx:5px
    classDef test fill:#fff3e0,stroke:#ffa726,stroke-width:2px,color:#000,rx:5px
    classDef coldpath fill:#ede7f6,stroke:#7e57c2,stroke-width:2px,color:#000,rx:5px
    classDef hotpath fill:#e8f5e9,stroke:#66bb6a,stroke-width:2px,color:#000,rx:5px

    FAIL["Agent 2 Blocking Failure"]:::fail --> T1

    T1["Test 1: Existence\nDoes information exist in corpus at all?\nTests 8 query variations"]:::test -->|"Not found"| CA["Class B Error\n(Knowledge Gap)"]:::fail
    T1 -->|"Found"| T2

    T2["Test 2: Chunking\nIs info split across chunk boundaries?"]:::test -->|"Split"| CB["Class A Error\n(Data Chunking Problem)"]:::fail
    T2 -->|"Not split"| T3

    T3["Test 3: Embedding\nIs there a big gap between BM25 and Vector scores?"]:::test -->|"Big gap"| CC["Class A Error\n(Embedding Mismatch)"]:::fail
    T3 -->|"No gap"| T4

    T4["Test 4: Query\nWas the search strategy wrong for this query?"]:::test -->|"Wrong strategy"| CD["Class C Error\n(Query Strategy Problem)"]:::fail
    T4 -->|"Strategy OK"| T5

    T5["Test 5: Filter\nDid metadata filters accidentally remove good chunks?"]:::test -->|"Over-filtered"| CE["Class C Error\n(Filter Problem)"]:::fail

    CA & CB & CC --> ROUTE4B["Route to Agent 4B\n(Background Corpus Repair)\nExit hot path immediately"]:::coldpath
    CD & CE --> ROUTE4A["Route to Agent 4A\n(Repair this query right now)"]:::hotpath
```

---

## 8. Celery Worker Queue Architecture (The Cold Path)

How background tasks are handled using Redis and Celery without blocking the user.

```mermaid
flowchart LR
    classDef producer fill:#fff3e0,stroke:#ffa726,stroke-width:2px,color:#000,rx:5px
    classDef queue fill:#e3f2fd,stroke:#42a5f5,stroke-width:2px,color:#000,rx:5px
    classDef worker fill:#ede7f6,stroke:#7e57c2,stroke-width:2px,color:#000,rx:5px
    classDef db fill:#eceff1,stroke:#78909c,stroke-width:2px,color:#000,rx:10px

    subgraph PRODUCERS ["Task Producers (FastAPI Hot Path)"]
        direction TB
        A3["Agent 3 (Diagnosis)\nFinds Class A/B Error"]:::producer -->|Queue Task| R[("Upstash Redis\nMessage Broker")]:::db
        A4A["Agent 4A (Formulator)\nFetches Live PubMed"]:::producer -->|Queue Task| R
        A6["Agent 6 (Learning)\nDetects Knowledge Gap"]:::producer -->|Queue Task| R
    end

    subgraph REDIS ["Redis Queues"]
        direction TB
        R --> Q1["Queue: 'repair_tasks'"]:::queue
        R --> Q2["Queue: 'ingestion_tasks'"]:::queue
        R --> Q3["Queue: 'learning_tasks'"]:::queue
    end

    subgraph CONSUMERS ["Celery Worker Nodes (Cold Path)"]
        direction TB
        Q1 --> W1["Worker 1 (Agent 4B)\nExecutes Deep Corpus Repair"]:::worker
        Q2 --> W2["Worker 2 (Agent 5B)\nEmbeds & Indexes New Papers"]:::worker
        Q3 --> W3["Worker 3 (Agent 6)\nRuns Weekly Benchmarks"]:::worker
    end
    
    W1 -.-> DB[("Supabase / Qdrant\nCloud Databases")]:::db
    W2 -.-> DB
    W3 -.-> DB
```

---

## 9. Agent 4A — Formulator

Handles Class C failures (query problems). Gets another chance to find the right evidence.

```mermaid
flowchart LR
    classDef input fill:#ffebee,stroke:#ef5350,stroke-width:2px,color:#000,rx:5px
    classDef process fill:#fff3e0,stroke:#ffa726,stroke-width:2px,color:#000,rx:5px
    classDef success fill:#e8f5e9,stroke:#66bb6a,stroke-width:2px,color:#000,rx:5px

    IN["Class C Diagnosis\n+ Original Chunks"]:::input --> GAP

    GAP["Gap Analysis\nIdentify exactly what query aspects\nwere missing from retrieved chunks"]:::process

    GAP --> FORM["Sub-Query Formulation\nGenerate one highly targeted query\nper missing aspect"]:::process

    FORM --> FETCH{"Diagnosis:\nIs Knowledge Drift detected?"}:::process
    FETCH -->|"Yes"| LIVE["Live PubMed API Fetch\nGet papers from last 30 days\nQueue for permanent ingestion"]:::process
    FETCH -->|"No"| NORMAL["Standard Re-retrieval\nQuery corpus with better strategy"]:::process

    LIVE & NORMAL --> MERGE["Merge & Deduplicate\nCombine new chunks with original chunks"]:::process
    MERGE --> OUT["Back to Agent 2\n(Re-evaluation)"]:::success
```

---

## 10. Agent 6 — Learning Architecture

```mermaid
flowchart TD
    classDef stream fill:#e3f2fd,stroke:#42a5f5,stroke-width:2px,color:#000,rx:5px
    classDef process fill:#ede7f6,stroke:#7e57c2,stroke-width:2px,color:#000,rx:5px
    classDef result fill:#e8f5e9,stroke:#66bb6a,stroke-width:2px,color:#000,rx:5px

    subgraph IN ["Data Streams (Every query feeds Agent 6)"]
        direction LR
        I1["Query Result (Pass/Fail)"]:::stream
        I2["User Feedback (👍/👎)"]:::stream
        I3["Weekly Benchmark Iteration"]:::stream
    end

    IN --> OBS["Record to Supabase PostgreSQL"]:::process

    OBS --> P1["Pattern Detection\nSame failure type >5 times = Pattern\n>20 times = High Severity"]:::process
    OBS --> P2["Calibration Tracking\nExpressed Confidence vs Actual Pass Rate"]:::process
    OBS --> P3["Gap Mapping\nIdentify topics asked but not answered"]:::process
    OBS --> P4["Topic Velocity\nCalculate how fast topics evolve"]:::process

    P1 --> D1["Admin Dashboard\nActionable Insights Panel"]:::result
    P2 --> D2["Agent 2 Dynamically Reads Calibration\nProvides honest Wilson Score intervals"]:::result
    P3 --> D3["Agent 5A Priority Targeting\nIngest new papers based on real user gaps"]:::result
    P4 --> D4["Cache TTL Tuning\nImmunotherapy = 4hr\nDrug Interactions = 24hr\nGenomics = 7 days"]:::result
```

---

## 11. Agent 7 — Generator

Produces the final answer. Receives everything the pipeline discovered.

```mermaid
flowchart LR
    classDef input fill:#e3f2fd,stroke:#42a5f5,stroke-width:2px,color:#000,rx:5px
    classDef process fill:#fff3e0,stroke:#ffa726,stroke-width:2px,color:#000,rx:5px
    classDef result fill:#e8f5e9,stroke:#66bb6a,stroke-width:2px,color:#000,rx:5px

    Q["Query Type & Keywords"]:::input --> DET

    DET{"Detect Best Output Format"}:::process
    DET -->|"comparative + 2 entities"| TABLE["Table Format\nSide-by-side feature comparison"]:::result
    DET -->|"list / what are / side effects"| LIST["Numbered List\nEach item explicitly cited"]:::result
    DET -->|"summarize / overview / explain"| SUMMARY["Structured Summary\nKey Finding + Evidence + Limitations"]:::result
    DET -->|"everything else"| PROSE["Conversational Prose\nFluent text with inline citations"]:::result
```

---

## 12. Semantic Cache

```mermaid
flowchart LR
    classDef input fill:#e3f2fd,stroke:#42a5f5,stroke-width:2px,color:#000,rx:5px
    classDef process fill:#fff3e0,stroke:#ffa726,stroke-width:2px,color:#000,rx:5px
    classDef db fill:#eceff1,stroke:#78909c,stroke-width:2px,color:#000,rx:10px
    classDef success fill:#e8f5e9,stroke:#66bb6a,stroke-width:2px,color:#000,rx:5px

    Q["Query Embedding\n768 dimensions"]:::input --> HASH["SimHash Algorithm\n32-bit consistent hash\nseed=42"]:::process
    HASH --> KEY["Redis Key\ncache:{8-char-hex}"]:::db
    KEY --> CHECK{"Cache Hit?"}:::process
    
    CHECK -->|"Hit"| VERIFY["Agent 2 (Fast Path)\nChecks Freshness & Completeness only"]:::success
    CHECK -->|"Miss"| FULL["Full 9-Agent Pipeline Execution"]:::process
    
    VERIFY -->|"Pass"| A7["Agent 7\nGenerates fresh text from cached chunks"]:::success
    VERIFY -->|"Fail"| FULL
    
    FULL --> STORE["Store retrieved chunks in Redis\n(Answers are NEVER cached)"]:::db
```

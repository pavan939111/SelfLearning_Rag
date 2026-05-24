# Self-Learning and Self-Healing RAG — Architecture

---

## Design Philosophy

**1. Pre-generation not post-generation evaluation**
Most RAG systems generate an answer first, and then ask a secondary LLM "does this answer look right?" Self-Learning and Self-Healing RAG evaluates the *raw evidence* before a single word of the final answer is generated. If the evidence is bad, it never reaches the generator, preventing hallucination at the source.

**2. Merge not replace in repair**
When Agent 1 fails to find enough data, Agent 4A reformulates the query and searches again. Instead of throwing away the first attempt, it merges the new findings with the original findings and deduplicates them. This ensures the system only gains knowledge during a repair cycle, never losing partial matches.

**3. Cache chunks not answers**
Caching generated text is dangerous in medical RAG because answers lose context and cannot be re-verified. Self-Learning and Self-Healing RAG caches the underlying semantic chunks instead. This allows Agent 2 to still perform freshness checks on cached data, ensuring the system remains lightning fast without sacrificing accuracy.

---

## Two Parallel Loops

```mermaid
flowchart TD
    classDef hotpath fill:#e0f7fa,stroke:#00bcd4,stroke-width:2px,color:#000,rx:5px
    classDef coldpath fill:#f3e5f5,stroke:#ab47bc,stroke-width:2px,color:#000,rx:5px
    classDef db fill:#eceff1,stroke:#78909c,stroke-width:2px,color:#000,rx:10px

    subgraph HOT ["⚡ The Hot Path (Synchronous Real-Time Loop)"]
        direction LR
        A1["Agent 1\n(Finder)"]:::hotpath --> A2["Agent 2\n(Inspector)"]:::hotpath
        A2 -->|"Fail"| A3["Agent 3\n(Detective)"]:::hotpath
        A3 --> A4A["Agent 4A\n(Formulator)"]:::hotpath
        A4A -->|"Retry"| A1
        A2 -->|"Pass"| A7["Agent 7\n(Generator)"]:::hotpath
    end

    subgraph COLD ["🌙 The Cold Path (Asynchronous Celery Loop)"]
        direction LR
        A4B["Agent 4B\n(Corpus Repair)"]:::coldpath --> A5A["Agent 5A\n(Verifier)"]:::coldpath
        A5A --> A5B["Agent 5B\n(Ingester)"]:::coldpath
        A5B --> A6["Agent 6\n(Learning)"]:::coldpath
    end

    HOT -.->|"Queues Background Tasks"| COLD
    COLD -.->|"Updates Knowledge Base"| DB[("Shared Databases")]:::db
```

---

## The Hot Path

### Query Classification and Domain Check

```mermaid
flowchart TD
    classDef process fill:#e0f7fa,stroke:#00bcd4,stroke-width:2px,color:#000,rx:5px
    classDef fail fill:#ffebee,stroke:#ef5350,stroke-width:2px,color:#000,rx:5px
    classDef route fill:#e8f5e9,stroke:#66bb6a,stroke-width:2px,color:#000,rx:5px

    Q["User Query arrives"] --> GEMINI["Single Gemini Call\nChecks domain AND type"]:::process

    GEMINI --> DOM{"Is it biomedical?"}
    DOM -->|"No"| REJ["Reject & Suggest\n(No database queries made)"]:::fail
    DOM -->|"Yes"| TYPE{"Classify Query Type"}

    TYPE -->|"simple_factual"| T1["Optimizes for strict keyword matches"]:::route
    TYPE -->|"multi_hop"| T2["Optimizes for dense vector context"]:::route
    TYPE -->|"comparative"| T3["Triggers Agent 7 to output a Markdown Table"]:::route
    TYPE -->|"temporal"| T4["Applies strict date filters to metadata"]:::route
    TYPE -->|"exploratory"| T5["Widens BM25 and relaxes MMR diversity"]:::route
```

### The Semantic Cache

```mermaid
flowchart LR
    classDef process fill:#e0f7fa,stroke:#00bcd4,stroke-width:2px,color:#000,rx:5px
    classDef success fill:#e8f5e9,stroke:#66bb6a,stroke-width:2px,color:#000,rx:5px
    classDef db fill:#eceff1,stroke:#78909c,stroke-width:2px,color:#000,rx:10px

    Q["Query Embedding"] --> SIM["SimHash Algorithm\n(Generates 32-bit ID)"]:::process
    SIM --> REDIS[("Redis Cache Lookup")]:::db
    
    REDIS -->|"Cache Miss"| FULL["Execute Full 9-Agent Pipeline"]:::process
    REDIS -->|"Cache Hit"| A2["Agent 2 (Quality Gate)\nOnly checks freshness & completeness"]:::success
    
    A2 -->|"Passes"| A7["Agent 7 generates fresh text"]:::success
    
    FULL -.->|"Saves chunks with dynamic TTL\n(e.g., Cancer=4h, Genetics=7d)"| REDIS
```

### Agent 1 — Retrieval

```mermaid
flowchart TD
    classDef process fill:#e0f7fa,stroke:#00bcd4,stroke-width:2px,color:#000,rx:5px
    classDef db fill:#eceff1,stroke:#78909c,stroke-width:2px,color:#000,rx:10px
    classDef warning fill:#fff3e0,stroke:#ffa726,stroke-width:2px,color:#000,rx:5px

    Q["Classified Query"] --> META["Metadata Pre-Filter\n(Applied BEFORE search to save compute)"]:::process
    
    META --> DENSE["S-PubMedBert Dense Vector Search"]:::process
    META --> SPARSE["BM25 Sparse Keyword Search"]:::process
    
    DENSE --> RRF["Reciprocal Rank Fusion (RRF)"]:::process
    SPARSE --> RRF
    
    RRF --> NEO4J[("Neo4j Knowledge Graph")]:::db
    NEO4J --> EXPAND["Graph Expansion\n(Boost highly cited, penalize contradicted)"]:::process
    
    EXPAND --> MMR["Maximal Marginal Relevance\n(Removes duplicates)"]:::process
    
    MMR --> CHECK{"Count < 3?"}
    CHECK -->|"Yes"| RELAX["Auto-Relax\nDrop filters and retry"]:::warning
    CHECK -->|"No"| OUT["Final Chunks"]:::process
```

### Agent 2 — Quality Gate

| Check | What it tests | Blocking? | On fail |
|---|---|---|---|
| Relevance | Does the chunk directly answer the user's intent? | Yes | Agent 3 Diagnosis |
| Completeness | Do we have the full picture or just partial fragments? | Yes | Agent 3 Diagnosis |
| Freshness | Is the publication date acceptable for this specific topic? | No | Triggers Live Fetch |
| Calibration | Should we trust this score based on historical performance? | No | Lowers confidence |
| Contradiction | Do the retrieved papers disagree with each other? | No | Alerts Agent 7 |

```mermaid
flowchart LR
    classDef process fill:#e0f7fa,stroke:#00bcd4,stroke-width:2px,color:#000,rx:5px
    classDef block fill:#ffebee,stroke:#ef5350,stroke-width:2px,color:#000,rx:5px
    classDef warn fill:#fff3e0,stroke:#ffa726,stroke-width:2px,color:#000,rx:5px
    classDef success fill:#e8f5e9,stroke:#66bb6a,stroke-width:2px,color:#000,rx:5px

    IN["Chunks arriving from A1"] --> R["Relevance"]:::process
    R -->|"Fail"| BLOCK["BLOCK Pipeline\nTrigger Agent 3"]:::block
    R -->|"Pass"| C["Completeness"]:::process
    
    C -->|"Fail"| BLOCK
    C -->|"Pass"| F["Freshness"]:::process
    
    F -->|"Fail"| W1["Warn: Flag for Live Fetch"]:::warn
    F -->|"Pass"| CAL["Calibration"]:::process
    
    CAL -->|"Low"| W2["Warn: Reduce Confidence"]:::warn
    CAL -->|"High"| CON["Contradiction"]:::process
    
    CON -->|"Found"| W3["Warn: Tell Agent 7 to explain conflict"]:::warn
    CON -->|"Clear"| OUT["PASS\nTrigger Agent 7"]:::success
```

### The Repair Cycle

```mermaid
flowchart LR
    classDef process fill:#e0f7fa,stroke:#00bcd4,stroke-width:2px,color:#000,rx:5px
    classDef evaluate fill:#f3e5f5,stroke:#ab47bc,stroke-width:2px,color:#000,rx:5px
    classDef fail fill:#ffebee,stroke:#ef5350,stroke-width:2px,color:#000,rx:5px
    classDef repair fill:#fff3e0,stroke:#ffa726,stroke-width:2px,color:#000,rx:5px
    classDef success fill:#e8f5e9,stroke:#66bb6a,stroke-width:2px,color:#000,rx:5px
    classDef cold fill:#f3e5f5,stroke:#ab47bc,stroke-width:2px,color:#000,rx:5px

    %% Define the cyclical nodes
    RETRIEVE["🔍 1. Execute Search\n(Agent 1)"]:::process
    INSPECT{"⚖️ 2. Inspect Evidence\n(Agent 2)"}:::evaluate
    DIAGNOSE["🩺 3. Diagnose Failure\n(Agent 3)"]:::fail
    FORMULATE["🎯 4. Formulate Fix\n(Agent 4A)"]:::repair
    ANSWER["✅ 5. Generate Answer\n(Agent 7)"]:::success
    EXIT["📤 Queue Agent 4B\n(Exit Hot Path)"]:::cold

    %% Create the cycle
    RETRIEVE -->|"Yields chunks"| INSPECT
    INSPECT -->|"Reject (Poor Quality)"| DIAGNOSE
    DIAGNOSE -->|"Class C\n(Bad Strategy)"| FORMULATE
    FORMULATE -->|"Injects New Query\nMerges Results"| RETRIEVE

    %% Exit the cycle
    INSPECT -->|"Approve (High Quality)"| ANSWER
    DIAGNOSE -->|"Class A/B\n(Knowledge Gap)"| EXIT
```

### Agent 7 — Generator

Agent 7 receives:
- The verified chunks that passed Agent 2
- The exact query
- Any contradiction warnings
- The calibrated confidence score

| Query type | Detected format |
|---|---|
| comparative + 2 entities | Markdown Table (side-by-side comparison) |
| "list" / "side effects" | Numbered List with inline citations |
| "summarize" / "overview" | Structured Summary (Findings, Evidence, Limits) |
| everything else | Conversational Prose with inline citations |

---

## The Cold Path

### Agent 4B — Corpus Repair

```mermaid
flowchart LR
    classDef cold fill:#f3e5f5,stroke:#ab47bc,stroke-width:2px,color:#000,rx:5px
    classDef db fill:#eceff1,stroke:#78909c,stroke-width:2px,color:#000,rx:10px
    classDef fail fill:#ffebee,stroke:#ef5350,stroke-width:2px,color:#000,rx:5px
    classDef success fill:#e8f5e9,stroke:#66bb6a,stroke-width:2px,color:#000,rx:5px

    TRIG["Triggered by Class A/B"] --> FETCH["Fetch raw paper text"]:::cold
    FETCH --> CHUNK["Re-chunk with new parameters"]:::cold
    CHUNK --> EMBED["Re-embed via S-PubMedBert"]:::cold
    EMBED --> STAGE[("Staging Database")]:::db
    
    STAGE --> VAL{"Validation\n(Run 3 Synthetic Queries)"}:::cold
    VAL -->|"Fail"| ROLL["Rollback Changes"]:::fail
    VAL -->|"Pass"| CHECK{"Count > 50 papers?"}
    
    CHECK -->|"Yes"| ADMIN["Require Admin Approval"]:::fail
    CHECK -->|"No"| PROD[("Promote to Production")]:::success
```

### Agent 5A — Verification Gate

```mermaid
flowchart TD
    classDef cold fill:#f3e5f5,stroke:#ab47bc,stroke-width:2px,color:#000,rx:5px
    classDef fail fill:#ffebee,stroke:#ef5350,stroke-width:2px,color:#000,rx:5px
    classDef success fill:#e8f5e9,stroke:#66bb6a,stroke-width:2px,color:#000,rx:5px

    PAPER["New Paper Proposed"] --> D{"1. Biomedical Domain?"}:::cold
    D -->|"No"| REJ["Reject & Discard"]:::fail
    D -->|"Yes"| P{"2. Peer-Reviewed or RCT?"}:::cold
    
    P -->|"No"| REJ
    P -->|"Yes"| V{"3. High Citation Velocity?"}:::cold
    
    V -->|"No"| REJ
    V -->|"Yes"| G{"4. Fills Known Gap?"}:::cold
    
    G -->|"No"| REJ
    G -->|"Yes"| PASS["Approve for Agent 5B"]:::success
```

### Agent 6 — Self-Learning

```mermaid
flowchart TD
    classDef input fill:#e0f7fa,stroke:#00bcd4,stroke-width:2px,color:#000,rx:5px
    classDef engine fill:#f3e5f5,stroke:#ab47bc,stroke-width:2px,color:#000,rx:10px
    classDef output fill:#e8f5e9,stroke:#66bb6a,stroke-width:2px,color:#000,rx:5px

    I1["Query Pass/Fail Results"]:::input --> A6
    I2["User Thumbs Up/Down"]:::input --> A6
    I3["Weekly Benchmark Scores"]:::input --> A6
    
    A6(("Agent 6\nLearning Engine")):::engine
    
    A6 --> O1["Updates Agent 2 Calibration Curve"]:::output
    A6 --> O2["Generates Gap Map for Agent 5A"]:::output
    A6 --> O3["Adjusts Redis TTL by Topic Velocity"]:::output
    A6 --> O4["Recommends Admin Actions"]:::output
    A6 --> O5["Predicts Future Knowledge Drift"]:::output
```

---

## The Self-Healing Loop

```mermaid
sequenceDiagram
    actor User
    participant HotPath as Hot Path
    participant ColdPath as Cold Path
    participant Database as Qdrant DB
    actor NextUser as Next User

    User->>HotPath: Asks about new drug X
    HotPath->>Database: Searches for drug X
    Database-->>HotPath: 0 results
    HotPath-->>User: Answers: "I don't have information on drug X."
    
    HotPath-)ColdPath: Agent 3 logs Class B Error (Knowledge Gap)
    ColdPath->>ColdPath: Agent 4B triggers mass fetch for drug X
    ColdPath->>ColdPath: Agent 5A verifies new papers
    ColdPath->>Database: Agent 5B indexes drug X papers
    
    NextUser->>HotPath: Asks about new drug X
    HotPath->>Database: Searches for drug X
    Database-->>HotPath: Returns 5 high-quality chunks
    HotPath-->>NextUser: Delivers accurate, cited answer on drug X!
```

---

## Data Architecture

### Four Databases

```mermaid
flowchart LR
    classDef db fill:#eceff1,stroke:#78909c,stroke-width:2px,color:#000,rx:10px
    
    REDIS[("⚡ Upstash Redis\n• SimHash Semantic Cache\n• Celery Message Broker\n• Topic Velocity TTLs")]:::db
    QDRANT[("🧠 Qdrant Cloud\n• S-PubMedBert Vectors\n• BM25 Sparse Indices\n• Staging vs Production collections")]:::db
    NEO4J[("🕸️ Neo4j AuraDB\n• Papers (Nodes)\n• Citations (Edges)\n• Contradictions (Edges)")]:::db
    SUPA[("📊 Supabase PostgreSQL\n• ReAct Thought Traces\n• Agent 6 Telemetry\n• System Calibration Curves")]:::db
```

### The Four-Level Chunk Hierarchy

```mermaid
flowchart TD
    classDef level fill:#e0f7fa,stroke:#00bcd4,stroke-width:2px,color:#000,rx:5px
    
    P["Raw Paper\n(1 item)"]:::level --> D["Level 1: Document\nMetadata & Abstract\n(1 item)"]:::level
    D --> S["Level 2: Section\nMethods, Results, etc.\n(~8 items)"]:::level
    S --> C["Level 3A: Semantic Chunk\n300 words overlapping\n(~40 items)"]:::level
    C --> F["Level 3B: Proposition\nAtomic Fact Claim\n(~120 items)"]:::level
```

---

## ReAct Thought Traces

Every agent exposes its internal logic in real-time using the OBS/THK/ACT/OUT paradigm (Observe, Think, Act, Output). This guarantees absolute transparency.

**Agent 2 Example:**
```text
OBS  Received 5 chunks. Query asks for pembrolizumab side effects.
THK  Relevance is high. I need to check freshness because immunotherapy changes fast.
ACT  Evaluating freshness metadata. Oldest paper is 2021. Acceptable.
OUT  PASS. No contradictions detected. Proceed to Agent 7.
```

---

## API Reference

| Method | Path | Purpose |
|---|---|---|
| POST | `/chat` | Submits a query and returns the final JSON response |
| GET | `/stream` | Connects to SSE endpoint for live ReAct thought traces |
| POST | `/feedback` | Submits thumbs up/down for Agent 6 processing |
| GET | `/health` | Verifies connections to all 4 databases |

---

## Scheduled Jobs

| Job | Schedule | Purpose |
|---|---|---|
| Weekly benchmark | Sunday 2am | Track system improvement over time (86.7% baseline) |
| Daily Agent 6 insights | Daily 6am | Generate recommendations based on yesterday's telemetry |
| Freshness sweep | Every 3 days | Flag stale vector clusters for Agent 4B update |
| Daily paper monitor | Daily 4am | Check PubMed RSS for highly cited new relevant papers |
| Gap-targeted sweep | Sunday 3am | Find and ingest papers for known user knowledge gaps |

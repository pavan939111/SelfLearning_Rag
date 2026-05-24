# Self-Learning and Self-Healing RAG

**A biomedical research assistant that fixes its own mistakes.**

Most AI assistants fail silently — they give you a confident wrong answer and you never know it was wrong. Self-Learning and Self-Healing RAG is different. When it cannot find good evidence, it diagnoses why, repairs itself, and tries again before giving you any answer.

Built on 1,767 PubMed papers across immunotherapy, drug interactions, and genomics.

---


## System Architecture (Holistic View)

This is the complete bird's-eye view of how the React frontend, FastAPI backend, 9 autonomous agents, and 4 specialized databases interact.

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
    REDIS -->|5. Cache Miss| HOT
    
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

## The Core Idea

```mermaid
graph LR
    A["👤 User: Asks a medical question"] --> B["🔍 System: Retrieves biomedical evidence"]
    B --> C{"⚖️ Quality Gate:\nIs evidence relevant, complete, and fresh?"}
    C -->|Yes: Evidence is solid| D["✍️ Generation:\nWrite answer with inline citations"]
    C -->|No: Evidence is flawed| E["🩺 Diagnosis:\nAgent identifies root cause of failure"]
    E --> F["🔧 Repair:\nAdjust query, fetch live data, and re-search"]
    F --> B
    D --> G["✅ User: Receives a reliable, verified answer"]
```

The system never gives you an answer it has not verified first.

---

## What It Can Answer

Ask questions about:
- **Immunotherapy** — pembrolizumab, nivolumab, checkpoint inhibitors, CAR-T therapy
- **Drug interactions** — CYP450 metabolism, warfarin combinations, adverse reactions
- **Genomics** — CRISPR, biomarkers, SNPs, gene expression, BRCA mutations

If you ask something unrelated to biomedical research, it tells you so and suggests relevant questions.

---

## How the Nine Agents Work Together

Think of it as a team of specialists, each with one job:

```mermaid
flowchart TD
    USER(["👤 User Query: e.g. 'How does pembrolizumab work?'"]) --> A1

    subgraph HOT ["⚡ Hot Path: Answering your question in real time"]
        A1["🔍 Agent 1 (Finder)\nScans 22,600+ chunks\nUses dense/sparse hybrid search"]
        A1 --> A2["⚖️ Agent 2 (Inspector)\nStrictly verifies evidence quality\nChecks relevance & freshness"]
        A2 -->|"Evidence Approved"| A7["✍️ Agent 7 (Writer)\nDrafts response\nEmbeds specific citations"]
        A2 -->|"Evidence Rejected"| RC["🔄 Repair Team (Agents 3 & 4A)\nDiagnoses search failures\nFetches new data if needed"]
        RC -->|"Retries Search"| A1
    end

    subgraph COLD ["🌙 Cold Path: Keeping the system healthy in background"]
        A4B["🔧 Agent 4B\nResolves deep knowledge gaps"]
        A5A["✅ Agent 5A\nFilters incoming PubMed papers"]
        A5B["📥 Agent 5B\nIndexes verified biomedical papers"]
        A6["🧠 Agent 6\nLearns from query success rates"]
    end

    A7 --> ANSWER(["✅ Final Answer Delivered\nIncludes confidence score"])
    A7 -.->|"Sends interaction data"| A6
    A6 -.->|"Optimizes future searches"| A1
    A6 -.->|"Improves confidence scoring"| A2
```

---

## What Happens When Evidence Is Bad

This is the most important part — the self-healing repair cycle:

```mermaid
flowchart TD
    FAIL(["❌ Agent 2 Rejection:\n'Evidence does not fully answer the question'"]) --> A3

    A3["🔍 Agent 3 (Detective)\nRuns 5 automated diagnostic tests to find the root cause"]

    A3 -->|"Cause: Search strategy was too narrow"| A4A
    A3 -->|"Cause: Information is completely missing"| EXIT

    A4A["🎯 Agent 4A (Strategist)\nGenerates sub-queries to fill knowledge gaps\nFetches recent PubMed articles if data is stale"]

    EXIT["📤 Queue Agent 4B\nSchedules background corpus repair\n(System will answer based on partial data)"]

    A4A --> RETRY["🔄 Second Attempt\nExecutes new search strategy\nMerges new findings with original evidence"]
    RETRY --> CHECK["⚖️ Agent 2 Re-evaluation\n'Does the merged evidence pass now?'"]

    CHECK -->|"Passes"| GEN["✍️ Agent 7 generates complete answer"]
    CHECK -->|"Still Fails"| HONEST["✍️ Agent 7 generates partial answer\nTransparently explains what is missing"]
```

**The key insight:** The system tries twice, merges the best evidence from both attempts, and always tells you honestly what it could and could not find.

---

## How It Gets Smarter Over Time

Agent 6 watches every query and learns from the results:

```mermaid
flowchart LR
    subgraph INPUTS ["Data Sources (What Agent 6 observes)"]
        I1["Query Outcomes (Pass/Fail)"]
        I2["User Feedback (Thumbs up/down)"]
        I3["Weekly Automated Benchmark Scores"]
    end

    A6(["🧠 Agent 6 (Longitudinal Learning Engine)"])

    subgraph OUTPUTS ["System Optimizations (How it improves)"]
        O1["Recalibrates confidence scores to match reality"]
        O2["Identifies knowledge gaps for Agent 5A to fill"]
        O3["Adjusts cache expiry (fast-changing topics expire sooner)"]
        O4["Generates actionable recommendations for human admins"]
    end

    INPUTS --> A6
    A6 --> OUTPUTS
```

**Result:** The 86.7% baseline pass rate improves automatically every week as the system learns from real usage.

---

## The Quality Check in Detail

Agent 2 runs 5 checks on retrieved evidence **before** writing a single word of the answer:

```mermaid
flowchart LR
    IN(["Raw Retrieved Evidence\n(From Vector Database)"]) --> C1

    C1{"Check 1: Relevance\nDoes it address the core topic?"}
    C1 -->|"Irrelevant"| STOP1["❌ Blocking Failure\nTrigger Repair Cycle"]
    C1 -->|"Relevant"| C2

    C2{"Check 2: Completeness\nAre all query aspects covered?"}
    C2 -->|"Incomplete"| STOP2["❌ Blocking Failure\nTrigger Repair Cycle"]
    C2 -->|"Complete"| C3

    C3{"Check 3: Freshness\nIs the data recent enough?"}
    C3 -->|"Stale Data"| FLAG1["⚠️ Non-Blocking Flag\nTrigger Live PubMed Fetch"]
    C3 -->|"Fresh"| C4
    FLAG1 --> C4

    C4{"Check 4: Calibration\nCalculate dynamic confidence interval"}
    C4 --> C5

    C5{"Check 5: Contradiction\nDo the papers disagree?"}
    C5 -->|"Conflict Found"| FLAG2["⚠️ Non-Blocking Flag\nSurface conflict in final answer"]
    C5 -->|"Consensus"| OUT
    FLAG2 --> OUT

    OUT(["✅ Evidence Fully Approved\nProceed to Answer Generation"])
```

Checks 1 and 2 are **blocking** — if they fail the system repairs and tries again.
Checks 3, 4, and 5 are **non-blocking** — they add context and flags to the answer.

---

## How Papers Enter the Knowledge Base

Not every paper gets added. Agent 5A applies strict rules:

```mermaid
flowchart TD
    SOURCES(["External Literature:\nPubMed, arXiv, Semantic Scholar"]) --> GATE

    GATE["Agent 5A (Verification Gate)\nEnsures only high-quality papers enter"]

    GATE --> R1{"Domain Check\nIs it biomedical?"}
    R1 -->|"No"| DISCARD1(["❌ Rejected: Out of scope"])
    R1 -->|"Yes"| R2

    R2{"Utility Check\nDoes it fill a known gap?"}
    R2 -->|"No"| DISCARD2(["❌ Rejected: Redundant"])
    R2 -->|"Yes"| R3

    R3{"Quality Check\nIs it an RCT or peer-reviewed?"}
    R3 --> R4

    R4{"Impact Check\nHigh citation velocity? (>50 citations)"}

    R4 --> RULE{"Did it pass all strict rules?"}
    RULE -->|"Failed"| DISCARD3(["❌ Rejected: Low impact"])
    RULE -->|"Passed"| CHUNK

    CHUNK["Agent 5B (Chunker)\nSplits into 4 hierarchies:\nDocument -> Section -> Chunk -> Fact Claim"]
    CHUNK --> STAGE["Staging Database\nMust pass 3 synthetic test queries"]
    STAGE -->|"Fails Tests"| ROLLBACK(["❌ Rollback: Discarded"])
    STAGE -->|"Passes Tests"| LIVE(["✅ Promoted to Production Vector Database"])
```

---

## The Four Databases

```mermaid
flowchart TB
    subgraph Q ["🗄️ Qdrant Cloud (Vector Database for Neural Search)"]
        Q1["Document Level: 1,500 full papers"]
        Q2["Section Level: 4,700 contextual sections"]
        Q3["Chunk Level: 10,900 searchable passages"]
        Q4["Claim Level: 5,500 specific factual claims"]
    end

    subgraph S ["📊 Supabase PostgreSQL (Relational Data & Telemetry)"]
        S1["Ingestion logs & paper metadata"]
        S2["Failure rates & repair history"]
        S3["Agent 6 learning metrics"]
        S4["ReAct thought traces (OBS/THK/ACT/OUT)"]
    end

    subgraph N ["🕸️ Neo4j AuraDB (Knowledge Graph)"]
        N1["1,767 Paper Nodes"]
        N2["Citation & Reference Edges"]
        N3["Contradiction & Agreement Edges"]
    end

    subgraph R ["⚡ Upstash Redis (High-Speed Caching & Queues)"]
        R1["Semantic Cache (SimHash) - 3.4x speedup"]
        R2["Conversation Context Memory (last 6 turns)"]
        R3["Celery Background Job Queues"]
    end
```

---

## The Transparency Feature

Every step the system takes is visible in real time. You can watch each agent think:

```
Agent 1 — Finder
  OBS  Query: "How does pembrolizumab work?" — simple factual type
  THK  Immunotherapy cluster. No date restriction needed.
  ACT  Hybrid search: dense + sparse. Apply cluster filter.
  OUT  5 chunks retrieved. Top score: 0.934. All from 2021-2023.

Agent 2 — Inspector
  OBS  5 chunks. Avg relevance 0.89. All mention PD-1 pathway.
  THK  Good relevance. Completeness checks out. Freshness OK.
  ACT  All 5 checks pass. Confidence calibrated to 0.82.
  OUT  PASS -> Agent 7 can generate.

Agent 7 — Writer
  OBS  5 verified chunks. Confidence 0.82. Format: prose.
  THK  Good evidence. Generate with inline citations.
  ACT  Generate response. Extract claim provenance.
  OUT  312 chars. 3 citations. Ready.
```

This OBS/THK/ACT/OUT format (called ReAct) shows you exactly why the system made each decision.

---

## Results

| Metric | Value |
|--------|-------|
| Benchmark pass rate | **86.7%** |
| Papers indexed | **1,767** |
| Searchable chunks | **22,600+** |
| Average confidence | **0.67** |
| Cache speedup | **3.4×** |
| Monthly cost | **₹0** |

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/pavan939111/SelfLearning_Rag.git
cd SelfLearning_Rag

# Install Python dependencies
pip install -r requirements.txt

# Add your API keys (copy the example file)
cp keys.txt.example keys.txt
# Edit keys.txt with your credentials

# Test all database connections
python test_connections.py

# Build the corpus (1-2 hours, can be interrupted)
python run_ingestion.py

# Start the backend
uvicorn api.main:app --port 8000

# Start the frontend (new terminal)
cd frontend && npm install && npm run dev
```

Open **http://localhost:5173**

See [SETUP.md](SETUP.md) for detailed instructions including free cloud service setup.

---

## Tech Stack

| What | Technology |
|------|-----------|
| AI reasoning | Gemini 2.0 Flash |
| Biomedical embeddings | S-PubMedBert-MS-MARCO |
| Vector search | Qdrant Cloud |
| Database | Supabase PostgreSQL |
| Knowledge graph | Neo4j AuraDB |
| Cache + queues | Upstash Redis |
| Backend API | FastAPI + Celery |
| Frontend | Vite + React |

All on free tier. Zero monthly cost.

---

## Project Structure

```
selflearning_rag/
├── agents/          # The nine agents
│   ├── models.py    # Shared data contracts (Pydantic)
│   ├── agent1_retrieval.py
│   ├── agent2_evaluator.py
│   ├── agent3_classifier.py
│   ├── agent4a_formulator.py
│   ├── agent4b_repair.py
│   ├── agent5a_verifier.py
│   ├── agent6_learning.py
│   ├── agent7_generator.py
│   └── repair_cycle.py
├── api/             # FastAPI backend
├── database/        # Database clients
├── ingestion/       # Paper fetching and processing
├── workers/         # Background Celery jobs
├── utils/           # Logging and thought traces
├── scripts/         # Setup and verification scripts
├── tests/           # Test suite
├── frontend/        # React UI
├── SETUP.md         # Detailed setup guide
├── ARCHITECTURE.md  # Technical deep dive
└── CHANGELOG.md     # Version history
```

---

## License

MIT — Pavan Kumar Kunukuntla — 2026

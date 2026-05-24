# Self-Learning and Self-Healing RAG

**A biomedical research assistant that fixes its own mistakes.**

Most AI assistants fail silently — they give you a confident wrong answer and you never know it was wrong. Self-Learning and Self-Healing RAG is different. When it cannot find good evidence, it diagnoses why, repairs itself, and tries again before giving you any answer.

Built on 1,767 PubMed papers across immunotherapy, drug interactions, and genomics.

---

## System Architecture

This is the complete bird's-eye view of how the React frontend, FastAPI backend, 9 autonomous agents, and 4 specialized databases interact.

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
    
    subgraph HOT ["⚡ Hot Path (Real-Time Pipeline)"]
        direction TB
        A1["🔍 Agent 1 (Finder)\nHybrid Search"]:::hotpath
        A2{"⚖️ Agent 2 (Inspector)\nQuality Gate"}:::hotpath
        A7["✍️ Agent 7 (Writer)\nFormat & Cite"]:::hotpath
        A3["🩺 Agent 3 (Detective)\nDiagnosis"]:::hotpath
        A4A["🎯 Agent 4A (Formulator)\nQuery Rewrite"]:::hotpath
        
        A1 --> A2
        A2 -->|"Passes"| A7
        A2 -->|"Fails"| A3
        A3 --> A4A
        A4A -->|"Retries"| A1
    end

    CACHE -->|"Cache Miss"| A1
    CACHE -.->|"Cache Hit"| A2
    
    subgraph COLD ["🌙 Cold Path (Background Maintenance)"]
        direction TB
        A4B["🔧 Agent 4B\n(Corpus Repair)"]:::coldpath
        A5A["✅ Agent 5A\n(PubMed Verifier)"]:::coldpath
        A5B["📥 Agent 5B\n(Data Ingester)"]:::coldpath
        A6["🧠 Agent 6\n(Learning Engine)"]:::coldpath
    end

    A3 -.->|"Schedules Repair"| A4B
    A7 -->|"Final Verified Answer"| UI
    A7 -.->|"Logs Query Telemetry"| A6
    A6 -.->|"Updates Calibration"| A2
    
    subgraph DB ["🗄️ Infrastructure Layer"]
        direction LR
        REDIS[("⚡ Redis\nQueues")]:::database
        QDRANT[("🧠 Qdrant\nVectors")]:::database
        NEO4J[("🕸️ Neo4j\nGraph")]:::database
        SUPA[("📊 Supabase\nSQL")]:::database
    end
    
    HOT <--> DB
    COLD <--> DB
```

> **Note:** For a highly technical breakdown of each individual agent, the Neo4j graph expansion, and the hybrid search mechanics, please read the [ARCHITECTURE.md](ARCHITECTURE.md) document.

---

## The Core Idea

```mermaid
graph LR
    classDef core fill:#e8f5e9,stroke:#66bb6a,stroke-width:2px,color:#000,rx:5px
    classDef fail fill:#ffebee,stroke:#ef5350,stroke-width:2px,color:#000,rx:5px

    A["👤 User: Asks a medical question"]:::core --> B["🔍 System: Retrieves biomedical evidence"]:::core
    B --> C{"⚖️ Quality Gate:\nIs evidence relevant, complete, and fresh?"}:::core
    C -->|Yes: Evidence is solid| D["✍️ Generation:\nWrite answer with inline citations"]:::core
    C -->|No: Evidence is flawed| E["🩺 Diagnosis:\nAgent identifies root cause of failure"]:::fail
    E --> F["🔧 Repair:\nAdjust query, fetch live data, and re-search"]:::fail
    F --> B
    D --> G["✅ User: Receives a reliable, verified answer"]:::core
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

## What Happens When Evidence Is Bad (The Repair Cycle)

This is the most important part — the self-healing repair cycle:

```mermaid
flowchart TD
    classDef fail fill:#ffebee,stroke:#ef5350,stroke-width:2px,color:#000,rx:5px
    classDef repair fill:#fff3e0,stroke:#ffa726,stroke-width:2px,color:#000,rx:5px
    classDef success fill:#e8f5e9,stroke:#66bb6a,stroke-width:2px,color:#000,rx:5px

    FAIL(["❌ Agent 2 Rejection:\n'Evidence does not fully answer the question'"]):::fail --> A3

    A3["🔍 Agent 3 (Detective)\nRuns 5 automated diagnostic tests to find the root cause"]:::repair

    A3 -->|"Cause: Search strategy was too narrow"| A4A
    A3 -->|"Cause: Information is completely missing"| EXIT

    A4A["🎯 Agent 4A (Strategist)\nGenerates sub-queries to fill knowledge gaps\nFetches recent PubMed articles if data is stale"]:::repair

    EXIT["📤 Queue Agent 4B\nSchedules background corpus repair\n(System will answer based on partial data)"]:::repair

    A4A --> RETRY["🔄 Second Attempt\nExecutes new search strategy\nMerges new findings with original evidence"]:::repair
    RETRY --> CHECK["⚖️ Agent 2 Re-evaluation\n'Does the merged evidence pass now?'"]:::success

    CHECK -->|"Passes"| GEN["✍️ Agent 7 generates complete answer"]:::success
    CHECK -->|"Still Fails"| HONEST["✍️ Agent 7 generates partial answer\nTransparently explains what is missing"]:::fail
```

**The key insight:** The system tries twice, merges the best evidence from both attempts, and always tells you honestly what it could and could not find.

---

## How It Gets Smarter Over Time

Agent 6 watches every query and learns from the results:

```mermaid
flowchart LR
    classDef data fill:#e3f2fd,stroke:#42a5f5,stroke-width:2px,color:#000,rx:5px
    classDef engine fill:#f3e5f5,stroke:#ab47bc,stroke-width:2px,color:#000,rx:10px
    classDef optimization fill:#e8f5e9,stroke:#66bb6a,stroke-width:2px,color:#000,rx:5px

    subgraph INPUTS ["Data Sources (What Agent 6 observes)"]
        I1["Query Outcomes (Pass/Fail)"]:::data
        I2["User Feedback (Thumbs up/down)"]:::data
        I3["Weekly Automated Benchmark Scores"]:::data
    end

    A6(["🧠 Agent 6 (Longitudinal Learning Engine)"]):::engine

    subgraph OUTPUTS ["System Optimizations (How it improves)"]
        O1["Recalibrates confidence scores to match reality"]:::optimization
        O2["Identifies knowledge gaps for Agent 5A to fill"]:::optimization
        O3["Adjusts cache expiry (fast-changing topics expire sooner)"]:::optimization
        O4["Generates actionable recommendations for human admins"]:::optimization
    end

    INPUTS --> A6
    A6 --> OUTPUTS
```

**Result:** The 86.7% baseline pass rate improves automatically every week as the system learns from real usage.

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

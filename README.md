# FailureRAG

**A biomedical research assistant that fixes its own mistakes.**

Most AI assistants fail silently — they give you a confident wrong answer and you never know it was wrong. FailureRAG is different. When it cannot find good evidence, it diagnoses why, repairs itself, and tries again before giving you any answer.

Built on 1,767 PubMed papers across immunotherapy, drug interactions, and genomics.

---

## The Core Idea

```mermaid
graph LR
    A[You ask a question] --> B[System finds evidence]
    B --> C{Is the evidence good enough?}
    C -->|Yes| D[Generate answer with citations]
    C -->|No| E[Diagnose why it failed]
    E --> F[Fix the problem]
    F --> B
    D --> G[You get a reliable answer]

    style A fill:#1a2a4a,stroke:#4a9eff,color:#e8eef8
    style B fill:#1a2a4a,stroke:#4a9eff,color:#e8eef8
    style C fill:#2a2a1a,stroke:#ffd60a,color:#ffd60a
    style D fill:#1a3a1a,stroke:#00e5a0,color:#00e5a0
    style E fill:#2a2a1a,stroke:#ffd60a,color:#ffd60a
    style F fill:#2a1a0a,stroke:#ff8c42,color:#ff8c42
    style G fill:#1a3a1a,stroke:#00e5a0,color:#00e5a0
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
    USER([You ask a question]) --> A1

    subgraph HOT ["⚡ Answering your question — happens in real time"]
        A1["🔍 Agent 1 — Finder\nSearches 22,600+ research chunks\nUses 5 different search strategies"]
        A1 --> A2["🔬 Agent 2 — Inspector\nChecks if evidence is good enough\nRuns 5 quality tests before generating"]
        A2 -->|Evidence passes| A7["✍️ Agent 7 — Writer\nGenerates answer with citations\nShows confidence score"]
        A2 -->|Evidence fails| RC["🔄 Repair Team\nAgent 3 + Agent 4A\nDiagnoses and fixes the problem"]
        RC --> A1
    end

    subgraph COLD ["🌙 Running in background — keeps system healthy"]
        A4B["🔧 Agent 4B\nFixes corpus problems\nasync — never slows you down"]
        A5A["✅ Agent 5A\nVerifies new papers\nbefore adding to corpus"]
        A5B["📥 Agent 5B\nAdds new papers\nto the knowledge base"]
        A6["🧠 Agent 6\nLearns from every query\nMakes system smarter over time"]
    end

    A7 --> ANSWER([You get a reliable answer])
    A7 --> A6
    A6 -.->|Improves search| A1
    A6 -.->|Improves confidence| A2

    style USER fill:#0f2a1a,stroke:#00e5a0,color:#00e5a0
    style ANSWER fill:#0f2a1a,stroke:#00e5a0,color:#00e5a0
    style A1 fill:#1a2a4a,stroke:#4a9eff,color:#4a9eff
    style A2 fill:#1a3a4a,stroke:#00d4ff,color:#00d4ff
    style A7 fill:#1a3a1a,stroke:#00e5a0,color:#00e5a0
    style RC fill:#2a1a0a,stroke:#ff8c42,color:#ff8c42
    style A4B fill:#2a1a2a,stroke:#a855f7,color:#a855f7
    style A5A fill:#1a2a3a,stroke:#60a5fa,color:#60a5fa
    style A5B fill:#1a3a3a,stroke:#34d399,color:#34d399
    style A6 fill:#3a1a3a,stroke:#e879f9,color:#e879f9
```

---

## What Happens When Evidence Is Bad

This is the most important part — the self-healing repair cycle:

```mermaid
flowchart TD
    FAIL(["❌ Agent 2 says:\nevidence is not good enough"]) --> A3

    A3["🔍 Agent 3 — Detective\nRuns 5 diagnostic tests\nFinds the root cause"]

    A3 -->|"Problem: Wrong search strategy\nor filters too strict"| A4A
    A3 -->|"Problem: Knowledge is outdated\nor missing from corpus"| EXIT

    A4A["🎯 Agent 4A — Strategist\nRe-thinks the search approach\nFormulates better targeted queries\nMerges new evidence with original"]

    EXIT["📤 Queue Agent 4B\nFix the corpus in background\nYou still get an answer now"]

    A4A --> RETRY["🔄 Try Again\nSearch with new strategy\nMerge with original evidence"]
    RETRY --> CHECK["🔬 Agent 2 checks again\nDid the new evidence help?"]

    CHECK -->|"Yes — evidence is good now"| GEN["✍️ Agent 7 generates\nyour answer"]
    CHECK -->|"Still not good after 2 tries"| HONEST["✍️ Agent 7 generates\nwith honest note:\nsome aspects not covered"]

    style FAIL fill:#3a1a1a,stroke:#ff4d6d,color:#ff4d6d
    style A3 fill:#2a2a1a,stroke:#ffd60a,color:#ffd60a
    style A4A fill:#2a1a0a,stroke:#ff8c42,color:#ff8c42
    style EXIT fill:#2a1a2a,stroke:#a855f7,color:#a855f7
    style RETRY fill:#1a2a4a,stroke:#4a9eff,color:#4a9eff
    style CHECK fill:#1a3a4a,stroke:#00d4ff,color:#00d4ff
    style GEN fill:#1a3a1a,stroke:#00e5a0,color:#00e5a0
    style HONEST fill:#2a2a1a,stroke:#ffd60a,color:#ffd60a
```

**The key insight:** The system tries twice, merges the best evidence from both attempts, and always tells you honestly what it could and could not find.

---

## How It Gets Smarter Over Time

Agent 6 watches every query and learns from the results:

```mermaid
flowchart LR
    subgraph INPUTS ["What Agent 6 observes"]
        I1["Every query result\n✓ or ✗"]
        I2["User feedback\n👍 or 👎"]
        I3["Weekly benchmark\nscores"]
    end

    A6(["🧠 Agent 6\nLearning Engine"])

    subgraph OUTPUTS ["How it improves the system"]
        O1["Adjusts confidence scores\nso they match reality"]
        O2["Tracks knowledge gaps\nto fill them with new papers"]
        O3["Controls cache expiry\nfast-changing topics expire sooner"]
        O4["Recommends parameter changes\nfor admin to approve"]
    end

    INPUTS --> A6
    A6 --> OUTPUTS

    style A6 fill:#3a1a3a,stroke:#e879f9,color:#e879f9
```

**Result:** The 86.7% baseline pass rate improves automatically every week as the system learns from real usage.

---

## The Quality Check in Detail

Agent 2 runs 5 checks on retrieved evidence **before** writing a single word of the answer:

```mermaid
flowchart LR
    IN(["Retrieved\nevidence"]) --> C1

    C1{"Check 1\nIs it relevant\nto the question?"}
    C1 -->|No| STOP1["❌ Stop\nEnter repair cycle"]
    C1 -->|Yes| C2

    C2{"Check 2\nDoes it fully\nanswer the question?"}
    C2 -->|No| STOP2["❌ Stop\nEnter repair cycle"]
    C2 -->|Yes| C3

    C3{"Check 3\nIs it fresh enough\nfor this topic?"}
    C3 -->|No| FLAG1["⚠️ Flag it\nFetch live from PubMed"]
    C3 -->|Yes| C4
    FLAG1 --> C4

    C4{"Check 4\nWhat confidence\nshould we express?"}
    C4 --> C5

    C5{"Check 5\nDo any sources\ncontradict each other?"}
    C5 -->|Yes| FLAG2["⚠️ Flag it\nTell user about conflict"]
    C5 -->|No| OUT
    FLAG2 --> OUT

    OUT(["✓ Evidence approved\nGenerate answer"])

    style IN fill:#1a2a4a,stroke:#4a9eff,color:#4a9eff
    style C1 fill:#1a3a4a,stroke:#00d4ff,color:#00d4ff
    style C2 fill:#1a3a4a,stroke:#00d4ff,color:#00d4ff
    style C3 fill:#1a3a4a,stroke:#00d4ff,color:#00d4ff
    style C4 fill:#1a3a4a,stroke:#00d4ff,color:#00d4ff
    style C5 fill:#1a3a4a,stroke:#00d4ff,color:#00d4ff
    style STOP1 fill:#3a1a1a,stroke:#ff4d6d,color:#ff4d6d
    style STOP2 fill:#3a1a1a,stroke:#ff4d6d,color:#ff4d6d
    style FLAG1 fill:#2a1a0a,stroke:#ff8c42,color:#ff8c42
    style FLAG2 fill:#2a1a0a,stroke:#ff8c42,color:#ff8c42
    style OUT fill:#1a3a1a,stroke:#00e5a0,color:#00e5a0
```

Checks 1 and 2 are **blocking** — if they fail the system repairs and tries again.
Checks 3, 4, and 5 are **non-blocking** — they add context and flags to the answer.

---

## How Papers Enter the Knowledge Base

Not every paper gets added. Agent 5A applies strict rules:

```mermaid
flowchart TD
    SOURCES(["PubMed · arXiv\nbioRxiv · Semantic Scholar"])
    SOURCES --> GATE

    GATE["Agent 5A — Verification Gate\nEvery paper must pass 4 checks"]

    GATE --> R1{"Is it biomedical?\nDomain check"}
    R1 -->|No| DISCARD1(["❌ Discard"])
    R1 -->|Yes| R2

    R2{"Does it fill a gap\nor correct something?"}
    R2 -->|No| DISCARD2(["❌ Discard"])
    R2 -->|Yes| R3

    R3{"Is it quality evidence?\nRCT · Review · Cohort?"}
    R3 --> R4

    R4{"Citation velocity check\nSemantic Scholar API\n50+ citations = important"}

    R4 --> RULE{"Any rule matched?"}
    RULE -->|None matched| DISCARD3(["❌ Discard"])
    RULE -->|At least one| CHUNK

    CHUNK["Agent 5B — Chunker\nSplit into 4 levels\nDocument → Section → Chunk → Claim"]
    CHUNK --> STAGE["Staging validation\n3 test queries must pass\nBefore production"]
    STAGE -->|Fails| ROLLBACK(["❌ Rollback"])
    STAGE -->|Passes| LIVE(["✓ Added to corpus"])

    style SOURCES fill:#1a2a3a,stroke:#60a5fa,color:#60a5fa
    style GATE fill:#1a2a3a,stroke:#60a5fa,color:#60a5fa
    style DISCARD1 fill:#3a1a1a,stroke:#ff4d6d,color:#ff4d6d
    style DISCARD2 fill:#3a1a1a,stroke:#ff4d6d,color:#ff4d6d
    style DISCARD3 fill:#3a1a1a,stroke:#ff4d6d,color:#ff4d6d
    style ROLLBACK fill:#3a1a1a,stroke:#ff4d6d,color:#ff4d6d
    style CHUNK fill:#1a3a3a,stroke:#34d399,color:#34d399
    style STAGE fill:#2a2a1a,stroke:#ffd60a,color:#ffd60a
    style LIVE fill:#1a3a1a,stroke:#00e5a0,color:#00e5a0
```

---

## The Four Databases

```mermaid
flowchart TB
    subgraph Q ["🗄️ Qdrant Cloud — finds relevant research"]
        Q1["Document level\n1,500 papers"]
        Q2["Section level\n4,700 sections"]
        Q3["Chunk level\n10,900 passages"]
        Q4["Claim level\n5,500 facts"]
    end

    subgraph S ["📊 Supabase — tracks everything that happens"]
        S1["Ingestion logs"]
        S2["Failure + repair history"]
        S3["Agent 6 learning data"]
        S4["Benchmark results"]
        S5["User feedback"]
        S6["Reasoning traces"]
    end

    subgraph N ["🕸️ Neo4j — knows how papers relate"]
        N1["1,767 paper nodes"]
        N2["Citation relationships"]
        N3["Contradiction relationships"]
    end

    subgraph R ["⚡ Redis — makes things fast"]
        R1["Query cache\n3.4× speedup"]
        R2["Conversation memory\n6 turns"]
        R3["Background job queues"]
    end

    style Q fill:#0a1a2a,stroke:#00d4ff
    style S fill:#0a1a0a,stroke:#00e5a0
    style N fill:#0a0a2a,stroke:#4a9eff
    style R fill:#1a0a0a,stroke:#ff8c42
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
  OUT  PASS → Agent 7 can generate.

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
failurerag/
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

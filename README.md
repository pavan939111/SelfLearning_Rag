# Self-Learning and Self-Healing RAG

A biomedical research assistant that diagnoses and fixes its own mistakes before giving you an answer.

---

## Why This Exists

Standard AI assistants and Retrieval-Augmented Generation (RAG) systems suffer from a fatal flaw: they fail silently. If they retrieve the wrong information or don't find enough data, they will confidently hallucinate an answer anyway. Self-Learning and Self-Healing RAG solves this by aggressively rejecting its own evidence. When it fails to find the perfect answer, it pauses, diagnoses the root cause of the failure, reformulates its search strategy, and tries again—guaranteeing you only receive verified, highly accurate medical information.

---

## How It Works — System Overview

```mermaid
flowchart TD
    classDef user fill:#f3e5f5,stroke:#ab47bc,stroke-width:2px,color:#000,rx:10px
    classDef frontend fill:#e3f2fd,stroke:#42a5f5,stroke-width:2px,color:#000,rx:10px
    classDef gateway fill:#fff3e0,stroke:#ffa726,stroke-width:2px,color:#000
    classDef hotpath fill:#e0f7fa,stroke:#00bcd4,stroke-width:2px,color:#000,rx:5px
    classDef coldpath fill:#f3e5f5,stroke:#ab47bc,stroke-width:2px,color:#000,rx:5px
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

## The Nine Agents

| Agent | Role | One-line description |
|---|---|---|
| **Agent 1** | Finder | Scours databases using hybrid search and knowledge graphs to find evidence. |
| **Agent 2** | Inspector | The strict quality gate that aggressively rejects poor or incomplete evidence. |
| **Agent 3** | Detective | Diagnoses exactly why Agent 2 rejected the evidence (the root cause). |
| **Agent 4A** | Formulator | Real-time repair engine that rewrites queries and fetches live PubMed data. |
| **Agent 4B** | Mechanic | Background worker that permanently fixes structural gaps in the database. |
| **Agent 5A** | Verifier | Scans new papers and rejects junk science (non-peer-reviewed/low impact). |
| **Agent 5B** | Ingester | Breaks down approved papers into searchable chunks and vectors. |
| **Agent 6** | Brain | Long-term learning engine that optimizes the system based on user feedback. |
| **Agent 7** | Writer | Generates the final human-readable answer with explicit inline citations. |

---

## Quick Start

```bash
git clone https://github.com/pavan939111/SelfLearning_Rag.git
cd SelfLearning_Rag
pip install -r requirements.txt
cp keys.txt.example keys.txt
python run_ingestion.py
uvicorn api.main:app --port 8000
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI Reasoning | Gemini 2.0 Flash |
| Vector Search | Qdrant Cloud |
| Knowledge Graph | Neo4j AuraDB |
| Telemetry Database | Supabase PostgreSQL |
| Cache & Queues | Upstash Redis |
| API Backend | FastAPI + Celery |
| Embeddings | S-PubMedBert-MS-MARCO |
| Frontend | React + Vite |

---

## Results

| Metric | Value |
|---|---|
| Benchmark pass rate | **86.7%** |
| Papers indexed | **1,767** |
| Searchable chunks | **22,600+** |
| Average confidence | **0.67** |
| Synthetic QA Pairs | **50** |

---

## Learn More

- [Architecture deep dive →](ARCHITECTURE.md)
- [Agent reference →](AGENTS.md)
- [Setup guide →](SETUP.md)

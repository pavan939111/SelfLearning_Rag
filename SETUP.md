# FailureRAG — Setup Guide

## Prerequisites

- Python 3.13
- Node.js 18+
- Free accounts on 4 cloud services

## Cloud Services

### Qdrant Cloud — vector database
  https://cloud.qdrant.io
  Create free cluster (1GB)
  Copy: Cluster URL, API key

### Supabase — relational database
  https://supabase.com
  Create project (500MB free)
  Copy: Project URL, anon key
  Action: Run supabase_schema.sql in SQL Editor

### Neo4j AuraDB — knowledge graph
  https://console.neo4j.io
  Create AuraDB Free (200K nodes)
  Copy: URI (neo4j+s://...), username, password
  Note: pauses after inactivity — resume at dashboard

### Upstash Redis — cache and queues
  https://upstash.com
  Create Redis database (10K cmd/day free)
  Copy: Redis URL (rediss://...), password

### Google AI Studio — LLM
  https://aistudio.google.com
  Create API key
  Free: 1,500 requests/day
  Tip: Create multiple keys and add all to keys.txt
       as GEMINI_API_KEY_2, GEMINI_API_KEY_3 etc.

### Semantic Scholar — citation data (optional)
  https://semanticscholar.org/product/api
  Request API key (approved in hours)
  Rate: 1 request/second
  Used for: citation velocity in Agent 5A

## Installation

```bash
# Clone
git clone https://github.com/pavan939111/SelfLearning_Rag.git
cd SelfLearning_Rag

# Python dependencies
pip install -r requirements.txt

# Configure keys
cp keys.txt.example keys.txt
# Edit keys.txt with your cloud service credentials

# Verify all connections
python test_connections.py
# Expected: Qdrant OK, Supabase OK, Neo4j OK, Redis OK

# Frontend dependencies
cd frontend && npm install && cd ..
```

## Supabase Schema

Copy the entire contents of supabase_schema.sql
and run it in your Supabase SQL Editor.
Creates all 13 required tables with indexes.

## Initial Corpus Setup

```bash
# Fetch and ingest 1,767 PubMed papers
# Takes 1-2 hours — checkpointed, safe to interrupt
python run_ingestion.py

# After ingestion: populate Neo4j knowledge graph
python scripts/backfill_neo4j.py

# Build contradiction graph (optional, takes 15min)
python scripts/build_contradiction_graph.py

# Seed 50 benchmark questions
python scripts/seed_benchmarks.py
```

## Running the System

```bash
# Terminal 1 — Backend API
uvicorn api.main:app --port 8000

# Terminal 2 — Frontend
cd frontend && npm run dev

# Terminal 3 — Background workers (optional)
python start_worker.py
```

Open: http://localhost:5173

## Verify Everything Works

```bash
python scripts/verify_all_phases.py
# Expected: 31/32 checks passing
# (Neo4j offline = acceptable warning)
```

## Common Issues

**Gemini 429 — quota exhausted**
  Ingestion and agent calls share quota.
  Pause ingestion while testing: Ctrl+C in ingestion terminal.
  Quota resets daily at midnight Pacific.

**Neo4j DNS failed**
  Instance paused after inactivity.
  Go to console.neo4j.io → Resume instance.
  Wait 3-5 minutes for DNS propagation.

**Redis SSL error**
  REDIS_URL must start with rediss:// (not redis://)
  Upstash always requires SSL.

**Embedding model slow first run**
  Downloads ~400MB from HuggingFace on first run.
  Cached locally afterward.
  Set HF_TOKEN environment variable for faster download.

**Cache not working**
  Verify numpy installed: pip install numpy
  SimHash requires numpy for 32-bit projection.

# FailureRAG Setup Guide

## Prerequisites
- Python 3.13
- Node.js 18+
- Git

## Cloud Services (all free tier)

### 1. Qdrant Cloud
  URL: cloud.qdrant.io
  Create free cluster
  Copy: Cluster URL, API key

### 2. Supabase
  URL: supabase.com
  Create project
  Copy: Project URL, anon key
  Run: supabase_schema.sql in SQL Editor

### 3. Neo4j AuraDB
  URL: console.neo4j.io
  Create free instance
  Copy: URI (neo4j+s://...), username, password
  Note: pauses after inactivity — resume if needed

### 4. Upstash Redis
  URL: upstash.com
  Create Redis database
  Copy: Redis URL (rediss://...), password

### 5. Google AI Studio
  URL: aistudio.google.com
  Create API key
  Free tier: 1500 requests/day

### 6. Semantic Scholar (optional)
  URL: semanticscholar.org/product/api
  Request API key (approved within hours)
  Improves citation velocity tracking

## Installation

1. Clone repository
   git clone https://github.com/pavan939111/SelfLearning_Rag.git
   cd SelfLearning_Rag

2. Install Python dependencies
   pip install -r requirements.txt

3. Create keys.txt (copy from keys.txt.example)
   Fill in all values from cloud services above

4. Test connections
   python test_connections.py
   All 4 databases should show CONNECTED

5. Create Supabase tables
   Copy supabase_schema.sql content
   Run in Supabase SQL Editor

6. Install frontend dependencies
   cd frontend
   npm install
   cd ..

## Running the System

### Development (all terminals)

Terminal 1 — Backend API:
  uvicorn api.main:app --port 8000 --reload

Terminal 2 — Frontend:
  cd frontend && npm run dev

Terminal 3 — Background workers (optional):
  python start_worker.py

### Initial corpus setup (one time)

python run_ingestion.py

Takes 1-2 hours for 1,767 papers.
Checkpointed — safe to interrupt and resume.

### Seed benchmark questions

python scripts/seed_benchmarks.py

### Run baseline benchmark

uvicorn api.main:app --port 8000
python scripts/run_benchmark.py

### Populate Neo4j (after ingestion)

python scripts/backfill_neo4j.py
python scripts/build_contradiction_graph.py

## Verification

python scripts/verify_all_phases.py

Expected: 31/32 checks passing
(Neo4j offline = acceptable warning)

## URLs when running

Frontend:     http://localhost:5173
Backend API:  http://localhost:8000
API docs:     http://localhost:8000/docs
Health check: http://localhost:8000/health

## Common Issues

### Gemini 429 quota exhausted
  Wait for reset (midnight Pacific)
  Add additional API keys to keys.txt
  System falls back gracefully — never crashes

### Neo4j DNS resolution failed
  Instance paused after inactivity
  Go to console.neo4j.io and resume
  Wait 3-5 minutes for DNS propagation

### Redis SSL error
  Ensure REDIS_URL uses rediss:// not redis://
  Upstash requires SSL

### Embedding model download slow
  First run downloads ~400MB from HuggingFace
  Subsequent runs use cache
  Set HF_TOKEN for faster downloads

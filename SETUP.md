# Self-Learning and Self-Healing RAG Setup Guide

## 1. Cloud Service Setup (all free tier)

### Qdrant Cloud
1. Go to cloud.qdrant.io
2. Create account and new cluster (free tier)
3. Copy Cluster URL and API key

### Supabase
1. Go to supabase.com
2. Create new project
3. Copy Project URL and anon key
4. Run the SQL from supabase_schema.sql in SQL editor

### Neo4j AuraDB
1. Go to console.neo4j.io
2. Create free AuraDB instance
3. Copy URI, username, password
4. Note: instance pauses after inactivity — resume if needed

### Upstash Redis
1. Go to upstash.com
2. Create Redis database (free tier)
3. Copy Redis URL and password
4. URL format: rediss://endpoint:6379

### Google AI Studio
1. Go to aistudio.google.com
2. Create API key
3. Free tier: 1500 requests/day per key

### Semantic Scholar (optional but recommended)
1. Go to semanticscholar.org/product/api
2. Request API key (approved within hours)
3. Rate limit: 1 request/second

## 2. Supabase Schema

Run this SQL in your Supabase SQL Editor
before starting the application:

[Include all CREATE TABLE statements from 
the schema we built throughout development]

## 3. Keys Configuration

Create keys.txt in project root:

QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_key
GEMINI_API_KEY=your_gemini_key
NEO4J_URI=neo4j+s://your_instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
REDIS_URL=rediss://your_upstash_endpoint:6379
REDIS_PASSWORD=your_password

Never commit this file — it is in .gitignore

## 4. Running the System

### Development mode (all components):
Terminal 1 — Backend API:
  uvicorn api.main:app --port 8000 --reload

Terminal 2 — Frontend:
  cd frontend && npm run dev

Terminal 3 — Background workers (optional):
  python start_worker.py

Terminal 4 — Monitor ingestion (optional):
  tail -f logs/ingestion.log

### Initial corpus setup:
  python run_ingestion.py
  (Takes 1-2 hours for 1767 papers)

## 5. Verification

Run full system verification:
  python scripts/verify_complete_system.py

Expected: 10/12 checks passing
(Neo4j offline and benchmark count
 are acceptable warnings)

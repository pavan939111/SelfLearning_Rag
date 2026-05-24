# FailureRAG — Setup Guide

## What You Need

**Accounts (all free):**
- [Qdrant Cloud](https://cloud.qdrant.io) — vector database
- [Supabase](https://supabase.com) — relational database
- [Neo4j AuraDB](https://console.neo4j.io) — knowledge graph
- [Upstash](https://upstash.com) — Redis cache
- [Google AI Studio](https://aistudio.google.com) — Gemini API

**Software:**
- Python 3.13
- Node.js 18+

---

## Step 1 — Create Cloud Accounts

### Qdrant Cloud
1. Go to cloud.qdrant.io
2. Create free cluster (1GB storage)
3. Copy your **Cluster URL** and **API key**

### Supabase
1. Go to supabase.com → New project
2. Copy your **Project URL** and **anon key**
3. Go to SQL Editor → paste and run `supabase_schema.sql`

### Neo4j AuraDB
1. Go to console.neo4j.io → Create AuraDB Free
2. Copy your **URI** (starts with neo4j+s://), **username**, **password**
3. Note: the free instance pauses after inactivity — resume at the dashboard if needed

### Upstash Redis
1. Go to upstash.com → Create Database
2. Copy your **Redis URL** (starts with rediss://) and **password**

### Google AI Studio
1. Go to aistudio.google.com → Get API key
2. Free tier: 1,500 requests per day
3. Create multiple keys if you plan to ingest the full corpus

### Semantic Scholar (optional but recommended)
1. Go to semanticscholar.org/product/api → Request API key
2. Approved within a few hours
3. Used for citation velocity tracking in Agent 5A

---

## Step 2 — Install and Configure

```bash
# Clone
git clone https://github.com/pavan939111/SelfLearning_Rag.git
cd SelfLearning_Rag

# Install Python packages
pip install -r requirements.txt

# Copy the key template
cp keys.txt.example keys.txt
```

Open `keys.txt` and fill in your credentials:

```
QDRANT_URL=https://your-cluster.cloud.qdrant.io
QDRANT_API_KEY=your_key_here

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key_here

GEMINI_API_KEY=AIzaSy_your_key_here

NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password_here

REDIS_URL=rediss://your-endpoint.upstash.io:6379
REDIS_PASSWORD=your_password_here

SEMANTIC_SCHOLAR_API_KEY=your_key_here
```

---

## Step 3 — Verify Connections

```bash
python test_connections.py
```

Expected output:
```
Qdrant:    OK
Supabase:  OK
Neo4j:     OK
Redis:     OK
All connections successful
```

---

## Step 4 — Build the Corpus

```bash
python run_ingestion.py
```

This fetches 1,767 PubMed papers and builds the vector index.
Takes 1-2 hours. Safe to interrupt and resume — it checkpoints progress.

After ingestion populate the knowledge graph:
```bash
python scripts/backfill_neo4j.py
```

---

## Step 5 — Seed Benchmark Questions

```bash
python scripts/seed_benchmarks.py
```

Adds 50 biomedical QA pairs for tracking system improvement over time.

---

## Step 6 — Run

**Terminal 1 — Backend:**
```bash
uvicorn api.main:app --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

---

## Step 7 — Verify Everything Works

```bash
python scripts/verify_all_phases.py
```

Expected: 31/32 checks passing.
(Neo4j offline = acceptable warning — just resume at console.neo4j.io)

---

## Common Issues

**"quota exhausted" when chatting**

Ingestion uses Gemini quota. Stop ingestion first:
- Press Ctrl+C in the ingestion terminal
- Wait 1 minute for quota to reset
- Then test the chat

**Neo4j DNS resolution failed**

The free instance paused after inactivity.
Go to console.neo4j.io → find your instance → Resume.
Wait 3-5 minutes for DNS to propagate.

**Redis SSL error**

Your Redis URL must start with `rediss://` not `redis://`
Upstash always requires SSL.

**Embedding model downloads slowly**

Normal on first run — it downloads ~400MB from HuggingFace.
Cached locally after the first run.

**ERR_CONNECTION_REFUSED in browser**

The backend is not running. Start it:
```bash
uvicorn api.main:app --port 8000
```

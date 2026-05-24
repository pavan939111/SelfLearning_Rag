# Tests

## Quick Start

Always set PYTHONPATH first on Windows:
```bash
$env:PYTHONPATH="c:\Users\mahip\OneDrive\Desktop\SelfLearning_Rag"
```

## Run in This Order

**1. Connection check (always first):**
```bash
python test_connections.py
```

**2. Unit tests (fast, no server needed):**
```bash
python tests/unit/test_fetcher.py
python tests/unit/test_chunker.py
python tests/unit/test_qdrant.py
```

**3. Integration tests (databases required):**
```bash
python tests/integration/test_agent1.py
python tests/integration/test_agent2.py
python tests/integration/test_agent6.py
```

**4. System tests (full pipeline + Gemini quota needed):**
```bash
python tests/system/test_repair_cycle.py
python tests/system/test_live_fetch_cycle.py
```

**5. Full verification:**
```bash
python scripts/verify_all_phases.py
```
Expected: 31/32 passing.

## What Each Test Covers

| Test | What it checks |
|------|---------------|
| test_connections.py | All 4 databases reachable |
| test_fetcher.py | PubMed paper fetching |
| test_chunker.py | 4-level hierarchical chunking |
| test_qdrant.py | Vector insert and search |
| test_agent1.py | Full retrieval pipeline |
| test_agent2.py | All 5 quality checks |
| test_agent6.py | Learning accumulation |
| test_repair_cycle.py | A2→A3→A4A full cycle |
| test_live_fetch_cycle.py | PubMed live fetch |
| verify_all_phases.py | All 32 system checks |

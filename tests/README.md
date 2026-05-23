# FailureRAG Tests

## Structure

```text
tests/
  unit/           Individual component tests
  integration/    Agent pipeline tests
  system/         End-to-end system tests
```

## Running Tests

Set PYTHONPATH first (Windows):
```powershell
$env:PYTHONPATH="c:\Users\mahip\OneDrive\Desktop\SelfLearning_Rag"
```

### Connection check (always run first):
```bash
python test_connections.py
```

### Unit tests (fast, no server needed):
```bash
python tests/unit/test_fetcher.py
python tests/unit/test_chunker.py
python tests/unit/test_qdrant.py
```

### Integration tests (databases required):
```bash
python tests/integration/test_agent1.py
python tests/integration/test_agent2.py
python tests/integration/test_agent6.py
python tests/integration/test_api.py
```

### System tests (full pipeline, Gemini required):
```bash
python tests/system/test_repair_cycle.py
python tests/system/test_live_fetch_cycle.py
python tests/system/test_agent6_loop.py
python tests/system/test_agent4b_staging.py
```

### Full verification (run before any commit):
```bash
python scripts/verify_all_phases.py
```
Target: 31/32 or higher

## What Each Test Covers

### Unit
```text
  test_fetcher.py  — PubMedFetcher, PaperRecord
  test_chunker.py  — HierarchicalChunker 4 levels
  test_qdrant.py   — Qdrant insert and search
```

### Integration
```text
  test_agent1.py   — Full retrieval pipeline
  test_agent2.py   — All 5 quality checks
  test_agent4b.py  — Celery task registration
  test_agent6.py   — Learning accumulation
  test_api.py      — All FastAPI endpoints
```

### System
```text
  test_repair_cycle.py    — A2→A3→A4A full cycle
  test_live_fetch_cycle.py — Live fetch end to end
  test_agent6_loop.py     — Complete learning loop
  test_agent4b_staging.py — Staging validation
```

## Verification Script

`scripts/verify_all_phases.py` covers all 32 checks.
Run this for complete system status.
Expected: 31/32 PASS (Neo4j offline = WARN not FAIL)

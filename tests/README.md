# FailureRAG Tests

## Structure

tests/
  unit/           — Individual component tests
  integration/    — Agent pipeline tests  
  system/         — End to end system tests

## Running Tests

### Quick connection check (run first):
  python test_connections.py

### Unit tests (no server needed):
  python tests/unit/test_fetcher.py
  python tests/unit/test_chunker.py
  python tests/unit/test_qdrant.py

### Integration tests (databases required):
  python tests/integration/test_agent1.py
  python tests/integration/test_agent2.py
  python tests/integration/test_agent6.py

### System tests (full pipeline):
  python tests/system/test_repair_cycle.py
  python tests/system/test_live_fetch_cycle.py

### API tests (server must be running on 8000):
  uvicorn api.main:app --port 8000
  python tests/integration/test_api.py

### Full system verification:
  python scripts/verify_complete_system.py

## Test Categories

Unit — tests one component in isolation.
  No external API calls where possible.
  Fast. Run these first.

Integration — tests agents working together.
  Requires Qdrant, Supabase, Redis connected.
  Requires Gemini quota available.
  Medium speed.

System — tests complete user flows.
  Requires all databases and Gemini quota.
  Slowest. Run before major changes.

## Setting PYTHONPATH

Set before running any test:

Windows:
  $env:PYTHONPATH="c:\path\to\failurerag"

Mac/Linux:
  export PYTHONPATH=/path/to/failurerag

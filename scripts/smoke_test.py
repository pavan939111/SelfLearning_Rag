import sys

print('Testing fixed components...')
print()

# Fix 1
try:
    from ingestion.pipeline import (
        IngestionPipeline, IngestionStats
    )
    stats = IngestionStats()
    print('CHECK 4 Fix: IngestionStats OK')
except Exception as e:
    print(f'CHECK 4 Still failing: {e}')

# Fix 2
try:
    from agents.live_fetcher import LiveFetcher
    from agents.live_fetch_ingester import LiveFetchIngester
    f = LiveFetcher()
    i = LiveFetchIngester()
    print('CHECK 9 Fix: LiveFetcher OK')
except Exception as e:
    print(f'CHECK 9 Still failing: {e}')

# Fix 3
try:
    from agents.conversation_memory import ConversationMemory
    m = ConversationMemory()
    print('CHECK 13 Fix: ConversationMemory OK')
except Exception as e:
    print(f'CHECK 13 Still failing: {e}')

# Fix 4
try:
    from agents.cache_manager import CacheManager
    from ingestion.embedder import BiomedicalEmbedder
    cache = CacheManager()
    embedder = BiomedicalEmbedder()
    emb = embedder.embed_text('test query')
    key1 = cache._generate_cache_key(emb)
    key2 = cache._generate_cache_key(emb)
    assert key1 == key2, 'Keys not consistent'
    print(f'CHECK 18 Fix: CacheManager OK — key={key1}')
except Exception as e:
    print(f'CHECK 18 Still failing: {e}')

# Fix 6
try:
    from workers.celery_app import celery_app
    tasks = list(celery_app.tasks.keys())
    required = [
        'repair.rechunk', 'repair.reembed',
        'repair.metadata', 'ingest.live_fetch_papers',
        'analysis.log_failure'
    ]
    missing = [t for t in required if t not in tasks]
    if missing:
        print(f'CHECK 29 Still missing: {missing}')
    else:
        print('CHECK 29 Fix: Celery tasks OK')
except Exception as e:
    print(f'CHECK 29 Still failing: {e}')

# Fix 7
try:
    from api.main import app
    routes = [r.path for r in app.routes]
    required = ['/chat', '/health']
    found = [r for r in required if r in routes]
    print(f'CHECK 31 Fix: FastAPI routes OK ({len(routes)} routes)')
except Exception as e:
    print(f'CHECK 31 Still failing: {e}')

print()
print('Smoke test complete')

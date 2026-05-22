import sys
import random
from agents.cache_manager import CacheManager

def test_simhash():
    print("\n--- TEST 1: SimHash Key Generation ---")
    cache = CacheManager()
    
    # 768-dimension embedding
    emb1 = [random.uniform(-1.0, 1.0) for _ in range(768)]
    # Slightly perturbed (cosine similarity ~0.99)
    emb2 = [v + random.uniform(-0.01, 0.01) for v in emb1]
    # Completely opposite/different
    emb3 = [-v for v in emb1]
    
    key1 = cache._generate_cache_key(emb1)
    key2 = cache._generate_cache_key(emb2)
    key3 = cache._generate_cache_key(emb3)
    
    print(f"Key 1: {key1}")
    print(f"Key 2 (similar): {key2}")
    print(f"Key 3 (opposite): {key3}")
    
    assert key1.startswith("cache:"), "Key 1 must start with cache:"
    assert key1 == key2, "Similar embeddings must generate the exact same SimHash key"
    assert key1 != key3, "Opposite embeddings must generate different keys"
    print("Test 1 PASSED")

def test_get_set():
    print("\n--- TEST 2: Cache Store and Retrieve ---")
    cache = CacheManager()
    if not cache.client:
        print("[SKIP] Redis client not connected. Skipping Redis tests.")
        return
        
    emb = [random.uniform(-1.0, 1.0) for _ in range(768)]
    mock_chunks = [
        {
            "chunk_id": "chunk_mock_1",
            "paper_id": "111111",
            "text": "This is a cached chunk about Pembrolizumab.",
            "year": 2023,
            "topic_cluster": "immunotherapy"
        },
        {
            "chunk_id": "chunk_mock_2",
            "paper_id": "222222",
            "text": "This is a second chunk in immunotherapy topic.",
            "year": 2024,
            "topic_cluster": "immunotherapy"
        }
    ]
    
    # Set to cache
    success = cache.set(emb, mock_chunks, "immunotherapy")
    assert success == True, "Failed to set cache"
    
    # Get from cache
    retrieved = cache.get(emb)
    assert retrieved is not None, "Failed to get cached chunks"
    assert len(retrieved) == 2, f"Expected 2 chunks, got {len(retrieved)}"
    assert retrieved[0]["chunk_id"] == "chunk_mock_1"
    assert retrieved[1]["paper_id"] == "222222"
    print("Test 2 PASSED")

def test_invalidation():
    print("\n--- TEST 3: Cache Invalidation by Topic Cluster ---")
    cache = CacheManager()
    if not cache.client:
        print("[SKIP] Redis client not connected. Skipping Redis tests.")
        return
        
    emb_imm = [random.uniform(-1.0, 1.0) for _ in range(768)]
    emb_gen = [-v for v in emb_imm]
    
    chunks_imm = [{"chunk_id": "imm_1", "topic_cluster": "immunotherapy"}]
    chunks_gen = [{"chunk_id": "gen_1", "topic_cluster": "genomics"}]
    
    # Set both
    cache.set(emb_imm, chunks_imm, "immunotherapy")
    cache.set(emb_gen, chunks_gen, "genomics")
    
    # Verify set
    assert cache.get(emb_imm) is not None
    assert cache.get(emb_gen) is not None
    
    # Invalidate immunotherapy
    deleted = cache.invalidate("immunotherapy")
    print(f"Keys deleted on invalidating 'immunotherapy': {deleted}")
    assert deleted >= 1, "Expected at least 1 key to be deleted"
    
    # Check states: immunotherapy should be gone, genomics should remain
    assert cache.get(emb_imm) is None, "Immunotherapy cache key should be deleted"
    assert cache.get(emb_gen) is not None, "Genomics cache key should not be deleted"
    
    # Clean up genomics
    cache.invalidate("genomics")
    assert cache.get(emb_gen) is None
    print("Test 3 PASSED")

def test_stats():
    print("\n--- TEST 4: Stats Tracking ---")
    cache = CacheManager()
    if not cache.client:
        print("[SKIP] Redis client not connected. Skipping Redis tests.")
        return
        
    stats = cache.get_stats()
    print(f"Stats: {stats}")
    assert "total_keys" in stats
    assert "estimated_size_mb" in stats
    print("Test 4 PASSED")

if __name__ == "__main__":
    test_simhash()
    test_get_set()
    test_invalidation()
    test_stats()
    print("\n==================================================")
    print("        ALL CACHE MANAGER TESTS PASSED")
    print("==================================================")

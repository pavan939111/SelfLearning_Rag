import json
import redis
import numpy as np
from config import get_config
from utils.logger import get_logger
from database.redis_client import RedisManager
from agents.models import RetrievalResult

class CacheManager:
    """
    Semantic Cache Manager for FailureRAG.
    Caches retrieved chunks using a SimHash of the query embedding.
    Never crashes, catching and logging all Redis-related errors.
    """
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger(__name__, level=self.config.log_level)
        
        # Initialize Redis connection using RedisManager
        try:
            self.redis_manager = RedisManager()
            self.client = self.redis_manager.client
            if not self.client:
                self.logger.warning("Redis client is not available in RedisManager.")
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            self.client = None
            
        # Default TTL seconds per topic velocity
        self.DEFAULT_TTL = {
            "immunotherapy": 4 * 3600,       # 4 hours
            "drug_interactions": 24 * 3600,   # 24 hours
            "genomics": 7 * 24 * 3600,        # 7 days
            "default": 24 * 3600              # 24 hours
        }

    def _generate_cache_key(self, query_embedding: list) -> str:
        """
        Generate a semantic hash from the query embedding using a 32-bit SimHash.
        Uses 32 random hyperplanes with a fixed seed for projection.
        """
        import numpy as np
        emb = np.array(query_embedding, dtype=np.float32)
        np.random.seed(42)
        hyperplanes = np.random.randn(32, len(emb))
        projections = hyperplanes @ emb
        bits = (projections > 0).astype(int)
        hash_int = int(
            ''.join(map(str, bits)), 2
        )
        hex_hash = format(hash_int, '08x')
        return f'cache:{hex_hash}'

    def _get_ttl(self, topic_cluster: str) -> int:
        """
        Return TTL seconds based on topic_cluster topic velocity.
        Tries to use config overrides first, then Agent6 dynamic velocity, then falls back to static TTL.
        """
        if not topic_cluster:
            return self.DEFAULT_TTL["default"]
            
        default_ttl = self.DEFAULT_TTL.get(topic_cluster, self.DEFAULT_TTL["default"])
        
        # 1. Config Overrides
        try:
            from utils.config_overrides import get_override
            override_val = get_override(f'cache_ttl_{topic_cluster}', None)
            if override_val is not None:
                return int(override_val)
        except Exception as e:
            self.logger.warning(f"Failed to check cache TTL override: {e}")
            
        # 2. Agent 6 Dynamic Velocity
        try:
            from agents.agent6_learning import Agent6Learning
            agent6 = Agent6Learning()
            velocity = agent6.get_topic_velocity(topic_cluster)
            
            mapping = {
                "high": 4 * 3600,
                "medium": 24 * 3600,
                "low": 7 * 24 * 3600
            }
            if velocity in mapping:
                self.logger.info(f"Dynamic TTL for cluster '{topic_cluster}' determined by Agent 6 velocity '{velocity}': {mapping[velocity]}s")
                return mapping[velocity]
        except Exception as e:
            self.logger.warning(f"Failed to use Agent 6 velocity for cache TTL, falling back to defaults: {e}")
            
        return default_ttl

    def get(self, query_embedding: list[float]) -> list[dict] | None:
        """
        Retrieve chunks list from semantic cache if found, else None.
        Never crashes.
        """
        if not self.client:
            self.logger.warning("Redis client unavailable. Skipping cache lookup.")
            return None
            
        try:
            key = self._generate_cache_key(query_embedding)
            self.logger.info(f"Checking semantic cache for key: {key}")
            
            cached_val = self.client.get(key)
            if cached_val:
                self.logger.info(f"Cache HIT for key: {key}")
                chunks_data = json.loads(cached_val)
                if isinstance(chunks_data, list):
                    return [RetrievalResult.model_validate(c) for c in chunks_data]
            else:
                self.logger.info(f"Cache MISS for key: {key}")
                
            return None
        except Exception as e:
            self.logger.warning(f"Error reading from semantic cache: {e}")
            return None

    def set(self, query_embedding: list[float], chunks: list, topic_cluster: str) -> bool:
        """
        Cache retrieved chunks in Redis with an appropriate topic-based TTL.
        Converts Chunk objects to dicts if required.
        Never crashes.
        """
        if not self.client:
            self.logger.warning("Redis client unavailable. Skipping cache store.")
            return False
            
        try:
            if not query_embedding or chunks is None:
                return False
                
            key = self._generate_cache_key(query_embedding)
            ttl = self._get_ttl(topic_cluster)
            
            # Serialize chunks to standard dictionaries
            if chunks and hasattr(chunks[0], 'model_dump'):
                stored = [c.model_dump() for c in chunks]
            else:
                stored = chunks
                    
            serialized_val = json.dumps(stored)
            
            self.logger.info(f"Writing {len(stored)} chunks to cache key: {key} (TTL: {ttl}s)")
            self.client.set(key, serialized_val, ex=ttl)
            return True
        except Exception as e:
            self.logger.warning(f"Error storing to semantic cache: {e}")
            return False

    def invalidate(self, topic_cluster: str) -> int:
        """
        Scan and delete all cache keys containing chunks belonging to a given topic cluster.
        Called when new papers are ingested for a topic to prevent stale cache entries.
        Never crashes.
        """
        if not self.client:
            self.logger.warning("Redis client unavailable. Skipping cache invalidation.")
            return 0
            
        deleted_count = 0
        try:
            cursor = 0
            keys_to_delete = []
            
            # Scan matching keys
            while True:
                cursor, keys = self.client.scan(cursor=cursor, match="cache:*", count=100)
                for key in keys:
                    try:
                        val = self.client.get(key)
                        if not val:
                            continue
                            
                        chunks = json.loads(val)
                        if isinstance(chunks, list):
                            # Invalidate if any chunk belongs to the target topic cluster
                            if any(c.get("topic_cluster") == topic_cluster for c in chunks if isinstance(c, dict)):
                                keys_to_delete.append(key)
                    except Exception as parse_err:
                        self.logger.warning(f"Failed to check key {key} for invalidation: {parse_err}")
                        
                if cursor == 0:
                    break
                    
            if keys_to_delete:
                self.logger.info(f"Invalidating {len(keys_to_delete)} stale semantic cache keys for topic: {topic_cluster}")
                # Delete keys
                self.client.delete(*keys_to_delete)
                deleted_count = len(keys_to_delete)
                
            return deleted_count
        except Exception as e:
            self.logger.warning(f"Error invalidating semantic cache: {e}")
            return 0

    def get_stats(self) -> dict:
        """
        Return semantic cache statistics including key count and estimated memory usage.
        Never crashes.
        """
        stats = {
            "total_keys": 0,
            "estimated_size_mb": 0.0
        }
        if not self.client:
            return stats
            
        try:
            cursor = 0
            total_bytes = 0
            total_keys = 0
            
            while True:
                cursor, keys = self.client.scan(cursor=cursor, match="cache:*", count=100)
                total_keys += len(keys)
                for key in keys:
                    val = self.client.get(key)
                    if val:
                        total_bytes += len(val.encode("utf-8"))
                        
                if cursor == 0:
                    break
                    
            stats["total_keys"] = total_keys
            stats["estimated_size_mb"] = round(total_bytes / (1024 * 1024), 4)
            return stats
        except Exception as e:
            self.logger.warning(f"Error retrieving cache statistics: {e}")
            return stats

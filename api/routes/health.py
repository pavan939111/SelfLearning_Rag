from fastapi import APIRouter
from api.models.responses import HealthResponse
import time

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
def health_check():
    # Import managers inside the endpoint to avoid circular imports or initialization issues
    from database.qdrant_client import QdrantManager
    from database.supabase_client import SupabaseManager
    from database.neo4j_client import Neo4jManager
    from database.redis_client import RedisManager
    
    qdrant = QdrantManager()
    supabase = SupabaseManager()
    neo4j = Neo4jManager()
    redis = RedisManager()
    
    q_ok = qdrant.test_connection()
    s_ok = supabase.test_connection()
    n_ok = neo4j.test_connection()
    r_ok = redis.test_connection()
    
    corpus_size = {}
    if q_ok:
        try:
            for level in ['document', 'section', 'semantic', 'proposition']:
                info = qdrant.client.get_collection(qdrant.COLLECTIONS[level])
                corpus_size[level] = info.points_count
        except Exception:
            pass
            
    status = "ok" if all([q_ok, s_ok, n_ok, r_ok]) else "degraded"
    
    return HealthResponse(
        status=status,
        qdrant=q_ok,
        supabase=s_ok,
        neo4j=n_ok,
        redis=r_ok,
        corpus_size=corpus_size
    )

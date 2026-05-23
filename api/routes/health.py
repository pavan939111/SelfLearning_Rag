import time
from fastapi import APIRouter
from api.models.responses import HealthResponse
from config import get_config

router = APIRouter()
START_TIME = time.time()

@router.get("/health", response_model=HealthResponse)
def health_check():
    # Import managers inside the endpoint to avoid circular imports
    from database.qdrant_client import QdrantManager
    from database.supabase_client import SupabaseManager
    from database.neo4j_client import Neo4jManager
    from database.redis_client import RedisManager
    
    qdrant = QdrantManager()
    supabase = SupabaseManager()
    neo4j = Neo4jManager()
    redis = RedisManager()
    
    # 1. Databases
    databases = {}
    
    # Qdrant
    t0 = time.time()
    q_ok = qdrant.test_connection()
    q_lat = int((time.time() - t0)*1000)
    q_pts = 0
    if q_ok:
        try:
            info = qdrant.client.get_collection(qdrant.COLLECTIONS["document"])
            q_pts = info.points_count
        except Exception:
            pass
    databases["qdrant"] = {"connected": q_ok, "latency_ms": q_lat, "points_count": q_pts}
    
    # Supabase
    t0 = time.time()
    s_ok = supabase.test_connection()
    s_lat = int((time.time() - t0)*1000)
    databases["supabase"] = {"connected": s_ok, "latency_ms": s_lat}
    
    # Neo4j
    t0 = time.time()
    n_ok = neo4j.test_connection()
    n_lat = int((time.time() - t0)*1000)
    n_pts = 0
    if n_ok and neo4j.driver:
        try:
            with neo4j.driver.session() as session:
                res = session.run("MATCH (n:Paper) RETURN count(n) as c")
                n_pts = res.single()["c"]
        except Exception:
            pass
    databases["neo4j"] = {"connected": n_ok, "latency_ms": n_lat, "paper_count": n_pts}
    
    # Redis
    t0 = time.time()
    r_ok = redis.test_connection()
    r_lat = int((time.time() - t0)*1000)
    r_mem = 0
    if r_ok and redis.client:
        try:
            info = redis.client.info("memory")
            r_mem = info.get("used_memory", 0)
        except Exception:
            pass
    databases["redis"] = {"connected": r_ok, "latency_ms": r_lat, "memory_used": r_mem}
    
    # 2. Agents
    # Gemini remaining calls can be mocked or empty, since there's no API for it
    # We will just put mock/placeholder values for agents for now
    gemini_quota = 1500 # Free tier daily
    last_retrieval_score = 0.0
    if s_ok and supabase.client:
        try:
            res = supabase.client.table("agent2_evaluations").select("score").order("created_at", desc=True).limit(10).execute()
            if res.data:
                last_retrieval_score = sum([r.get("score", 0) for r in res.data]) / len(res.data)
        except Exception:
            pass
            
    agents = {
        "gemini_quota": gemini_quota,
        "last_retrieval_score": round(last_retrieval_score, 3)
    }
    
    # 3. System
    uptime_seconds = int(time.time() - START_TIME)
    requests_today = 0
    cache_hit_rate = 0.0
    
    # To get cache hit rate or requests, we can check redis if r_ok
    # but for simplicity, we mock them if not explicitly stored
    if r_ok and redis.client:
        try:
            # We don't have exact metrics tracked in Redis for total requests_today yet
            # Let's just mock it or try to fetch it if we had it
            requests_today = 0
            cache_hits = 0
            cache_misses = 0
        except Exception:
            pass

    system = {
        "uptime_seconds": uptime_seconds,
        "requests_today": requests_today,
        "cache_hit_rate": cache_hit_rate
    }
    
    status = "healthy" if all([q_ok, s_ok, n_ok, r_ok]) else "degraded"
    if not any([q_ok, s_ok, n_ok, r_ok]):
        status = "unhealthy"
        
    return HealthResponse(
        status=status,
        databases=databases,
        agents=agents,
        system=system
    )

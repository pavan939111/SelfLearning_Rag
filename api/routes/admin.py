from fastapi import APIRouter
from fastapi.responses import JSONResponse
import os
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

@router.get("/stats")
def get_stats():
    from database.qdrant_client import QdrantManager
    from database.supabase_client import SupabaseManager
    
    qdrant = QdrantManager()
    supabase = SupabaseManager()
    
    qdrant_counts = {}
    corpus_ready = False
    if qdrant.client:
        try:
            for level in ['document', 'section', 'semantic', 'proposition']:
                info = qdrant.client.get_collection(qdrant.COLLECTIONS[level])
                qdrant_counts[level] = info.points_count
                if level == 'document' and info.points_count > 100:
                    corpus_ready = True
        except Exception as e:
            logger.warning(f"Failed to get qdrant counts: {e}")
            
    supabase_stats = supabase.get_ingestion_stats()
    
    agent6_insights = 0
    top_gaps = []
    if supabase.client:
        try:
            res_ins = supabase.client.table("agent6_insights").select("id").execute()
            if res_ins.data:
                agent6_insights = len(res_ins.data)
        except Exception as e:
            logger.warning(f"Failed to get agent6_insights count: {e}")
            
        try:
            res_gaps = supabase.client.table("agent6_gaps").select("topic, query_count").order("query_count", desc=True).limit(3).execute()
            if res_gaps.data:
                top_gaps = res_gaps.data
        except Exception as e:
            logger.warning(f"Failed to get top gaps: {e}")
            
    # Simple check if ingestion is running by looking for the lock/checkpoint file
    running = os.path.exists("checkpoint.json") or os.path.exists("logs/ingestion_stats.json")
    
    return {
        "qdrant_counts": qdrant_counts,
        "supabase_stats": supabase_stats,
        "ingestion_running": running,
        "corpus_ready": corpus_ready,
        "agent6_insights": agent6_insights,
        "top_gaps": top_gaps
    }

@router.get("/recent-failures")
def get_recent_failures():
    from database.supabase_client import SupabaseManager
    supabase = SupabaseManager()
    
    if not supabase.client:
        return {"failures": []}
        
    try:
        res = supabase.client.table("agent_failures").select("id, query, failed_check, root_cause, resolved, created_at").order("created_at", desc=True).limit(20).execute()
        
        failures = []
        for r in res.data:
            q = r.get("query", "")
            if q and len(q) > 80:
                r["query"] = q[:77] + "..."
            failures.append(r)
            
        return failures
    except Exception as e:
        logger.error(f"Failed to fetch recent failures: {e}")
        return {"error": str(e)}

@router.get("/corpus-health")
def get_corpus_health():
    from database.qdrant_client import QdrantManager
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    
    qdrant = QdrantManager()
    if not qdrant.client:
        return {"error": "Qdrant not connected"}
        
    try:
        collections_info = []
        doc_count = 0
        for level in ['document', 'section', 'semantic', 'proposition']:
            name = qdrant.COLLECTIONS[level]
            info = qdrant.client.get_collection(name)
            if level == 'document':
                doc_count = info.points_count
            collections_info.append({
                "collection": name,
                "point_count": info.points_count,
                "estimated_papers": doc_count
            })
            
        # Query chunks with contradictions
        contradictions = 0
        semantic_coll = qdrant.COLLECTIONS["semantic"]
        try:
            res = qdrant.client.count(
                collection_name=semantic_coll,
                count_filter=Filter(
                    must=[
                        FieldCondition(
                            key="contradiction_flag",
                            match=MatchValue(value=True)
                        )
                    ]
                )
            )
            contradictions = res.count
        except Exception as e:
            logger.warning(f"Failed to count contradictions: {e}")
            
        return {
            "collections": collections_info,
            "chunks_with_contradictions": contradictions
        }
    except Exception as e:
        logger.error(f"Failed to get corpus health: {e}")
        return {"error": str(e)}

@router.post("/clear-session/{session_id}")
def clear_session(session_id: str):
    try:
        from agents.conversation_memory import ConversationMemory
        memory = ConversationMemory()
        memory.clear_session(session_id)
        return {"cleared": True, "session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to clear session: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/pending-approvals")
def get_pending_approvals():
    from database.supabase_client import SupabaseManager
    supabase = SupabaseManager()
    if not supabase.client:
        return []
    
    try:
        res = supabase.client.table("repair_queue").select("id, query, failure_class, root_cause, confidence, created_at, status, estimated_papers_affected").eq("status", "pending_approval").execute()
        return res.data
    except Exception as e:
        if "PGRST205" in str(e):
            return []  # Table not created yet
        logger.error(f"Failed to fetch pending approvals: {e}")
        return {"error": str(e)}

@router.post("/approve-repair/{job_id}")
def approve_repair(job_id: str, action: str = "approve"):
    from database.supabase_client import SupabaseManager
    from workers.repair_tasks import rechunk_documents
    import json
    
    supabase = SupabaseManager()
    if not supabase.client:
        return {"error": "Supabase not connected"}
        
    try:
        res = supabase.client.table("repair_queue").select("*").eq("id", job_id).execute()
        if not res.data:
            return {"error": "Job not found"}
            
        job_data = res.data[0]
        
        if action.lower() == "approve":
            supabase.client.table("repair_queue").update({"status": "approved"}).eq("id", job_id).execute()
            
            # Re-queue celery task
            payload_str = job_data.get("payload", "{}")
            payload = payload_str if isinstance(payload_str, dict) else json.loads(payload_str)
            paper_ids = payload.get("paper_ids", [])
            query = job_data.get("query", "unknown")
            root_cause = job_data.get("root_cause", "unknown")
            
            if paper_ids:
                rechunk_documents.delay(paper_ids, query, root_cause, is_approved=True)
                
            return {"status": "approved", "requeued": True}
            
        else:
            supabase.client.table("repair_queue").update({"status": "rejected"}).eq("id", job_id).execute()
            return {"status": "rejected", "requeued": False}
            
    except Exception as e:
        if "PGRST205" in str(e):
            return {"error": "repair_queue table not created yet."}
        logger.error(f"Failed to approve repair: {e}")
        return {"error": str(e)}

@router.get("/repair-history")
def get_repair_history():
    from database.supabase_client import SupabaseManager
    supabase = SupabaseManager()
    if not supabase.client:
        return []
        
    history = []
    try:
        # Fetch completed repairs
        res1 = supabase.client.table("repair_history").select("*").order("created_at", desc=True).limit(20).execute()
        history.extend(res1.data)
    except Exception as e:
        if "PGRST205" not in str(e):
            logger.warning(f"Failed to fetch repair_history: {e}")
            
    try:
        # Fetch pending/rejected from queue
        res2 = supabase.client.table("repair_queue").select("*").in_("status", ["pending_approval", "rejected"]).order("created_at", desc=True).limit(10).execute()
        history.extend(res2.data)
    except Exception as e:
        if "PGRST205" not in str(e):
            logger.warning(f"Failed to fetch repair_queue history: {e}")
            
    return history

@router.get("/benchmark-history")
def get_benchmark_history():
    from database.supabase_client import SupabaseManager
    supabase = SupabaseManager()
    if not supabase.client:
        return []
    
    try:
        # We group manually in python for simplicity
        res = supabase.client.table("benchmark_results").select("run_id, created_at, agent2_passed, confidence, processing_time_ms").order("created_at", desc=True).execute()
        
        runs = {}
        for row in res.data:
            rid = row.get("run_id", "unknown")
            if rid not in runs:
                runs[rid] = {
                    "run_id": rid,
                    "date": row.get("created_at"),
                    "total_questions": 0,
                    "passed": 0,
                    "total_conf": 0.0,
                    "total_time": 0
                }
            runs[rid]["total_questions"] += 1
            if row.get("agent2_passed"):
                runs[rid]["passed"] += 1
            runs[rid]["total_conf"] += row.get("confidence", 0.0)
            runs[rid]["total_time"] += row.get("processing_time_ms", 0)
            
        history = []
        for rid, data in runs.items():
            tq = data["total_questions"]
            history.append({
                "run_id": rid,
                "date": data["date"],
                "total_questions": tq,
                "pass_rate": data["passed"] / max(1, tq),
                "avg_confidence": data["total_conf"] / max(1, tq),
                "avg_time_ms": data["total_time"] / max(1, tq)
            })
            
        # Sort by date desc
        history.sort(key=lambda x: x["date"], reverse=True)
        return history[:12]
    except Exception as e:
        logger.error(f"Benchmark history failed: {e}")
        return []

@router.get("/benchmark-trend")
def get_benchmark_trend():
    history = get_benchmark_history()
    # Reverse to chronological order for charts
    history.reverse()
    
    return {
        "labels": [h["date"].split("T")[0] for h in history],
        "pass_rates": [h["pass_rate"] for h in history],
        "avg_confidence": [h["avg_confidence"] for h in history]
    }

@router.get("/latest-benchmark")
def get_latest_benchmark():
    history = get_benchmark_history()
    if not history:
        return {}
        
    latest = history[0]
    latest["improvement_vs_previous"] = 0.0
    
    if len(history) > 1:
        prev = history[1]
        latest["improvement_vs_previous"] = latest["pass_rate"] - prev["pass_rate"]
        
    return latest

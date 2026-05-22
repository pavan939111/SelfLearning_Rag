import redis
import json
from config import get_config
from utils.logger import get_logger

logger = get_logger(__name__)
config = get_config()

class Agent4BRepair:
    """
    Interface between the internal Agent 3 diagnostics and the external Celery workers.
    Routes Class A (Data) and Class B (Knowledge) failures to async background queues.
    """
    def __init__(self):
        self.logger = logger
        self.config = config
        
    def queue_repair(self, diagnosis, query: str, session_id: str) -> dict:
        self.logger.info(f"Agent 4B analyzing diagnosis: {diagnosis.root_cause}")
        
        try:
            from workers.repair_tasks import log_repair_needed, rechunk_documents, reembed_cluster
            
            root_cause = diagnosis.root_cause.lower()
            
            if "coverage_gap" in root_cause or "knowledge_gap" in root_cause:
                log_repair_needed.delay(
                    session_id, 
                    query, 
                    {
                        "failure_class": getattr(diagnosis, 'failure_class', 'Unknown'), 
                        "root_cause": diagnosis.root_cause, 
                        "confidence": getattr(diagnosis, 'confidence', 0.0)
                    }
                )
                return {"queued": "log_failure", "action": "monitor"}
                
            elif "knowledge_drift" in root_cause:
                log_repair_needed.delay(
                    session_id, 
                    query, 
                    {
                        "failure_class": getattr(diagnosis, 'failure_class', 'Unknown'), 
                        "root_cause": diagnosis.root_cause, 
                        "confidence": getattr(diagnosis, 'confidence', 0.0)
                    }
                )
                return {"queued": "log_failure", "action": "live_fetch_active"}
                
            elif "query_formulation" in root_cause:
                self.logger.warning("Agent 4B received a query_formulation failure. This should have been handled by Agent 4A.")
                return {"queued": None, "action": "none"}
                
            # Class A Data Problem
            else:
                paper_ids = getattr(diagnosis, "paper_ids", []) 
                topic_cluster = getattr(diagnosis, "topic_cluster", "Unknown")
                
                if "chunk" in root_cause:
                    rechunk_documents.delay(paper_ids, query, diagnosis.root_cause)
                    return {"queued": "repair_task", "action": "repairing"}
                    
                elif "embed" in root_cause:
                    reembed_cluster.delay(topic_cluster, diagnosis.root_cause)
                    return {"queued": "repair_task", "action": "repairing"}
                    
                else:
                    log_repair_needed.delay(
                        session_id, 
                        query, 
                        {
                            "failure_class": getattr(diagnosis, 'failure_class', 'Unknown'), 
                            "root_cause": diagnosis.root_cause, 
                            "confidence": getattr(diagnosis, 'confidence', 0.0)
                        }
                    )
                    return {"queued": "log_failure", "action": "monitor"}
                    
        except Exception as e:
            self.logger.error(f"Agent 4B failed to queue repair: {e}")
            return {"queued": None, "action": "error"}

    def get_queue_depth(self) -> dict:
        try:
            from database.redis_client import RedisManager
            r = RedisManager()
            if not r.client:
                return {"high": 0, "medium": 0, "low": 0}
                
            high = r.client.llen("high_priority")
            medium = r.client.llen("medium_priority")
            low = r.client.llen("low_priority")
            
            return {"high": high, "medium": medium, "low": low}
        except Exception as e:
            self.logger.error(f"Failed to get queue depth: {e}")
            return {"high": 0, "medium": 0, "low": 0}

    def get_recent_repairs(self, limit=10) -> list:
        try:
            from database.supabase_client import SupabaseManager
            sb = SupabaseManager()
            if not sb.client:
                return []
                
            res = sb.client.table("repair_history").select("*").order("created_at", desc=True).limit(limit).execute()
            return res.data
        except Exception as e:
            self.logger.error(f"Failed to fetch recent repairs: {e}")
            return []

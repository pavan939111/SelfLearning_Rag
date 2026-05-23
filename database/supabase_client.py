from supabase import create_client, Client
from tenacity import retry, stop_after_attempt, wait_fixed
from config import get_config
from utils.logger import get_logger

config = get_config()
logger = get_logger(__name__, level=config.log_level)

class SupabaseManager:
    def __init__(self):
        try:
            self.client: Client = create_client(config.supabase_url, config.supabase_key)
            logger.info("Initialized Supabase client")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            self.client = None

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def test_connection(self) -> bool:
        """
        Tests connection to Supabase by performing a simple query.
        """
        if not self.client:
            return False
        try:
            # Attempt to list tables or run a simple query. 
            # We'll use a generic query that checks connection.
            self.client.table("_non_existent_table_test_").select("count", count="exact").limit(1).execute()
            # If we reached here without a connection error, it's connected
            logger.info("Supabase: OK - CONNECTED")
            return True
        except Exception as e:
            # If the error is just "table not found", it's still a success for connection
            error_str = str(e).lower()
            success_indicators = ["does not exist", "404", "could not find the table", "pgrst205"]
            if any(indicator in error_str for indicator in success_indicators):
                logger.info("Supabase: OK - CONNECTED")
                return True
            logger.error(f"Supabase: FAIL - {e}")
            return False

    def log_ingestion(self, 
                      paper, 
                      chunks_created: int, 
                      status: str, 
                      error_message: str = ""):
        """Logs a single paper ingestion attempt to Supabase."""
        if not self.client:
            return
        
        try:
            data = {
                "paper_id": paper.paper_id,
                "title": paper.title,
                "topic_cluster": paper.topic_cluster,
                "evidence_level": paper.evidence_level,
                "year": paper.year,
                "ingestion_date": paper.ingestion_date,
                "chunks_created": chunks_created,
                "status": status,
                "error_message": error_message if error_message else None
            }
            self.client.table("ingestion_logs").insert(data).execute()
            logger.debug(f"Logged ingestion for {paper.paper_id} to Supabase")
        except Exception as e:
            logger.warning(f"Failed to log ingestion to Supabase for {paper.paper_id}: {e}")

    def get_ingestion_stats(self) -> dict:
        """Aggregates ingestion metrics from Supabase logs."""
        if not self.client:
            return {}
        
        try:
            # 1. Total Success
            success_res = self.client.table("ingestion_logs").select("id", count="exact").eq("status", "success").execute()
            total_success = success_res.count if success_res.count is not None else 0

            # 2. Total Failed
            failed_res = self.client.table("ingestion_logs").select("id", count="exact").eq("status", "failed").execute()
            total_failed = failed_res.count if failed_res.count is not None else 0

            # 3. By Cluster 
            cluster_res = self.client.table("ingestion_logs").select("topic_cluster").eq("status", "success").execute()
            clusters = [r["topic_cluster"] for r in cluster_res.data]
            by_cluster = {}
            for c in clusters:
                by_cluster[c] = by_cluster.get(c, 0) + 1

            # 4. Latest Date
            date_res = self.client.table("ingestion_logs").select("ingestion_date").order("ingestion_date", desc=True).limit(1).execute()
            latest_date = date_res.data[0]["ingestion_date"] if date_res.data else "None"

            return {
                "total_ingested": total_success,
                "total_failed": total_failed,
                "by_cluster": by_cluster,
                "latest_date": latest_date
            }
        except Exception as e:
            logger.error(f"Failed to get ingestion stats from Supabase: {e}")
            return {}

    def get_user_profile(self, user_id: str) -> dict | None:
        if not self.client or not user_id:
            return None
        try:
            response = self.client.table("user_profiles").select("*").eq("user_id", user_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.warning(f"Failed to fetch user profile for {user_id}: {e}")
            return None

    def update_user_profile(self, user_id: str, query: str, topic_cluster: str, rating: int = 0) -> None:
        if not self.client or not user_id:
            return
            
        try:
            profile = self.get_user_profile(user_id)
            
            if not profile:
                # Create new
                clusters = topic_cluster if topic_cluster else ""
                self.client.table("user_profiles").insert({
                    "user_id": user_id,
                    "preferred_clusters": clusters,
                    "query_history_count": 1,
                    "positive_feedback_count": 1 if rating > 0 else 0,
                    "negative_feedback_count": 1 if rating < 0 else 0
                }).execute()
            else:
                # Update existing
                clusters = profile.get("preferred_clusters", "")
                if topic_cluster:
                    clusters = f"{clusters},{topic_cluster}" if clusters else topic_cluster
                    
                updates = {
                    "query_history_count": profile.get("query_history_count", 0) + 1,
                    "preferred_clusters": clusters,
                    "last_active": "now()"
                }
                
                if rating > 0:
                    updates["positive_feedback_count"] = profile.get("positive_feedback_count", 0) + 1
                elif rating < 0:
                    updates["negative_feedback_count"] = profile.get("negative_feedback_count", 0) + 1
                    
                self.client.table("user_profiles").update(updates).eq("user_id", user_id).execute()
                
        except Exception as e:
            logger.warning(f"Failed to update user profile for {user_id}: {e}")

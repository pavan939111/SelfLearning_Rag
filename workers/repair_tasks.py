import time
from dataclasses import dataclass
from typing import List
import json
from datetime import datetime

from workers.celery_app import celery_app
from utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class RepairJob:
    job_id: str
    paper_ids: List[str]
    repair_type: str
    root_cause: str
    priority: str
    query_that_failed: str
    created_at: str

def _log_repair_history(repair_type: str, paper_ids: str, root_cause: str, chunks_affected: int, success_count: int, error_count: int, duration_seconds: float):
    """Helper to log the final result of a background repair job to Supabase."""
    try:
        from database.supabase_client import SupabaseManager
        sb = SupabaseManager()
        if sb.client:
            sb.client.table("repair_history").insert({
                "repair_type": repair_type,
                "paper_ids": paper_ids,
                "root_cause": root_cause,
                "chunks_affected": chunks_affected,
                "success_count": success_count,
                "error_count": error_count,
                "duration_seconds": duration_seconds
            }).execute()
    except Exception as e:
        logger.error(f"Failed to log to repair_history: {e}")


@celery_app.task(name="repair.rechunk", queue="high_priority", bind=True)
def rechunk_documents(self, paper_ids: list, query_that_failed: str, root_cause: str, is_approved: bool = False):
    logger.info(f"Task repair.rechunk started for {len(paper_ids)} papers.")
    
    count = len(paper_ids)
    if count > 50 and not is_approved:
        logger.warning(f"ADMIN APPROVAL REQUIRED: rechunk affecting {count} papers")
        try:
            from database.supabase_client import SupabaseManager
            sb = SupabaseManager()
            job_id = self.request.id or "manual-" + str(time.time())
            if sb.client:
                sb.client.table("repair_queue").insert({
                    "id": job_id,
                    "session_id": "auto-repair",
                    "query": query_that_failed,
                    "failure_class": "A",
                    "root_cause": root_cause,
                    "confidence": 1.0,
                    "status": "pending_approval",
                    "estimated_papers_affected": count,
                    "payload": {"paper_ids": paper_ids, "query": query_that_failed, "root_cause": root_cause}
                }).execute()
        except Exception as e:
            if "PGRST205" not in str(e):
                logger.error(f"Failed to queue pending approval: {e}")
        return {"status": "pending_approval", "job_id": getattr(self.request, "id", "unknown")}
        
    start_time = time.time()
    success_count = 0
    error_count = 0
    chunks_affected = 0
    
    try:
        from database.qdrant_client import QdrantManager
        from ingestion.chunker import HierarchicalChunker
        from ingestion.embedder import BiomedicalEmbedder
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        qdrant = QdrantManager()
        chunker = HierarchicalChunker()
        embedder = BiomedicalEmbedder()
        
        if not qdrant.client:
            raise Exception("Qdrant client not connected")
            
        dimension = embedder.dimension if hasattr(embedder, 'dimension') else 768
        qdrant.create_staging_collections(dimension, recreate=True)
            
        for pid in paper_ids:
            try:
                # 1. Load existing chunks from Qdrant (using proposition text as source truth)
                scroll_filter = Filter(
                    must=[FieldCondition(key="paper_id", match=MatchValue(value=pid))]
                )
                
                records, _ = qdrant.client.scroll(
                    collection_name=qdrant.COLLECTIONS["proposition"],
                    scroll_filter=scroll_filter,
                    limit=10000,
                    with_payload=True,
                    with_vectors=False
                )
                
                if not records:
                    error_count += 1
                    continue
                    
                # Sort by chunk_index to retain correct paragraph order
                records_sorted = sorted(records, key=lambda r: r.payload.get("chunk_index", 0))
                full_text = " ".join([r.payload.get("text", "") for r in records_sorted])
                
                # Retain metadata
                first_payload = records_sorted[0].payload
                topic_cluster = first_payload.get("topic_cluster", "Unknown")
                year = first_payload.get("year", 0)
                evidence_level = first_payload.get("evidence_level", "Unknown")
                
                # 2. Delete existing section and semantic chunks
                for level in ["section", "semantic"]:
                    qdrant.client.delete(
                        collection_name=qdrant.COLLECTIONS[level],
                        points_selector=scroll_filter
                    )
                    
                # 3. Re-run Hierarchical Chunker
                class DummyPaper:
                    def __init__(self, paper_id, body_text, topic_cluster, year, evidence_level):
                        self.paper_id = paper_id
                        self.title = f"Repair Reconstructed: {paper_id}"
                        self.abstract = ""
                        self.body_text = body_text
                        self.topic_cluster = topic_cluster
                        self.year = year
                        self.evidence_level = evidence_level
                        self.ingestion_date = datetime.now().isoformat()
                        
                paper = DummyPaper(pid, full_text, topic_cluster, year, evidence_level)
                new_chunks_dict = chunker.chunk_paper(paper)
                
                # Filter to only insert section and semantic (propositions remain unchanged)
                chunks_to_insert = new_chunks_dict.get("sections", []) + new_chunks_dict.get("semantic", [])
                chunks_affected += len(chunks_to_insert)
                
                # 4. Re-embed and Insert
                texts = [c.text for c in chunks_to_insert]
                if texts:
                    embeddings = embedder.embed_batch(texts)
                    chunk_embeddings = list(zip(chunks_to_insert, embeddings))
                    
                    section_ce = [ce for ce in chunk_embeddings if getattr(ce[0].level, "value", ce[0].level) == "section"]
                    semantic_ce = [ce for ce in chunk_embeddings if getattr(ce[0].level, "value", ce[0].level) == "semantic"]
                    
                    if section_ce:
                        qdrant.insert_chunks(section_ce, "section", is_staging=True)
                    if semantic_ce:
                        qdrant.insert_chunks(semantic_ce, "semantic", is_staging=True)
                        
                success_count += 1
            except Exception as e:
                logger.error(f"Error rechunking paper {pid}: {e}")
                error_count += 1
                
        # 5. Staging Validation & Promotion
        if success_count > 0:
            # We assume topic_cluster is available from the first paper processed. 
            # If not, default to "general medical context".
            tc = topic_cluster if 'topic_cluster' in locals() else "general medical context"
            test_queries = [
                query_that_failed,
                f"What are the main findings of this research regarding {tc}?",
                f"general overview of {tc}"
            ]
            val_res = qdrant.validate_staging("semantic", test_queries)
            
            if val_res["passed"]:
                logger.info("Staging validation PASSED. Promoting to production.")
                qdrant.promote_staging_to_production("section")
                qdrant.promote_staging_to_production("semantic")
            else:
                error_count += success_count
                success_count = 0
                logger.error(f"Staging validation FAILED: {val_res['reason']}. Changes not promoted.")
                qdrant.create_staging_collections(dimension, recreate=True) # Clears staging
                
                # Insert to repair_queue with status validation_failed
                try:
                    from database.supabase_client import SupabaseManager
                    sb = SupabaseManager()
                    if sb.client:
                        job_id = getattr(self.request, "id", f"manual-{int(time.time())}")
                        sb.client.table("repair_queue").insert({
                            "id": job_id,
                            "session_id": "auto-repair",
                            "query": query_that_failed,
                            "failure_class": "A",
                            "root_cause": root_cause,
                            "confidence": val_res.get("avg_score", 0.0),
                            "status": "validation_failed",
                            "estimated_papers_affected": chunks_affected
                        }).execute()
                except Exception as e:
                    if "PGRST205" not in str(e):
                        logger.error(f"Failed to log validation_failed to repair_queue: {e}")
                
        duration = time.time() - start_time
        _log_repair_history("rechunk", json.dumps(paper_ids), root_cause, chunks_affected, success_count, error_count, duration)
        logger.info(f"Task repair.rechunk completed successfully in {duration:.2f}s")
        return {"success_count": success_count, "error_count": error_count}
        
    except Exception as e:
        logger.error(f"Task repair.rechunk crashed: {e}")
        return {"success_count": success_count, "error_count": error_count, "error": str(e)}


@celery_app.task(name="repair.reembed", queue="high_priority")
def reembed_cluster(topic_cluster: str, root_cause: str):
    logger.info(f"Task repair.reembed started for cluster: {topic_cluster}")
    start_time = time.time()
    chunks_reembedded = 0
    
    try:
        from database.qdrant_client import QdrantManager
        from ingestion.embedder import BiomedicalEmbedder
        from qdrant_client.models import Filter, FieldCondition, MatchValue, PointStruct
        
        qdrant = QdrantManager()
        embedder = BiomedicalEmbedder()
        
        if not qdrant.client:
            raise Exception("Qdrant client not connected")
            
        scroll_filter = Filter(
            must=[FieldCondition(key="topic_cluster", match=MatchValue(value=topic_cluster))]
        )
        
        offset = None
        while True:
            records, offset = qdrant.client.scroll(
                collection_name=qdrant.COLLECTIONS["semantic"],
                scroll_filter=scroll_filter,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            
            if not records:
                break
                
            texts = [r.payload.get("text", "") for r in records]
            embeddings = embedder.embed_batch(texts)
            
            points = []
            for r, emb in zip(records, embeddings):
                points.append(PointStruct(id=r.id, vector=emb, payload=r.payload))
                
            if points:
                qdrant.client.upsert(collection_name=qdrant.COLLECTIONS["semantic"], points=points)
                chunks_reembedded += len(points)
                
            if offset is None:
                break
                
        duration = time.time() - start_time
        _log_repair_history("reembed", topic_cluster, root_cause, chunks_reembedded, chunks_reembedded, 0, duration)
        logger.info(f"Task repair.reembed completed in {duration:.2f}s")
        return chunks_reembedded
        
    except Exception as e:
        logger.error(f"Task repair.reembed crashed: {e}")
        return chunks_reembedded


@celery_app.task(name="repair.metadata", queue="medium_priority")
def fix_metadata(paper_ids: list, field_updates: dict):
    logger.info(f"Task repair.metadata started for {len(paper_ids)} papers.")
    start_time = time.time()
    chunks_updated = 0
    
    try:
        from database.qdrant_client import QdrantManager
        from qdrant_client.models import Filter, FieldCondition, MatchAny
        
        qdrant = QdrantManager()
        if not qdrant.client:
            raise Exception("Qdrant client not connected")
            
        qdrant_filter = Filter(
            must=[FieldCondition(key="paper_id", match=MatchAny(any=paper_ids))]
        )
        
        for level in ['document', 'section', 'semantic', 'proposition']:
            collection_name = qdrant.COLLECTIONS[level]
            try:
                # Count points first for logging
                count_res = qdrant.client.count(collection_name=collection_name, count_filter=qdrant_filter)
                chunks_updated += count_res.count
                
                # Apply payload update
                qdrant.client.set_payload(
                    collection_name=collection_name,
                    payload=field_updates,
                    points_selector=qdrant_filter
                )
            except Exception as e:
                logger.error(f"Failed to update metadata in {collection_name}: {e}")
                
        duration = time.time() - start_time
        _log_repair_history("metadata", json.dumps(paper_ids), "Metadata Fix", chunks_updated, chunks_updated, 0, duration)
        logger.info(f"Task repair.metadata completed in {duration:.2f}s")
        return chunks_updated
        
    except Exception as e:
        logger.error(f"Task repair.metadata crashed: {e}")
        return chunks_updated


@celery_app.task(name="analysis.log_failure", queue="low_priority")
def log_repair_needed(session_id: str, query: str, diagnosis_dict: dict):
    logger.info(f"Task analysis.log_failure started for session {session_id}")
    
    try:
        from database.supabase_client import SupabaseManager
        sb = SupabaseManager()
        if sb.client:
            sb.client.table("repair_queue").insert({
                "session_id": session_id,
                "query": query,
                "failure_class": diagnosis_dict.get("failure_class", ""),
                "root_cause": diagnosis_dict.get("root_cause", ""),
                "confidence": diagnosis_dict.get("confidence", 0.0),
                "status": "pending"
            }).execute()
            logger.info("Successfully logged to repair_queue.")
    except Exception as e:
        logger.error(f"Task analysis.log_failure crashed: {e}")


@celery_app.task(name="ingest.live_fetch_papers", queue="medium_priority")
def ingest_live_fetch_papers(paper_ids: list[str], query: str) -> dict:
    """
    Asynchronously fetches PubMed metadata for paper_ids, 
    verifies if they should be ingested, and runs the hierarchical indexing pipeline.
    """
    logger.info(f"Task ingest.live_fetch_papers started for PMIDs: {paper_ids}")
    
    try:
        from agents.live_fetch_ingester import LiveFetchIngester
        import requests
        import xmltodict
        
        ingester = LiveFetchIngester()
        ingested = 0
        skipped = 0
        failed = 0
        
        # Read NCBI key from config
        ncbi_api_key = ingester.chunker.config.ncbi_api_key if hasattr(ingester.chunker, "config") else ""
        
        for pmid in paper_ids:
            try:
                # Re-fetch from PubMed efetch API
                efetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
                fetch_params = {
                    "db": "pubmed",
                    "id": pmid,
                    "rettype": "abstract",
                    "retmode": "xml"
                }
                if ncbi_api_key:
                    fetch_params["api_key"] = ncbi_api_key
                    
                r_fetch = requests.get(efetch_url, params=fetch_params, timeout=10.0)
                r_fetch.raise_for_status()
                
                xml_data = xmltodict.parse(r_fetch.text)
                article_set = xml_data.get("PubmedArticleSet", {}) or {}
                article = article_set.get("PubmedArticle", {})
                if isinstance(article, list):
                    article = article[0]
                    
                medline = article.get("MedlineCitation", {}) or {}
                article_data = medline.get("Article", {}) or {}
                
                title_obj = article_data.get("ArticleTitle", "")
                if isinstance(title_obj, dict):
                    title = title_obj.get("#text", str(title_obj))
                elif isinstance(title_obj, list):
                    title = " ".join([t.get("#text", str(t)) if isinstance(t, dict) else str(t) for t in title_obj])
                else:
                    title = str(title_obj)
                    
                abstract_data = article_data.get("Abstract", {}) or {}
                abstract_text = ""
                abstract_text_element = abstract_data.get("AbstractText", "")
                if isinstance(abstract_text_element, list):
                    abstract_text = " ".join([t.get("#text", str(t)) if isinstance(t, dict) else str(t) for t in abstract_text_element])
                elif isinstance(abstract_text_element, dict):
                    abstract_text = abstract_text_element.get("#text", str(abstract_text_element))
                else:
                    abstract_text = str(abstract_text_element)
                    
                pub_date = article_data.get("Journal", {}).get("JournalIssue", {}).get("PubDate", {}) or {}
                year = 2022  # fallback
                year_val = pub_date.get("Year", "")
                if year_val:
                    try:
                        year = int(year_val)
                    except ValueError:
                        pass
                        
                journal_name = article_data.get("Journal", {}).get("Title", "")
                
                # Detect topic cluster from query
                q_lower = query.lower()
                if any(kw in q_lower for kw in ["pd-1", "pd-l1", "pembrolizumab", "nivolumab", "immunotherapy", "checkpoint", "car-t"]):
                    topic_cluster = "immunotherapy"
                elif any(kw in q_lower for kw in ["drug interaction", "cytochrome", "p450", "pharmacokinetics", "adverse"]):
                    topic_cluster = "drug_interactions"
                elif any(kw in q_lower for kw in ["gene", "genome", "crispr", "snp", "sequencing", "genomics"]):
                    topic_cluster = "genomics"
                else:
                    topic_cluster = "immunotherapy"
                    
                chunk_dict = {
                    "paper_id": pmid,
                    "title": title,
                    "text": abstract_text,
                    "year": year,
                    "journal": journal_name,
                    "topic_cluster": topic_cluster,
                    "freshness_score": 1.0,
                    "contradiction_flag": False
                }
                
                if ingester.should_ingest(chunk_dict):
                    success = ingester.ingest_single(chunk_dict)
                    if success:
                        ingested += 1
                    else:
                        failed += 1
                else:
                    skipped += 1
                    
            except Exception as paper_err:
                logger.error(f"Error ingesting paper {pmid}: {paper_err}")
                failed += 1
                
        # Log to Supabase ingestion_logs if possible
        try:
            if ingester.supabase.client:
                ingester.supabase.client.table("ingestion_logs").insert({
                    "batch_id": f"live_fetch_{int(time.time())}",
                    "ingested_count": ingested,
                    "skipped_count": skipped,
                    "failed_count": failed,
                    "status": "completed",
                    "notes": f"Live fetch queue triggered by query: {query[:100]}"
                }).execute()
        except Exception as log_err:
            logger.warning(f"Could not insert into ingestion_logs: {log_err}")
            
        # Log to repair_history helper
        try:
            _log_repair_history(
                repair_type="live_ingestion",
                paper_ids=json.dumps(paper_ids),
                root_cause="knowledge_drift_live_fetch",
                chunks_affected=ingested * 3,
                success_count=ingested,
                error_count=failed,
                duration_seconds=0.0
            )
        except Exception:
            pass
            
        return {"ingested": ingested, "skipped": skipped, "failed": failed}
        
    except Exception as e:
        logger.error(f"Task ingest.live_fetch_papers failed: {e}")
        return {"ingested": 0, "skipped": 0, "failed": len(paper_ids)}

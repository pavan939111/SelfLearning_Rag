import json
import os
import requests
import xmltodict
from datetime import datetime
from ingestion.chunker import HierarchicalChunker
from ingestion.embedder import BiomedicalEmbedder
from database.qdrant_client import QdrantManager
from database.supabase_client import SupabaseManager
from utils.logger import get_logger
from ingestion.fetcher import PaperRecord

class LiveFetchIngester:
    """
    Handles downstream background ingestion of papers retrieved dynamically from PubMed.
    Normalizes PubMed articles into Self-Learning and Self-Healing RAG's 3-level vector hierarchy (excluding propositions)
    and indexes them permanently.
    """
    def __init__(self):
        self.chunker = HierarchicalChunker()
        self.embedder = BiomedicalEmbedder()
        self.qdrant = QdrantManager()
        self.supabase = SupabaseManager()
        self.logger = get_logger(__name__)

    def check_already_ingested(self, paper_id: str) -> bool:
        """Searches Qdrant's document collection to check if the paper exists."""
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            collection_name = self.qdrant.COLLECTIONS["document"]
            
            res, _ = self.qdrant.client.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="paper_id",
                            match=MatchValue(value=paper_id)
                        )
                    ]
                ),
                limit=1,
                with_payload=True
            )
            return len(res) > 0
        except Exception as e:
            self.logger.error(f"Failed to check if paper {paper_id} is ingested: {e}")
            return False

    def should_ingest(self, chunk_dict: dict) -> bool:
        """Returns True if the abstract is robust, fresh, and verified by Agent 5A."""
        try:
            paper_id = chunk_dict.get('paper_id', '')
            
            # Keep check_already_ingested check to prevent double indexing
            if self.check_already_ingested(paper_id):
                self.logger.info(f"Skipping ingestion for paper {paper_id}: already present in document collection")
                return False
                
            from agents.agent5a_verifier import Agent5AVerifier
            verifier = Agent5AVerifier()
            res = verifier.verify(chunk_dict)
            self.logger.info(f"Agent 5A verification for paper {paper_id}: passed={res.passed}, reason='{res.reason}'")
            
            # Update chunk_dict metadata based on ingestion instructions
            if res.passed:
                chunk_dict["topic_cluster"] = res.ingestion_instructions.get("topic_cluster", chunk_dict.get("topic_cluster"))
                chunk_dict["evidence_level"] = res.ingestion_instructions.get("evidence_level", "other")
                chunk_dict["priority"] = res.ingestion_instructions.get("priority", "low")
                if res.ingestion_instructions.get("contradiction_suspected", False):
                    chunk_dict["contradiction_flag"] = True
            
            return res.passed
        except Exception as e:
            self.logger.error(f"Error checking if paper should be ingested: {e}")
            return False

    def ingest_single(self, chunk_dict: dict) -> bool:
        """Performs hierarchical chunking, embedding generation, and Qdrant storage."""
        self.logger.info(f"Beginning single live paper ingestion for PMID: {chunk_dict.get('paper_id')}")
        
        paper_id = chunk_dict['paper_id']
        title = chunk_dict.get('title', 'Unknown')
        abstract = chunk_dict['text']
        year = chunk_dict['year']
        journal = chunk_dict.get('journal', 'Unknown')
        topic_cluster = chunk_dict['topic_cluster']
        
        paper_record = PaperRecord(
            paper_id=paper_id,
            title=title,
            abstract=abstract,
            year=year,
            journal=journal,
            topic_cluster=topic_cluster,
            authors=['Unknown'],
            doi='',
            evidence_level=chunk_dict.get('evidence_level', 'other'),
            ingestion_date=datetime.now().date().isoformat(),
            freshness_score=1.0,
            contradiction_flag=chunk_dict.get('contradiction_flag', False),
            has_full_text=False
        )
        
        try:
            # Chunking
            result = self.chunker.chunk_paper(paper_record)
            
            # Count total chunks across document, sections, semantic levels
            total_chunks = 0
            
            # Skip propositions as requested: "Skip proposition level - too slow for background ingestion"
            for level in ["document", "section", "semantic"]:
                key = "sections" if level == "section" else level
                chunks = result.get(key, [])
                if not chunks:
                    continue
                    
                # Embed chunks
                chunk_embeddings = self.embedder.embed_chunks(chunks)
                # Insert chunks (which acts as upsert)
                inserted = self.qdrant.insert_chunks(chunk_embeddings, level)
                total_chunks += inserted
                
            # Log successful ingestion to Supabase
            self.supabase.log_ingestion(paper_record, total_chunks, "success")
            
            self.logger.info(f"Successfully ingested paper {paper_id} with {total_chunks} total chunks indexed.")
            
            # Invalidate semantic cache for this topic cluster to prevent stale cache entries
            try:
                from agents.cache_manager import CacheManager
                cache = CacheManager()
                cache.invalidate(paper_record.topic_cluster)
            except Exception as cache_err:
                self.logger.warning(f"Failed to invalidate cache after ingesting paper {paper_id}: {cache_err}")
                
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to ingest paper {paper_id}: {e}")
            self.supabase.log_ingestion(paper_record, 0, "failed", str(e))
            return False

    def ingest_from_log(self, diagnosis_dict: dict) -> dict:
        """Fetches fresh abstracts from PubMed and triggers sequential local pipeline ingests."""
        self.logger.info(f"Pick up background ingestion from log: {diagnosis_dict}")
        try:
            paper_ids = diagnosis_dict.get("paper_ids", [])
            ingested_count = 0
            failed_count = 0
            
            # Read NCBI key from config
            ncbi_api_key = self.chunker.config.ncbi_api_key if hasattr(self.chunker, "config") else ""
            
            for pmid in paper_ids:
                try:
                    # efetch abstract
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
                    
                    # Navigate xmltodict
                    article_set = xml_data.get("PubmedArticleSet", {}) or {}
                    article = article_set.get("PubmedArticle", {})
                    
                    # In case multiple or list returned
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
                    
                    # Simple default topic cluster based on keywords
                    title_and_abstract = (title + " " + abstract_text).lower()
                    if any(kw in title_and_abstract for kw in ["pd-1", "pd-l1", "pembrolizumab", "nivolumab", "immunotherapy", "checkpoint", "car-t"]):
                        topic_cluster = "immunotherapy"
                    elif any(kw in title_and_abstract for kw in ["drug interaction", "cytochrome", "p450", "pharmacokinetics", "adverse"]):
                        topic_cluster = "drug_interactions"
                    elif any(kw in title_and_abstract for kw in ["gene", "genome", "crispr", "snp", "sequencing", "genomics"]):
                        topic_cluster = "genomics"
                    else:
                        topic_cluster = "immunotherapy"
                        
                    chunk_dict = {
                        "paper_id": pmid,
                        "title": title,
                        "text": abstract_text,
                        "year": year,
                        "journal": journal_name,
                        "topic_cluster": topic_cluster
                    }
                    
                    if self.should_ingest(chunk_dict):
                        success = self.ingest_single(chunk_dict)
                        if success:
                            ingested_count += 1
                        else:
                            failed_count += 1
                    else:
                        failed_count += 1
                        
                except Exception as paper_err:
                    self.logger.error(f"Failed to fetch or ingest single PMID {pmid} from log: {paper_err}")
                    failed_count += 1
                    
            return {"ingested": ingested_count, "failed": failed_count}
        except Exception as e:
            self.logger.error(f"Failed in ingest_from_log: {e}")
            return {"ingested": 0, "failed": 0}

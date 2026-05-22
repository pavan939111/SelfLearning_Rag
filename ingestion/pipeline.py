import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from ingestion.fetcher import PubMedFetcher, PaperRecord, load_papers
from ingestion.chunker import HierarchicalChunker
from ingestion.embedder import BiomedicalEmbedder
from database.qdrant_client import QdrantManager
from database.supabase_client import SupabaseManager
from utils.logger import get_logger

@dataclass
class IngestionStats:
    total_papers: int = 0
    successful_papers: int = 0
    failed_papers: int = 0
    chunks_document: int = 0
    chunks_section: int = 0
    chunks_semantic: int = 0
    chunks_proposition: int = 0
    inserted_document: int = 0
    inserted_section: int = 0
    inserted_semantic: int = 0
    inserted_proposition: int = 0
    start_time: float = field(default_factory=time.time)
    duration_seconds: float = 0.0

    def to_dict(self):
        return {
            "total_papers": self.total_papers,
            "successful_papers": self.successful_papers,
            "failed_papers": self.failed_papers,
            "chunks": {
                "document": self.chunks_document,
                "section": self.chunks_section,
                "semantic": self.chunks_semantic,
                "proposition": self.chunks_proposition,
            },
            "inserted": {
                "document": self.inserted_document,
                "section": self.inserted_section,
                "semantic": self.inserted_semantic,
                "proposition": self.inserted_proposition,
            },
            "duration_seconds": round(self.duration_seconds, 2),
            "papers_per_hour": round((self.successful_papers / (self.duration_seconds / 3600)), 2) if self.duration_seconds > 0 else 0,
            "timestamp": datetime.now().isoformat()
        }

class IngestionPipeline:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.fetcher = PubMedFetcher()
        self.chunker = HierarchicalChunker()
        self.embedder = BiomedicalEmbedder()
        self.qdrant = QdrantManager()
        self.supabase = SupabaseManager()

    def setup_collections(self, recreate: bool = False):
        """Initializes Qdrant collections."""
        dim = self.embedder.dimension
        self.logger.info(f"Setting up Qdrant collections with dimension {dim}")
        return self.qdrant.create_collections(dimension=dim, recreate=recreate)

    def process_paper(self, paper: PaperRecord, stats: IngestionStats) -> bool:
        """Processes a single paper: chunk -> embed -> insert."""
        try:
            self.logger.info(f"Processing paper: {paper.paper_id}")
            
            # BEFORE chunking: Run Agent 5A Verification
            from agents.agent5a_verifier import Agent5AVerifier
            verifier = Agent5AVerifier()
            res = verifier.verify(paper)
            if not res.passed:
                self.logger.warning(f"Paper {paper.paper_id} failed verification: {res.reason} (failed check: '{res.failed_check}')")
                stats.failed_papers += 1
                # Log failed ingestion to Supabase
                self.supabase.log_ingestion(paper, 0, "failed", f"Rejected by Agent 5A: {res.reason}")
                return False
                
            # Apply ingestion instructions to metadata
            paper.topic_cluster = res.ingestion_instructions.get("topic_cluster", paper.topic_cluster)
            paper.evidence_level = res.ingestion_instructions.get("evidence_level", paper.evidence_level)
            if res.ingestion_instructions.get("contradiction_suspected", False):
                paper.contradiction_flag = True
            
            # 1. Chunking
            result = self.chunker.chunk_paper(paper)
            
            # Update stats for chunks
            stats.chunks_document += len(result.get("document", []))
            stats.chunks_section += len(result.get("sections", []))
            stats.chunks_semantic += len(result.get("semantic", []))
            stats.chunks_proposition += len(result.get("propositions", []))

            # 2. Embedding and Insertion for each level
            for level in ["document", "section", "semantic", "proposition"]:
                key = "sections" if level == "section" else "propositions" if level == "proposition" else level
                chunks = result.get(key, [])
                
                if not chunks:
                    continue
                    
                chunk_embeddings = self.embedder.embed_chunks(chunks)
                inserted = self.qdrant.insert_chunks(chunk_embeddings, level)
                
                if level == "document": stats.inserted_document += inserted
                elif level == "section": stats.inserted_section += inserted
                elif level == "semantic": stats.inserted_semantic += inserted
                elif level == "proposition": stats.inserted_proposition += inserted

            stats.successful_papers += 1
            
            # Log successful ingestion to Supabase
            total_chunks = len(result.get("document", [])) + \
                          len(result.get("sections", [])) + \
                          len(result.get("semantic", [])) + \
                          len(result.get("propositions", []))
            self.supabase.log_ingestion(paper, total_chunks, "success")
            
            # Populate Neo4j with paper node
            try:
                from database.neo4j_client import Neo4jManager
                neo4j = Neo4jManager()
                neo4j.create_paper_node(paper)
            except Exception as e:
                self.logger.warning(f"Neo4j node creation failed: {e}")
                # Never fail ingestion due to Neo4j issues
                
            return True

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Failed to process paper {paper.paper_id}: {error_msg}")
            stats.failed_papers += 1
            
            # Log failed ingestion to Supabase
            self.supabase.log_ingestion(paper, 0, "failed", error_msg)
            
            return False

    def run(self, 
            papers_per_cluster: int = 50,
            papers_file: str = None,
            checkpoint_file: str = "ingestion_checkpoint.json",
            log_every: int = 5) -> IngestionStats:
        """Runs the full ingestion pipeline."""
        stats = IngestionStats()
        
        # Ensure logs directory exists
        os.makedirs("logs", exist_ok=True)
        
        # Setup collections
        if not self.setup_collections():
            self.logger.error("Failed to setup Qdrant collections. Aborting.")
            return stats

        # Load papers
        papers = []
        if papers_file and os.path.exists(papers_file):
            self.logger.info(f"Loading papers from file: {papers_file}")
            papers = load_papers(papers_file)
        else:
            self.logger.info(f"Fetching {papers_per_cluster} papers per cluster...")
            papers = self.fetcher.fetch_all_clusters(papers_per_cluster=papers_per_cluster)

        stats.total_papers = len(papers)
        self.logger.info(f"Starting pipeline for {stats.total_papers} papers")

        # Load checkpoint
        processed_ids = []
        if os.path.exists(checkpoint_file):
            try:
                with open(checkpoint_file, "r") as f:
                    processed_ids = json.load(f)
                self.logger.info(f"Resuming from checkpoint: {len(processed_ids)} papers already processed")
            except Exception as e:
                self.logger.warning(f"Failed to load checkpoint: {e}. Starting fresh.")
                processed_ids = []

        # Filter out already processed papers
        papers_to_process = [p for p in papers if p.paper_id not in processed_ids]
        self.logger.info(f"Need to process {len(papers_to_process)} remaining papers")

        try:
            for i, paper in enumerate(papers_to_process):
                # Process paper
                self.process_paper(paper, stats)
                processed_ids.append(paper.paper_id)

                # Save checkpoint every 10 papers
                if (i + 1) % 10 == 0:
                    with open(checkpoint_file, "w") as f:
                        json.dump(processed_ids, f)
                    self.logger.info(f"Checkpoint saved at {i+1} papers processed this session")

                # Log progress
                if (i + 1) % log_every == 0 or (i + 1) == len(papers_to_process):
                    elapsed = time.time() - stats.start_time
                    rate = (i + 1) / (elapsed / 60) if elapsed > 0 else 0 # papers per minute
                    remaining = len(papers_to_process) - (i + 1)
                    eta_min = remaining / rate if rate > 0 else 0
                    self.logger.info(
                        f"Progress: {i+1}/{len(papers_to_process)} | "
                        f"Rate: {rate:.2f} papers/min | "
                        f"ETA: {eta_min:.2f} min"
                    )

        finally:
            # Final stats calculation
            stats.duration_seconds = time.time() - stats.start_time
            
            # Save final stats
            stats_dict = stats.to_dict()
            with open("logs/ingestion_stats.json", "w") as f:
                json.dump(stats_dict, f, indent=4)
            self.logger.info(f"Final stats saved to logs/ingestion_stats.json")
            
            # Cleanup checkpoint if finished
            if len(processed_ids) >= len(papers) and len(papers) > 0:
                if os.path.exists(checkpoint_file):
                    os.remove(checkpoint_file)
                self.logger.info("Ingestion complete. Checkpoint cleared.")

        return stats

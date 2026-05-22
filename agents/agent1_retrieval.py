import json
from google import genai
import numpy as np
from dataclasses import dataclass
from config import get_config
from utils.logger import get_logger
from utils.llm_utils import get_gemini_key

@dataclass
class SufficiencyResult:
    is_sufficient: bool
    reason: str
    suggestion: str

@dataclass
class FilterConfig:
    must_conditions: list[dict]
    should_conditions: list[dict]
    min_year: int | None
    topic_cluster: str | None
    requires_fresh: bool

@dataclass
class RetrievalResult:
    chunk_id: str
    paper_id: str
    text: str
    score: float
    level: str
    section_type: str
    topic_cluster: str
    year: int
    freshness_score: float
    contradiction_flag: bool
    keyword_matches: int

@dataclass
class QueryClassification:
    query: str
    query_type: str
    main_topics: list[str]
    requires_recent: bool
    entities: list[str]

    def to_dict(self):
        return {
            "query": self.query,
            "query_type": self.query_type,
            "main_topics": self.main_topics,
            "requires_recent": self.requires_recent,
            "entities": self.entities
        }

@dataclass
class Agent1Result:
    query: str
    classification: QueryClassification
    results: list[RetrievalResult]
    sufficiency: SufficiencyResult
    filter_was_relaxed: bool
    query_was_rewritten: bool
    rewritten_query: str

class QueryClassifier:
    """
    Agent component that classifies user queries into retrieval strategies
    and extracts key medical entities.
    """
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger(__name__)
        # Keys are configured per-call for round-robin rotation

    def classify(self, query: str) -> QueryClassification:
        """
        Uses Gemini Flash to classify the query type and extract entities.
        
        Args:
            query: The raw user query string.
            
        Returns:
            QueryClassification object with type and metadata.
        """
        self.logger.info(f"Classifying query: {query[:50]}...")
        
        # Configure Gemini using round-robin key management
        client = genai.Client(api_key=get_gemini_key())
        
        prompt = (
            f"Analyze this biomedical query and provide a structured classification.\n"
            f"Query: \"{query}\"\n\n"
            f"Return a JSON object with exactly these keys:\n"
            f"- query_type: one of [simple_factual, multi_hop, comparative, temporal, exploratory]\n"
            f"- main_topics: list of key medical/biological terms (max 5)\n"
            f"- requires_recent: boolean, True if asking for current/latest/recent info\n"
            f"- entities: list of specific drug names, genes, diseases mentioned\n\n"
            f"Definitions:\n"
            f"- simple_factual: Direct lookup of a single concept.\n"
            f"- multi_hop: Connects multiple concepts or mechanisms.\n"
            f"- comparative: Comparing drugs, therapies, or outcomes.\n"
            f"- temporal: Asking about the latest state-of-the-art or current trends.\n"
            f"- exploratory: Open-ended search for emerging patterns.\n\n"
            f"Return ONLY the JSON block."
        )

        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
            text = response.text.strip()
            
            # Clean JSON from markdown if necessary
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            data = json.loads(text)
            
            # Validate query_type
            valid_types = ["simple_factual", "multi_hop", "comparative", "temporal", "exploratory"]
            qtype = data.get("query_type", "simple_factual")
            if qtype not in valid_types:
                qtype = "simple_factual"

            return QueryClassification(
                query=query,
                query_type=qtype,
                main_topics=data.get("main_topics", []),
                requires_recent=data.get("requires_recent", False),
                entities=data.get("entities", [])
            )

        except Exception as e:
            self.logger.error(f"Query classification failed: {e}")
            # Robust heuristic fallback based on keywords when LLM fails or is rate-limited
            query_lower = query.lower()
            qtype = "simple_factual"
            requires_recent = False
            
            temporal_words = ["latest", "recent", "2023", "2024", "current", "newly", "update"]
            if any(w in query_lower for w in temporal_words):
                qtype = "temporal"
                requires_recent = True
            elif any(w in query_lower for w in ["compare", "vs", "versus", "difference between"]):
                qtype = "comparative"
            elif any(w in query_lower for w in ["how", "why", "mechanism", "pathway", "interaction"]):
                qtype = "multi_hop"
                
            entities = []
            for word in query.split():
                if word[0].isupper() and len(word) > 2:
                    entities.append(word.strip(".,;:?!()\"'"))

            return QueryClassification(
                query=query,
                query_type=qtype,
                main_topics=[w for w in ["immunotherapy", "genomics", "drug_interactions"] if w in query_lower],
                requires_recent=requires_recent,
                entities=entities
            )

class MetadataPreFilter:
    """
    Builds Qdrant-specific filter conditions based on query classification
    to narrow the search space before vector search.
    """
    
    def __init__(self):
        self.cluster_keywords = {
            "immunotherapy": [
                "pd-1", "pd-l1", "checkpoint", "pembrolizumab", 
                "nivolumab", "car-t", "immunotherapy", "ici", "ctla-4"
            ],
            "drug_interactions": [
                "drug interaction", "cytochrome", "p450", "cyp", 
                "pharmacokinetics", "adverse", "polypharmacy", "ddi"
            ],
            "genomics": [
                "gene", "genome", "crispr", "snp", "sequencing", 
                "epigenetics", "mutation", "rna", "dna", "allele"
            ]
        }

    def _detect_cluster(self, classification: QueryClassification) -> str | None:
        """Heuristically maps query content to a known data cluster."""
        text = (
            classification.query + " " + 
            " ".join(classification.main_topics) + " " + 
            " ".join(classification.entities)
        ).lower()
        
        for cluster, keywords in self.cluster_keywords.items():
            if any(k in text for k in keywords):
                return cluster
        return None

    def build_filter(self, classification: QueryClassification) -> FilterConfig:
        """
        Constructs a FilterConfig with specific conditions for the query type.
        """
        cluster = self._detect_cluster(classification)
        must = []
        should = []
        min_year = None
        requires_fresh = False

        # Apply topic cluster filter if detected
        if cluster:
            must.append({"key": "topic_cluster", "match": cluster})

        qtype = classification.query_type

        if qtype == "multi_hop":
            min_year = 2010
            must.append({"key": "year", "range": {"gte": 2010}})
        
        elif qtype == "temporal" or classification.requires_recent:
            min_year = 2018
            import re
            years = [int(y) for y in re.findall(r'\b(20\d{2})\b', classification.query)]
            if years:
                min_year = max(years)
            must.append({"key": "year", "range": {"gte": min_year}})
            requires_fresh = True
            
        elif qtype == "comparative":
            # No age restriction, but bias toward newer comparisons
            should.append({"key": "year", "range": {"gte": 2015}})
            
        return FilterConfig(
            must_conditions=must,
            should_conditions=should,
            min_year=min_year,
            topic_cluster=cluster,
            requires_fresh=requires_fresh
        )

    def build(self, classification: QueryClassification) -> FilterConfig:
        """Alias for build_filter for compatibility."""
        return self.build_filter(classification)

class HybridRetriever:
    """
    Executes hybrid retrieval combining dense vector search and keyword boosting.
    Optimizes for relevance, freshness, and diversity using RRF and MMR.
    """
    
    def __init__(self):
        from database.qdrant_client import QdrantManager
        from ingestion.embedder import BiomedicalEmbedder
        self.qdrant = QdrantManager()
        self.embedder = BiomedicalEmbedder()
        self.logger = get_logger(__name__)

    def _calculate_keyword_matches(self, text: str, query: str) -> int:
        query_terms = set(query.lower().split())
        text_lower = text.lower()
        matches = 0
        for term in query_terms:
            if len(term) > 3 and term in text_lower:
                matches += 1
        return matches

    def _rrf_fuse(self, dense_results: list[dict], query: str) -> list[dict]:
        """Combines dense scores and keyword matches using Reciprocal Rank Fusion."""
        # 1. Rank by dense score
        dense_ranked = sorted(dense_results, key=lambda x: x["score"], reverse=True)
        
        # 2. Rank by keyword matches
        for r in dense_results:
            r["keyword_matches"] = self._calculate_keyword_matches(r["text"], query)
        keyword_ranked = sorted(dense_results, key=lambda x: x["keyword_matches"], reverse=True)

        # 3. Apply RRF
        # score = 1 / (rank + k) where k=60
        fusion_scores = {}
        for rank, res in enumerate(dense_ranked):
            cid = res["chunk_id"]
            fusion_scores[cid] = fusion_scores.get(cid, 0) + (1.0 / (rank + 60))
        
        for rank, res in enumerate(keyword_ranked):
            cid = res["chunk_id"]
            fusion_scores[cid] = fusion_scores.get(cid, 0) + (1.0 / (rank + 60))

        # Update scores and return
        for res in dense_results:
            res["fusion_score"] = fusion_scores[res["chunk_id"]]
        
        return sorted(dense_results, key=lambda x: x["fusion_score"], reverse=True)

    def _mmr_rerank(self, query_emb, results: list[dict], top_k: int, lambda_param: float = 0.7) -> list[dict]:
        """Re-ranks results to maximize diversity using Maximum Marginal Relevance."""
        if not results:
            return []
            
        # Get embeddings for chunks to calculate similarity
        texts = [r["text"] for r in results]
        chunk_embs_list = self.embedder.embed_batch(texts)
        chunk_embs = np.array(chunk_embs_list)
        # Normalize embeddings for dot product (cosine similarity)
        chunk_embs = chunk_embs / np.linalg.norm(chunk_embs, axis=1, keepdims=True)
        
        selected_indices = []
        candidates = list(range(len(results)))
        
        # Query embedding normalization
        query_norm = query_emb / np.linalg.norm(query_emb)

        while len(selected_indices) < top_k and candidates:
            best_mmr = -1e9
            best_idx = -1
            
            for i in candidates:
                # Similarity to query
                sim_query = np.dot(query_norm, chunk_embs[i])
                
                # Max similarity to already selected
                sim_selected = 0
                if selected_indices:
                    sim_selected = max(np.dot(chunk_embs[i], chunk_embs[j]) for j in selected_indices)
                
                mmr_score = lambda_param * sim_query - (1 - lambda_param) * sim_selected
                
                if mmr_score > best_mmr:
                    best_mmr = mmr_score
                    best_idx = i
            
            if best_idx != -1:
                selected_indices.append(best_idx)
                candidates.remove(best_idx)
            else:
                break
                
        return [results[i] for i in selected_indices]

    def retrieve(self, 
                 query: str, 
                 classification = None, 
                 filter_config = None, 
                 top_k: int = 5) -> list[RetrievalResult]:
        """
        Main retrieval entry point.
        Supports both retrieve(query, classification, filter_config, top_k)
        and retrieve(query, filter_config, top_k) positional patterns.
        """
        try:
            # Handle parameter swapping dynamically
            if classification is not None and classification.__class__.__name__ == "FilterConfig":
                tmp = classification
                classification = filter_config if (filter_config is not None and filter_config.__class__.__name__ == "QueryClassification") else None
                filter_config = tmp

            # Fallback to defaults if None
            if classification is None:
                classification = QueryClassification(query=query, query_type="simple_factual", main_topics=[], requires_recent=False, entities=[])
            if filter_config is None:
                filter_config = FilterConfig(must_conditions=[], should_conditions=[], min_year=0, topic_cluster=None, requires_fresh=False)

            query_emb = self.embedder.embed_text(query)
            
            # Step 1: Dense Retrieval with Pre-filters
            filters = {}
            if filter_config.topic_cluster:
                filters["topic_cluster"] = filter_config.topic_cluster
            
            results = self.qdrant.search_chunks(
                query_embedding=query_emb,
                level="semantic",
                top_k=20,
                filters=filters
            )

            # Step 3: Keyword Boost & RRF Fusion
            fused_results = self._rrf_fuse(results, query)

            # Step 4: Apply metadata filtering (Safety Check)
            filtered = []
            for r in fused_results:
                # Contradiction check
                if r.get("contradiction_flag", False):
                    continue
                # Date check
                if filter_config.min_year and r.get("year", 0) < filter_config.min_year:
                    continue
                # Freshness check
                if filter_config.requires_fresh and r.get("freshness_score", 0) < 0.5:
                    continue
                filtered.append(r)

            # Record number of filtered results before potentially relaxing
            num_filtered_before_relax = len(filtered)

            # Step 6: Safeguard - Relax filters if needed
            if len(filtered) < 3 and results:
                self.logger.warning(f"Retrieval returned only {len(filtered)} results. Relaxing filters.")
                # Just use original results without date/freshness constraints
                filtered = [r for r in fused_results if not r.get("contradiction_flag", False)]

            # Step 5: MMR Reranking for diversity
            final_list = self._mmr_rerank(query_emb, filtered, top_k)

            results_to_return = [
                RetrievalResult(
                    chunk_id=r["chunk_id"],
                    paper_id=r["paper_id"],
                    text=r["text"],
                    score=r["score"],
                    level=r["level"],
                    section_type=r["section_type"],
                    topic_cluster=r["topic_cluster"],
                    year=r["year"],
                    freshness_score=r["freshness_score"],
                    contradiction_flag=r["contradiction_flag"],
                    keyword_matches=r.get("keyword_matches", 0)
                )
                for r in final_list
            ]

            # Safeguard: if temporal query produces fewer than 3 chunks after pre-filter/retry
            qtype = getattr(classification, "query_type", "")
            is_temporal = qtype == "temporal" or (filter_config and getattr(filter_config, "requires_fresh", False))
            if is_temporal and (num_filtered_before_relax < 3 or len(results_to_return) < 3):
                self.logger.info(
                    "Temporal query: insufficient corpus coverage"
                    " — signaling immediate live fetch needed"
                )
                
                # Append LIVE_FETCH_SIGNAL sentinel dict to trigger immediate live fetch
                results_to_return.append({
                    "chunk_id": "LIVE_FETCH_SIGNAL",
                    "text": "",
                    "score": 0.0,
                    "live_fetch_required": True,
                    "topic_cluster": filter_config.topic_cluster or "immunotherapy"
                })

            return results_to_return

        except Exception as e:
            self.logger.error(f"Hybrid retrieval failed: {e}")
            return []

class RetrievalSufficiencyEvaluator:
    """
    Evaluates if the retrieved chunks are sufficient to answer the user query.
    Performs checks on quantity, relevance score, paper diversity, and freshness.
    """
    
    def evaluate(self, 
                 results: list[RetrievalResult], 
                 classification: QueryClassification) -> SufficiencyResult:
        """
        Runs the self-check evaluation.
        """
        # Check for LIVE_FETCH_SIGNAL sentinel first
        for r in results:
            cid = r.chunk_id if hasattr(r, "chunk_id") else (r.get("chunk_id", "") if isinstance(r, dict) else "")
            if cid == "LIVE_FETCH_SIGNAL":
                return SufficiencyResult(
                    is_sufficient=False,
                    reason="stale_results",
                    suggestion="live_fetch"
                )

        # Filter out sentinel markers if present to avoid AttributeError on dictionary fields
        clean_results = [
            r for r in results 
            if not (isinstance(r, dict) and r.get("chunk_id") == "LIVE_FETCH_SIGNAL")
        ]

        # Check 1: Quantity
        if len(clean_results) < 3:
            return SufficiencyResult(
                is_sufficient=False, 
                reason="too_few_chunks", 
                suggestion="broaden_query"
            )

        # Check 2: Relevance (using the average vector score)
        if not clean_results:
            return SufficiencyResult(is_sufficient=False, reason="too_few_chunks", suggestion="broaden_query")
            
        avg_score = sum(r.score for r in clean_results) / len(clean_results)
        if avg_score < 0.45:
            return SufficiencyResult(
                is_sufficient=False, 
                reason="low_relevance", 
                suggestion="rewrite_query"
            )

        # Check 3: Coverage (Diversity of sources)
        if classification.query_type in ["multi_hop", "comparative"]:
            unique_papers = set(r.paper_id for r in clean_results)
            if len(unique_papers) < 2:
                return SufficiencyResult(
                    is_sufficient=False, 
                    reason="low_diversity", 
                    suggestion="parallel_retrieval"
                )

        # Check 4: Freshness (For temporal queries)
        if classification.query_type == "temporal" or classification.requires_recent:
            recent_count = sum(1 for r in clean_results if r.year >= 2020)
            if recent_count < 2:
                return SufficiencyResult(
                    is_sufficient=False, 
                    reason="stale_results", 
                    suggestion="live_fetch"
                )

        # All checks passed
        return SufficiencyResult(is_sufficient=True, reason="", suggestion="")


class Agent1Retrieval:
    """
    Main orchestrator for Agent 1 (Agentic Retrieval).
    Coordinates classification, filtering, hybrid retrieval, and sufficiency evaluation.
    """
    
    def __init__(self):
        self.classifier = QueryClassifier()
        self.pre_filter = MetadataPreFilter()
        self.retriever = HybridRetriever()
        self.evaluator = RetrievalSufficiencyEvaluator()
        self.logger = get_logger(__name__)

    def _rewrite_query(self, query: str) -> str:
        """Uses Gemini to rewrite a query for better retrieval."""
        try:
            # Configure Gemini using round-robin key management
            client = genai.Client(api_key=get_gemini_key())
            
            prompt = (
                f"Rewrite this biomedical query to be more effective for a vector search engine.\n"
                f"Original: \"{query}\"\n"
                f"Simplify terms, use common synonyms, and remove filler words.\n"
                f"Return ONLY the rewritten query text."
            )
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            self.logger.error(f"Query rewriting failed: {e}")
            return query

    def retrieve(self, 
                 query: str, 
                 conversation_history: list = None, 
                 top_k: int = 5) -> Agent1Result:
        """
        Executes the full Agent 1 retrieval pipeline with retry logic.
        """
        # 1. Classify
        classification = self.classifier.classify(query)
        
        # 2. Build Filter
        filter_config = self.pre_filter.build_filter(classification)
        
        # 3. Hybrid Retrieval
        results = self.retriever.retrieve(query, classification, filter_config, top_k)
        
        # 4. Evaluate Sufficiency
        sufficiency = self.evaluator.evaluate(results, classification)
        
        filter_was_relaxed = False
        query_was_rewritten = False
        rewritten_query = ""

        # 5. Retry Logic
        if not sufficiency.is_sufficient:
            if sufficiency.suggestion == "broaden_query":
                self.logger.info("Retrying with relaxed filters (broaden_query)")
                # Relax filter: remove topic cluster and min_year
                filter_config.topic_cluster = None
                filter_config.min_year = None
                filter_config.must_conditions = []
                results = self.retriever.retrieve(query, classification, filter_config, top_k)
                sufficiency = self.evaluator.evaluate(results, classification)
                filter_was_relaxed = True
                
            elif sufficiency.suggestion == "rewrite_query":
                self.logger.info("Retrying with rewritten query (rewrite_query)")
                rewritten_query = self._rewrite_query(query)
                query_was_rewritten = True
                # Re-classify and re-run
                new_class = self.classifier.classify(rewritten_query)
                new_filter = self.pre_filter.build_filter(new_class)
                results = self.retriever.retrieve(rewritten_query, new_class, new_filter, top_k)
                sufficiency = self.evaluator.evaluate(results, new_class)

        return Agent1Result(
            query=query,
            classification=classification,
            results=results,
            sufficiency=sufficiency,
            filter_was_relaxed=filter_was_relaxed,
            query_was_rewritten=query_was_rewritten,
            rewritten_query=rewritten_query
        )

import json
from google import genai
import numpy as np
from dataclasses import dataclass
from config import get_config
from utils.logger import get_logger
from utils.llm_utils import get_gemini_key
from utils.thought_logger import ThoughtLogger

from agents.models import (
    QueryClassification, FilterConfig,
    RetrievalResult, SufficiencyResult
)

class Agent1Result:
    # We can keep internal wrappers as standard classes or dataclasses per the user's instructions: "Keep as dataclass: Internal computation results that never cross agent boundaries."
    def __init__(self, query: str, classification: QueryClassification, results: list[RetrievalResult], sufficiency: SufficiencyResult, filter_was_relaxed: bool, query_was_rewritten: bool, rewritten_query: str):
        self.query = query
        self.classification = classification
        self.results = results
        self.sufficiency = sufficiency
        self.filter_was_relaxed = filter_was_relaxed
        self.query_was_rewritten = query_was_rewritten
        self.rewritten_query = rewritten_query

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
        
        tl = ThoughtLogger(
            session_id=getattr(self, '_session_id', ''),
            agent='agent1'
        )
        
        # Configure Gemini using round-robin key management
        client = genai.Client(api_key=get_gemini_key())
        
        prompt = f"""You are a query classifier for a
biomedical research assistant specializing in
immunotherapy, drug interactions, and genomics.

Analyze this query and return JSON only.

Query: {query}

Return this exact JSON structure:
{{
  "is_biomedical": true or false,
  "rejection_reason": "why rejected if not biomedical, else empty string",
  "query_type": "simple_factual" or "multi_hop" or "comparative" or "temporal" or "exploratory",
  "main_topics": ["topic1", "topic2"],
  "entities": ["drug or gene or disease names"],
  "requires_recent": true or false
}}

Rules for is_biomedical:
  true  - question is about drugs, diseases, genes,
          clinical trials, pharmacology, genomics,
          medical treatments, biomarkers, or any
          biomedical research topic
  false - question is about cooking, sports, politics,
          technology, entertainment, general science,
          math, history, or anything unrelated to
          biomedical research

Rules for query_type (only if is_biomedical is true):
  simple_factual - single concept lookup
  multi_hop      - requires connecting multiple concepts
  comparative    - comparing two or more things
  temporal       - asks about current or recent state
  exploratory    - open ended discovery

Rules for requires_recent:
  true if query uses words like: current, latest,
  recent, 2024, 2023, now, today, approved

Return ONLY the JSON object. No explanation."""

        try:
            response = client.models.generate_content(
                model="gemini-flash-latest",
                contents=prompt
            )
            text = response.text.strip()
            
            # Clean JSON from markdown if necessary
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            parsed = json.loads(text)
            
            is_biomedical = parsed.get('is_biomedical', True)
            
            if not is_biomedical:
                self.logger.info(f"Query rejected as off-topic: {query[:60]}")
                return QueryClassification(
                    query=query,
                    query_type='simple_factual',
                    main_topics=[],
                    requires_recent=False,
                    entities=[],
                    domain_rejected=True,
                    rejection_reason=parsed.get(
                        'rejection_reason',
                        'Query not related to biomedical research'
                    )
                )
            
            # Validate query_type
            valid_types = ["simple_factual", "multi_hop", "comparative", "temporal", "exploratory"]
            qtype = parsed.get("query_type", "simple_factual")
            if qtype not in valid_types:
                qtype = "simple_factual"

            classification = QueryClassification(
                query=query,
                query_type=qtype,
                main_topics=parsed.get("main_topics", []),
                requires_recent=parsed.get("requires_recent", False),
                entities=parsed.get("entities", []),
                domain_rejected=False,
                rejection_reason=''
            )
            try:
                tl.trace(
                    step='classify',
                    obs=f"Query received: '{query[:80]}' "
                        f"Length: {len(query)} chars",
                    thk=f"Analyzing query intent. "
                        f"Keywords suggest {qtype} type. "
                        f"Entities detected: {classification.entities[:3]}",
                    act=f"Classify as {qtype}. "
                        f"Set requires_recent={classification.requires_recent}",
                    out=f"Classification: {qtype} | "
                        f"Topics: {classification.main_topics[:2]} | "
                        f"Entities: {classification.entities[:2]}",
                    confidence=0.85,
                    metadata={'query_type': qtype,
                              'entity_count': len(classification.entities)}
                )
                classification.thought_traces = tl.get_traces()
            except Exception as trace_err:
                self.logger.warning(f"Trace logging failed: {trace_err}")
                
            return classification

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
            
        filter_config = FilterConfig(
            must_conditions=must,
            should_conditions=should,
            min_year=min_year,
            topic_cluster=cluster,
            requires_fresh=requires_fresh
        )
        
        try:
            tl = ThoughtLogger(session_id='', agent='agent1')
            tl.trace(
                step='pre_filter',
                obs=f"Query type: {classification.query_type}. "
                    f"Topics: {classification.main_topics[:2]}. "
                    f"Requires recent: {classification.requires_recent}",
                thk=f"Temporal query needs tightest filter. "
                    f"Simple factual needs cluster match only. "
                    f"Applying {'tight' if classification.requires_recent else 'standard'} filter.",
                act=f"Building filter: "
                    f"cluster={filter_config.topic_cluster}, "
                    f"min_year={filter_config.min_year}, "
                    f"requires_fresh={filter_config.requires_fresh}",
                out=f"Filter built with "
                    f"{len(filter_config.must_conditions)} must conditions",
                confidence=0.9
            )
        except Exception as trace_err:
            pass
            
        return filter_config

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
                 top_k: int = 5,
                 session_id: str | None = None) -> list[RetrievalResult]:
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

            from utils.config_overrides import get_override
            qtype = getattr(classification, "query_type", "simple_factual")
            if qtype == "multi_hop":
                top_k = get_override('retrieval_top_k_multi_hop', top_k)

            embedding_query = query
            if session_id:
                from agents.conversation_memory import SessionTopicModel
                topic_model = SessionTopicModel()
                bias = topic_model.get_retrieval_bias(session_id, query)
                if bias:
                    embedding_query = topic_model.build_biased_query(query, bias)
                    if bias.get("preferred_cluster") and not filter_config.topic_cluster:
                        filter_config.topic_cluster = bias["preferred_cluster"]
                        filter_config.must_conditions.append({"key": "topic_cluster", "match": bias["preferred_cluster"]})
                    self.logger.info(f"Session bias applied: {bias.get('preferred_cluster')}")

            query_emb = self.embedder.embed_text(embedding_query)
            
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
            
            from utils.config_overrides import get_override
            freshness_threshold = get_override('temporal_freshness_threshold', 0.5)
            
            for r in fused_results:
                # Contradiction check
                if r.get("contradiction_flag", False):
                    continue
                # Date check
                if filter_config.min_year and r.get("year", 0) < filter_config.min_year:
                    continue
                # Freshness check
                if filter_config.requires_fresh and r.get("freshness_score", 0) < freshness_threshold:
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
                    keyword_matches=r.get("keyword_matches", 0),
                    from_graph=r.get("from_graph", False)
                )
                for r in final_list
            ]

            # Graph Expansion
            if len(results_to_return) < top_k * 2:
                try:
                    graph_expander = GraphExpansionRetriever()
                    expanded_results = graph_expander.expand_with_graph(
                        results_to_return, query_emb, top_k
                    )
                    if any(getattr(r, 'from_graph', False) for r in expanded_results):
                        self.logger.info("Graph expansion added citation neighbors")
                    results_to_return = expanded_results
                except Exception as e:
                    self.logger.warning(f"Graph expansion failed: {e}")

            # Safeguard: if temporal query produces fewer than 3 chunks after pre-filter/retry
            qtype = getattr(classification, "query_type", "")
            is_temporal = qtype == "temporal" or (filter_config and getattr(filter_config, "requires_fresh", False))
            if is_temporal and (num_filtered_before_relax < 3 or len(results_to_return) < 3):
                self.logger.info(
                    "Temporal query: insufficient corpus coverage"
                    " - signaling immediate live fetch needed"
                )
                
                # Append LIVE_FETCH_SIGNAL sentinel dict to trigger immediate live fetch
                results_to_return.append(RetrievalResult(
                    chunk_id="LIVE_FETCH_SIGNAL",
                    paper_id="",
                    text="",
                    score=0.0,
                    level="",
                    topic_cluster=filter_config.topic_cluster or "immunotherapy",
                    live_fetch=True
                ))

            try:
                tl = ThoughtLogger(session_id=session_id or '', agent='agent1')
                avg_score = sum(r.score for r in results_to_return) / max(len(results_to_return), 1)
                fresh_count = sum(
                    1 for r in results_to_return if getattr(r, 'freshness_score', 0) > 0.7
                )
                tl.trace(
                    step='retrieve',
                    obs=f"Searched {len(results_to_return)} chunks returned. "
                        f"Avg score: {avg_score:.3f}. "
                        f"Fresh chunks: {fresh_count}/{len(results_to_return)}",
                    thk=f"{'Good coverage' if avg_score > 0.7 else 'Low similarity scores - sparse coverage'}. "
                        f"{'Sufficient fresh evidence' if fresh_count >= 3 else 'Limited fresh chunks for temporal query'}. "
                        f"Strategy: {classification.query_type}",
                    act=f"Return top {len(results_to_return)} chunks after RRF+MMR. "
                        f"{'Flag for freshness check' if fresh_count < 3 else 'No flags needed'}",
                    out=f"Retrieved {len(results_to_return)} chunks. "
                        f"Top score: {results_to_return[0].score:.3f if results_to_return else 0:.3f}. "
                        f"Clusters: {list(set(getattr(r, 'topic_cluster', '') for r in results_to_return[:3]))}",
                    confidence=avg_score,
                    metadata={'result_count': len(results_to_return),
                              'avg_score': avg_score}
                )
                
                # Append the traces to the classification object since results is a list
                if classification is not None and not hasattr(classification, "thought_traces"):
                    classification.thought_traces = []
                classification.thought_traces.extend(tl.get_traces())
            except Exception as trace_err:
                self.logger.warning(f"Trace logging failed: {trace_err}")

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
            if r.chunk_id != "LIVE_FETCH_SIGNAL"
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
                model="gemini-flash-latest",
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

class GraphExpansionRetriever:
    def __init__(self):
        from database.neo4j_client import Neo4jManager
        from database.qdrant_client import QdrantManager
        from ingestion.embedder import BiomedicalEmbedder
        self.neo4j = Neo4jManager()
        self.qdrant = QdrantManager()
        self.embedder = BiomedicalEmbedder()
        self.logger = get_logger(__name__)

    def expand_with_graph(self, initial_results: list, query_embedding: list[float], top_k: int = 5) -> list:
        if not self.neo4j.driver:
            return initial_results
            
        # Step 1: Extract paper_ids from initial results
        paper_ids = list(set(r.paper_id for r in initial_results if hasattr(r, 'paper_id')))
        if not paper_ids:
            return initial_results
            
        # Step 2: Get graph neighbors
        citation_neighbors = self.neo4j.get_citation_neighbors(paper_ids, depth=1)
        contradiction_neighbors = self.neo4j.get_contradiction_neighbors(paper_ids)
        all_neighbor_ids = list(set(citation_neighbors + contradiction_neighbors))
        
        if not all_neighbor_ids:
            return initial_results
            
        # Step 3: Fetch chunks for neighbor papers from Qdrant
        neighbor_chunks = []
        for neighbor_id in all_neighbor_ids[:10]:
            try:
                results = self.qdrant.search_chunks(
                    query_embedding=query_embedding,
                    level='semantic',
                    top_k=2,
                    filters={'paper_id': neighbor_id}
                )
                neighbor_chunks.extend(results)
            except Exception as e:
                self.logger.warning(f"Failed to fetch neighbor chunks for {neighbor_id}: {e}")
                
        if not neighbor_chunks:
            return initial_results
            
        # Step 4: Convert neighbor chunks to RetrievalResult format
        neighbor_results = []
        for chunk in neighbor_chunks:
            neighbor_results.append(RetrievalResult(
                chunk_id=chunk['chunk_id'],
                paper_id=chunk['paper_id'],
                text=chunk['text'],
                score=chunk['score'] * 0.85,  # slight penalty for graph hop
                level=chunk['level'],
                section_type=chunk['section_type'],
                topic_cluster=chunk.get('topic_cluster', ''),
                year=chunk.get('year', 2020),
                freshness_score=chunk.get('freshness_score', 1.0),
                contradiction_flag=chunk.get('contradiction_flag', False),
                keyword_matches=0,
                from_graph=True
            ))
            
        # Step 5: Combine and re-rank with MMR
        all_candidates = initial_results + neighbor_results
        
        # We need query_embedding as np array
        import numpy as np
        query_emb = np.array(query_embedding)
        
        # We'll use HybridRetriever's _mmr_rerank to simplify if possible, but it takes list of dicts.
        # Let's implement a simple MMR here for the objects.
        # Get embeddings for chunks to calculate similarity
        texts = [r.text for r in all_candidates]
        chunk_embs_list = self.embedder.embed_batch(texts)
        chunk_embs = np.array(chunk_embs_list)
        # Normalize embeddings
        chunk_embs = chunk_embs / np.linalg.norm(chunk_embs, axis=1, keepdims=True)
        query_norm = query_emb / np.linalg.norm(query_emb)
        
        selected_indices = []
        candidates = list(range(len(all_candidates)))
        lambda_param = 0.7
        
        while len(selected_indices) < top_k and candidates:
            best_mmr = -1e9
            best_idx = -1
            
            for i in candidates:
                sim_query = np.dot(query_norm, chunk_embs[i])
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
                
        return [all_candidates[i] for i in selected_indices]

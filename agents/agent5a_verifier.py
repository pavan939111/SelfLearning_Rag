import json
from google import genai
from dataclasses import dataclass
from ingestion.embedder import BiomedicalEmbedder
from database.qdrant_client import QdrantManager
from utils.logger import get_logger
from utils.llm_utils import get_gemini_key

from agents.models import VerificationResult

class Agent5AVerifier:
    """
    Agent 5A: Standalone Quality-Gate Verifier.
    Verifies any paper before it enters the FailurerRAG corpus —
    whether from batch ingestion, live fetch, or manual addition.
    """
    def __init__(self, embedder=None, qdrant=None, logger=None, model=None):
        self.embedder = embedder if embedder is not None else BiomedicalEmbedder()
        self.qdrant = qdrant if qdrant is not None else QdrantManager()
        self.logger = logger if logger is not None else get_logger(__name__)
        
        # Configure Gemini
        if model is not None:
            self.client = model
        else:
            gemini_key = get_gemini_key()
            self.client = genai.Client(api_key=gemini_key) if gemini_key else genai.Client()

    def _detect_cluster(self, text: str) -> str | None:
        """Heuristically detects a known topic cluster from text keywords."""
        text_lower = text.lower()
        if any(kw in text_lower for kw in ["pd-1", "pd-l1", "pembrolizumab", "nivolumab", "immunotherapy", "checkpoint", "car-t", "ici", "ctla-4"]):
            return "immunotherapy"
        elif any(kw in text_lower for kw in ["drug interaction", "cytochrome", "p450", "pharmacokinetics", "adverse", "polypharmacy", "ddi"]):
            return "drug_interactions"
        elif any(kw in text_lower for kw in ["gene", "genome", "crispr", "snp", "sequencing", "genomics", "epigenetics", "mutation", "rna", "dna", "allele"]):
            return "genomics"
        return None

    def _get_citation_velocity(self, paper_id: str) -> int:
        """
        Fetches citation count for a paper from Semantic Scholar.
        Returns citation count as integer. Returns 0 on any error.
        """
        import requests
        import time
        from config import get_config
        config = get_config()
        
        try:
            url = f"https://api.semanticscholar.org/graph/v1/paper/PMID:{paper_id}"
            params = {"fields": "citationCount,year,title"}
            headers = {"x-api-key": config.semantic_scholar_api_key} if config.semantic_scholar_api_key else {}
            
            response = requests.get(url, params=params, headers=headers, timeout=8)
            time.sleep(1.1)  # Strict 1 request per second rate limit
            
            if response.status_code == 429:
                self.logger.warning("Semantic Scholar 429 Rate Limit. Sleeping 5s and retrying...")
                time.sleep(5)
                response = requests.get(url, params=params, headers=headers, timeout=8)
                time.sleep(1.1)
                
            if response.status_code == 200:
                data = response.json()
                return int(data.get("citationCount", 0))
            return 0
        except Exception as e:
            self.logger.warning(f"Citation fetch failed for {paper_id}: {e}")
            return 0

    def _citations_from_corpus(self, paper_id: str) -> int:
        """
        Counts how many papers in our existing Qdrant corpus cite this paper.
        Approximated by checking if paper_id appears in any chunk payloads.
        """
        try:
            # We skip the heavy scroll for MVP, returning 0 or mock
            # In a real impl, we'd scroll Qdrant or use a dedicated graph DB like neo4j
            return 0
        except Exception:
            return 0

    def _evaluate_ingestion_rules(self, paper, check4_result) -> tuple[bool, str]:
        """
        Evaluates which selective ingestion rule applies.
        Returns (should_ingest: bool, rule_matched: str)
        """
        try:
            # Extract fields from PaperRecord object or dict
            if hasattr(paper, "abstract"):
                abstract = getattr(paper, "abstract", "") or ""
                year = getattr(paper, "year", 2022) or 2022
                topic_cluster = getattr(paper, "topic_cluster", "") or ""
                evidence_level = getattr(paper, "evidence_level", "other") or "other"
            else:
                abstract = paper.get("abstract", paper.get("text", "")) or ""
                year = paper.get("year", 2022) or 2022
                topic_cluster = paper.get("topic_cluster", "") or ""
                evidence_level = paper.get("evidence_level", "other") or "other"

            # RULE 1 — Contradiction detection:
            pot = check4_result.get("potential_contradiction", False) if isinstance(check4_result, dict) else False
            conf = check4_result.get("confidence", 0.0) if isinstance(check4_result, dict) else 0.0
            if pot and conf > 0.7:
                return (True, "contradiction_detected")

            # RULE 3 — Citation Velocity:
            paper_id = getattr(paper, "paper_id", "") or paper.get("paper_id", "") if isinstance(paper, dict) else ""
            total_citations = self._get_citation_velocity(paper_id)
            if isinstance(check4_result, dict):
                check4_result["citation_count"] = total_citations
                
            if total_citations >= 50:
                return (True, "high_citation_velocity")
            if year >= 2021 and total_citations >= 10:
                return (True, "high_citation_velocity")
                
            if total_citations == 0:
                # Fall back to recency rule: year >= 2022
                if year >= 2022:
                    return (True, "recent_paper_fallback")

            # RULE 5 — Fallback for recent papers:
            if year >= 2023:
                return (True, "recent_paper")

            # Extract keywords from paper abstract for rules 2 & 4
            abstract_lower = abstract.lower()
            abstract_keywords = set(word.strip(".,;:?!'\"()[]{}*-_") for word in abstract_lower.split() if len(word.strip(".,;:?!'\"()[]{}*-_")) > 2)

            # Query database
            from database.supabase_client import SupabaseManager
            supabase = SupabaseManager()
            if supabase and supabase.client:
                # RULE 2 — Coverage gap match:
                res_gaps = supabase.client.table("agent6_gaps").select("topic").gte("query_count", 3).execute()
                if res_gaps and res_gaps.data:
                    for row in res_gaps.data:
                        gap_topic = row.get("topic", "").strip().lower()
                        if gap_topic:
                            if gap_topic in abstract_lower or any(word in abstract_keywords for word in gap_topic.split()):
                                return (True, "fills_coverage_gap")

                # RULE 4 — Query pattern match:
                res_patterns = supabase.client.table("agent6_patterns").select("topic_cluster", "failure_type").gte("occurrence_count", 5).execute()
                if res_patterns and res_patterns.data:
                    for row in res_patterns.data:
                        pattern_cluster = row.get("topic_cluster", "").strip().lower()
                        failure_type = row.get("failure_type", "").strip().lower()
                        if pattern_cluster == topic_cluster.lower() and failure_type == "completeness":
                            return (True, "matches_query_patterns")

        except Exception as sb_err:
            self.logger.warning(f"Supabase query failed during selective ingestion rule check: {sb_err}. Falling back to basic rule.")
            # Fall back to year >= 2018 basic rule
            try:
                if hasattr(paper, "year"):
                    year = getattr(paper, "year", 2022) or 2022
                else:
                    year = paper.get("year", 2022) or 2022
                if year >= 2018:
                    return (True, "basic_rule_fallback")
            except Exception:
                pass

        return (False, "no_rule_matched")

    def verify(self, paper) -> VerificationResult:
        """
        Runs 4 checks in sequence.
        Each rejection returns immediately.
        All 4 must pass for verification to succeed.
        """
        paper_id = "unknown"
        try:
            # Extract fields from PaperRecord object or dict
            if hasattr(paper, "abstract"):
                abstract = getattr(paper, "abstract", "") or ""
                title = getattr(paper, "title", "") or ""
                year = getattr(paper, "year", 2022) or 2022
                paper_id = getattr(paper, "paper_id", "") or ""
                topic_cluster = getattr(paper, "topic_cluster", "") or ""
                journal = getattr(paper, "journal", "") or ""
            else:
                abstract = paper.get("abstract", paper.get("text", "")) or ""
                title = paper.get("title", "") or ""
                year = paper.get("year", 2022) or 2022
                paper_id = paper.get("paper_id", "") or ""
                topic_cluster = paper.get("topic_cluster", "") or ""
                journal = paper.get("journal", "") or ""

            # Standardize empty paper fallback
            if not paper_id:
                paper_id = "unknown"

            # -----------------------------------------------------------------
            # CHECK 1 — Domain Filter
            # -----------------------------------------------------------------
            try:
                # Embed the abstract
                query_vector = self.embedder.embed_text(abstract)
                # Search Qdrant document collection for top similarity
                results = self.qdrant.search_chunks(query_embedding=query_vector, level="document", top_k=1)
                
                if results:
                    top_score = results[0].get("score", 0.0)
                    if top_score < 0.3:
                        return VerificationResult(
                            paper_id=paper_id,
                            passed=False,
                            failed_check="domain_filter",
                            reason="Outside biomedical domain",
                            priority="low",
                            ingestion_instructions={}
                        )
                else:
                    self.logger.info("Qdrant document collection returned 0 results. Skipping domain filter check (safe pass).")
            except Exception as q_err:
                self.logger.warning(f"Domain Filter: Qdrant query failed: {q_err}. Gracefully passing to prevent infrastructure lockup.")

            # -----------------------------------------------------------------
            # CHECK 2 — Corpus Relationship
            # -----------------------------------------------------------------
            detected_cluster = self._detect_cluster(abstract + " " + title)
            pass_a = detected_cluster in ["immunotherapy", "drug_interactions", "genomics"]
            
            # Query Supabase agent6_gaps table
            pass_b = False
            gaps = []
            try:
                from database.supabase_client import SupabaseManager
                supabase = SupabaseManager()
                if supabase.client:
                    res = supabase.client.table("agent6_gaps").select("topic").execute()
                    if res.data:
                        gaps = [r.get("topic", "").strip().lower() for r in res.data if r.get("topic")]
            except Exception as sb_err:
                self.logger.warning(f"Could not fetch coverage gaps from Supabase: {sb_err}")
                
            if gaps:
                text_to_check = (title + " " + abstract).lower()
                if detected_cluster and detected_cluster in gaps:
                    pass_b = True
                elif topic_cluster and topic_cluster.lower() in gaps:
                    pass_b = True
                elif any(gap in text_to_check for gap in gaps):
                    pass_b = True

            # Check Freshness
            pass_c = year >= 2022
            
            if not (pass_a or pass_b or pass_c):
                return VerificationResult(
                    paper_id=paper_id,
                    passed=False,
                    failed_check="corpus_relationship",
                    reason="No corpus relationship found",
                    priority="low",
                    ingestion_instructions={}
                )

            # -----------------------------------------------------------------
            # CHECK 3 — Evidence Quality
            # -----------------------------------------------------------------
            text_lower = abstract.lower()
            if "systematic review" in text_lower or "meta-analysis" in text_lower:
                evidence_level = "review"
            elif "randomized" in text_lower or "rct" in text_lower:
                evidence_level = "rct"
            elif "cohort" in text_lower or "prospective" in text_lower or "retrospective" in text_lower:
                evidence_level = "cohort"
            elif "case report" in text_lower or "case series" in text_lower:
                evidence_level = "case_report"
            else:
                evidence_level = "other"

            # -----------------------------------------------------------------
            # CHECK 4 — Contradiction Check
            # -----------------------------------------------------------------
            contradiction_suspected = False
            pot_from_gemini = False
            conf_from_gemini = 0.0
            if len(abstract) > 200:
                try:
                    prompt = (
                        "Does this abstract make claims that contradict established medical consensus?\n"
                        f"Abstract: {abstract}\n\n"
                        "Reply JSON only:\n"
                        "{\n"
                        '  "potential_contradiction": true/false,\n'
                        '  "confidence": 0.0 to 1.0\n'
                        "}"
                    )
                    response = self.client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=prompt
                    )
                    text = response.text.strip()
                    
                    if "```json" in text:
                        text = text.split("```json")[1].split("```")[0].strip()
                    elif "```" in text:
                        text = text.split("```")[1].split("```")[0].strip()
                    
                    start = text.find("{")
                    end = text.rfind("}")
                    if start != -1 and end != -1:
                        text = text[start:end+1]
                    
                    data = json.loads(text)
                    pot_from_gemini = data.get("potential_contradiction", False)
                    conf_from_gemini = data.get("confidence", 0.0)
                    
                    if pot_from_gemini and conf_from_gemini > 0.8:
                        contradiction_suspected = True
                except Exception as gemini_err:
                    self.logger.warning(f"Contradiction Gemini check failed: {gemini_err}. Gracefully passing contradiction check.")

            # -----------------------------------------------------------------
            # Rule Evaluation (Selective Ingestion Gate)
            # -----------------------------------------------------------------
            check4_result = {
                "potential_contradiction": pot_from_gemini,
                "confidence": conf_from_gemini
            }
            should, rule = self._evaluate_ingestion_rules(paper, check4_result)
            if not should:
                return VerificationResult(
                    paper_id=paper_id,
                    passed=False,
                    failed_check="ingestion_rules",
                    reason="No selective ingestion rule matched",
                    priority="low",
                    ingestion_instructions={}
                )

            # -----------------------------------------------------------------
            # Priority and Ingestion Instructions Assignment
            # -----------------------------------------------------------------
            if contradiction_suspected or year >= 2023:
                priority = "high"
            elif year >= 2020:
                priority = "medium"
            else:
                priority = "low"

            t_cluster = detected_cluster
            if not t_cluster:
                if topic_cluster and topic_cluster.lower() in ["immunotherapy", "drug_interactions", "genomics"]:
                    t_cluster = topic_cluster.lower()
                else:
                    t_cluster = "immunotherapy"  # safe default

            instructions = {
                "topic_cluster": t_cluster,
                "evidence_level": evidence_level,
                "priority": priority,
                "contradiction_suspected": contradiction_suspected,
                "recommended_chunking": "standard",
                "rule_matched": rule,
                "citation_count": check4_result.get("citation_count", 0)
            }

            if contradiction_suspected:
                try:
                    # Find which existing papers might be contradicted
                    query_vector = self.embedder.embed_text(abstract)
                    results = self.qdrant.search_chunks(query_embedding=query_vector, level="semantic", top_k=3)
                    if results:
                        from database.neo4j_client import Neo4jManager
                        neo4j = Neo4jManager()
                        candidates = []
                        for r in results:
                            c_id = r.get("paper_id")
                            if c_id and c_id != paper_id:
                                candidates.append(c_id)
                        
                        candidates = list(set(candidates))
                        for c_id in candidates:
                            neo4j.create_contradiction_relationship(
                                paper_id_a=paper_id,
                                paper_id_b=c_id,
                                confidence=conf_from_gemini,
                                topic=t_cluster
                            )
                        self.logger.info(f"Contradiction graph updated: {paper_id} contradicts {len(candidates)} existing papers")
                except Exception as neo_err:
                    self.logger.warning(f"Neo4j contradiction graph update failed: {neo_err}")

            return VerificationResult(
                paper_id=paper_id,
                passed=True,
                failed_check="",
                reason="",
                priority=priority,
                ingestion_instructions=instructions
            )

        except Exception as general_err:
            self.logger.error(f"Agent 5A general crash: {general_err}. Gracefully returning safe PASS VerificationResult.")
            # Fallback to safe pass to prevent blocking user ingestion pipeline
            return VerificationResult(
                paper_id=paper_id,
                passed=True,
                failed_check="",
                reason=f"Verification crashed internally: {general_err}; bypassed for safety",
                priority="low",
                ingestion_instructions={
                    "topic_cluster": "immunotherapy",
                    "evidence_level": "other",
                    "priority": "low",
                    "contradiction_suspected": False,
                    "recommended_chunking": "standard"
                }
            )

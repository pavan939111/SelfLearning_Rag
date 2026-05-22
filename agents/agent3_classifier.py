from google import genai
import json
import time
from dataclasses import dataclass
from config import get_config
from utils.logger import get_logger
from utils.llm_utils import get_gemini_key
from database.qdrant_client import QdrantManager
from ingestion.embedder import BiomedicalEmbedder

@dataclass
class DiagnosisResult:
    failure_class: str
    root_cause: str
    confidence: float
    evidence: str
    route_to: str

class Agent3Classifier:
    """
    Agent 3: Root Cause Classifier.
    Diagnoses WHY retrieval failed so Agent 4A or 4B knows what to fix.
    Runs inside the A2->A3->A4 repair cycle.
    """
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger(__name__)
        # Initialize dependencies for Test 1
        self.qdrant = QdrantManager()
        self.embedder = BiomedicalEmbedder()

    def _determine_route(self, failure_class: str, confidence: float) -> str:
        if failure_class == "C" and confidence >= 0.65:
            return "4A"
        elif failure_class in ["A", "B"] and confidence >= 0.85:
            return "4B"
        else:
            return "escalate"

    def _test_4_freshness(self, agent2_result) -> DiagnosisResult | None:
        if getattr(agent2_result, 'live_fetch_needed', False):
            self.logger.info("Test 4 (Freshness) triggered.")
            conf = 0.85
            fc = "B"
            return DiagnosisResult(
                failure_class=fc,
                root_cause="knowledge_drift",
                confidence=conf,
                evidence="Agent 2 flagged live_fetch_needed=True due to stale local chunks.",
                route_to=self._determine_route(fc, conf)
            )
        return None

    def _test_3_completeness(self, query: str, classification, agent2_result) -> DiagnosisResult | None:
        if getattr(agent2_result, 'failed_check', '') == "completeness_grounding":
            self.logger.info("Test 3 (Completeness) triggered.")
            gaps = getattr(agent2_result, 'coverage_gaps', [])
            if not gaps:
                return None
            
            # Use Gemini to classify the nature of the gap
            try:
                client = genai.Client(api_key=get_gemini_key())
                topics = ", ".join(getattr(classification, 'main_topics', []))
                
                prompt = (
                    f"Query: {query}\n"
                    f"Main Topics: {topics}\n"
                    f"Coverage Gaps: {gaps}\n\n"
                    f"Do these gaps represent subtopics that SHOULD be in a standard clinical "
                    f"corpus about these topics (IN_SCOPE), or do they represent genuinely missing/novel/unresearched knowledge (NOVEL)?\n"
                    f"Reply ONLY with 'IN_SCOPE' or 'NOVEL'."
                )
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt
                )
                answer = response.text.strip().upper()
                
                if "IN_SCOPE" in answer:
                    fc = "C"
                    conf = 0.75
                    return DiagnosisResult(
                        failure_class=fc,
                        root_cause="query_too_narrow",
                        confidence=conf,
                        evidence="Gaps identified as in-scope. Query likely failed to retrieve available subtopics.",
                        route_to=self._determine_route(fc, conf)
                    )
                else:
                    fc = "B"
                    conf = 0.70
                    return DiagnosisResult(
                        failure_class=fc,
                        root_cause="knowledge_gap",
                        confidence=conf,
                        evidence="Gaps identified as novel/missing knowledge. Corpus lacks this data.",
                        route_to=self._determine_route(fc, conf)
                    )
            except Exception as e:
                self.logger.warning(f"Test 3 Gemini call failed: {e}")
                # Fallback on failure
                return None
        return None

    def _test_2_query_processing(self, classification, retrieval_results, agent2_result) -> DiagnosisResult | None:
        if getattr(agent2_result, 'failed_check', '') == "retrieval_relevance":
            self.logger.info("Test 2 (Query Processing) triggered.")
            if not retrieval_results:
                return None
                
            topics = set(t.lower() for t in getattr(classification, 'main_topics', []))
            entities = set(e.lower() for e in getattr(classification, 'entities', []))
            query_terms = topics.union(entities)
            
            if not query_terms:
                return None
                
            overlap_found = False
            for r in retrieval_results:
                text = (r.text if hasattr(r, 'text') else r.get('text', '')).lower()
                for term in query_terms:
                    if term in text:
                        overlap_found = True
                        break
                if overlap_found:
                    break
                    
            if not overlap_found:
                fc = "C"
                conf = 0.80
                return DiagnosisResult(
                    failure_class=fc,
                    root_cause="query_formulation",
                    confidence=conf,
                    evidence="Retrieved chunks have zero overlap with query topics/entities.",
                    route_to=self._determine_route(fc, conf)
                )
        return None

    def _test_1_existence(self, query: str) -> DiagnosisResult | None:
        self.logger.info("Test 1 (Existence) triggered.")
        try:
            client = genai.Client(api_key=get_gemini_key())
            prompt = (
                f"Generate 5 distinct alternative search queries for the following medical query.\n"
                f"Query: {query}\n"
                f"Return ONLY a JSON list of 5 strings."
            )
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
            text = response.text.strip()
            
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
                
            alt_queries = json.loads(text)
            if not isinstance(alt_queries, list) or len(alt_queries) == 0:
                raise ValueError("Invalid JSON format from Gemini")
                
            all_below_threshold = True
            for alt_q in alt_queries[:5]:
                emb = self.embedder.embed_text(alt_q)
                results = self.qdrant.search_chunks(
                    query_embedding=emb,
                    level="semantic",
                    top_k=3
                )
                if results:
                    avg_score = sum(r.get("score", 0.0) for r in results) / len(results)
                    if avg_score >= 0.4:
                        all_below_threshold = False
                        break
                        
            if all_below_threshold:
                fc = "B"
                conf = 0.85
                return DiagnosisResult(
                    failure_class=fc,
                    root_cause="coverage_gap",
                    confidence=conf,
                    evidence="5 alternative phrasings all yielded avg semantic scores below 0.4.",
                    route_to=self._determine_route(fc, conf)
                )
        except Exception as e:
            self.logger.warning(f"Test 1 Existence test failed/skipped: {e}")
        return None

    def diagnose(self, query: str, classification, retrieval_results: list, agent2_result) -> DiagnosisResult:
        """
        Runs 5 diagnostic tests in sequence.
        First test that returns a confident result wins.
        Never crashes.
        """
        self.logger.info("Starting Agent 3 Diagnosis...")
        
        try:
            # Check 4 is often deterministic and fast, but user said:
            # "Runs 5 diagnostic tests in sequence. First test that returns confident result wins."
            
            # Test 1 - Existence Test
            res_1 = self._test_1_existence(query)
            if res_1: return res_1
            
            # Test 2 - Query Processing Test
            res_2 = self._test_2_query_processing(classification, retrieval_results, agent2_result)
            if res_2: return res_2
            
            # Test 3 - Completeness Test
            res_3 = self._test_3_completeness(query, classification, agent2_result)
            if res_3: return res_3
            
            # Test 4 - Freshness Test
            res_4 = self._test_4_freshness(agent2_result)
            if res_4: return res_4
            
        except Exception as e:
            self.logger.error(f"Agent 3 encountered an unexpected error: {e}")
            
        # Test 5 - Default Fallback
        self.logger.info("Test 5 (Default Fallback) triggered.")
        fc = "C"
        conf = 0.50
        return DiagnosisResult(
            failure_class=fc,
            root_cause="unknown_query_issue",
            confidence=conf,
            evidence="No diagnostic test yielded a confident diagnosis.",
            route_to=self._determine_route(fc, conf)
        )

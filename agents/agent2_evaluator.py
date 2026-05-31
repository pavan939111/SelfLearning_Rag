from google import genai
import time
import json
from dataclasses import dataclass, field
from config import get_config
from utils.logger import get_logger
from utils.llm_utils import get_gemini_key
from utils.thought_logger import ThoughtLogger

from agents.models import (
    EvaluationResult, Agent2Result, RetrievalResult
)

class Agent2Evaluator:
    """
    Agent 2 (Quality Gate) Evaluator.
    Responsible for validating retrieved chunks before they are used for generation.
    """
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger(__name__)
        self._live_fetch_needed = False
        # Note: Gemini is re-configured per-call via get_gemini_key in checks

    def _make_result(self, 
                    checks: list[EvaluationResult], 
                    retrieval_results: list, 
                    **kwargs) -> Agent2Result:
        """Helper to construct the final Agent2Result."""
        all_passed = all(c.passed for c in checks)
        failed_check = ""
        if not all_passed:
            # Get name of first failed check
            failed_check = next((c.check_name for c in checks if not c.passed), "")
            
        return Agent2Result(
            all_passed=all_passed,
            failed_check=failed_check,
            checks=checks,
            retrieval_results=retrieval_results,
            **kwargs
        )

    def _check_retrieval_relevance(self, query: str, results: list) -> EvaluationResult:
        """
        Check 1: Verified if the chunks are actually about the query using Gemini.
        """
        self.logger.info("Running Check 1: Retrieval Relevance...")
        if not results:
            return EvaluationResult(
                check_name="retrieval_relevance",
                passed=False,
                score=0.0,
                reason="No chunks to evaluate",
                suggestion="broaden_query"
            )
            
        yes_count = 0
        for r in results:
            try:
                # Round-robin key rotation
                client = genai.Client(api_key=get_gemini_key())
                
                # Use the 'text' attribute of RetrievalResult or dict
                text = r.text if hasattr(r, 'text') else r.get('text', '')
                
                prompt = (
                    f"Query: {query}\n"
                    f"Text: {text}\n\n"
                    f"Is this text directly relevant to answering the query? Reply only YES or NO."
                )
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                answer = response.text.strip().upper()
                
                if "YES" in answer:
                    yes_count += 1
                
                # Throttling
                time.sleep(0.3)
                
            except Exception as e:
                self.logger.warning(f"Gemini relevance check failed for chunk: {e}")
                # Requirement: assume YES on failure
                yes_count += 1
        
        ratio = yes_count / len(results)
        passed = ratio >= 0.6
        
        return EvaluationResult(
            check_name="retrieval_relevance",
            passed=passed,
            score=ratio,
            reason=f"{yes_count} of {len(results)} chunks relevant",
            suggestion="rewrite_query" if not passed else ""
        )

    def _check_completeness_grounding(self, query: str, results: list) -> tuple[EvaluationResult, list[str]]:
        """
        Check 2: Verified if the evidence is sufficient to answer the whole query.
        """
        self.logger.info("Running Check 2: Completeness Grounding...")
        
        evidence_text = ""
        for i, r in enumerate(results):
            text = r.text if hasattr(r, 'text') else r.get('text', '')
            evidence_text += f"{i+1}. {text}\n"

        prompt = (
            f"Query: {query}\n\n"
            f"Evidence chunks:\n{evidence_text}\n"
            f"Does this evidence collectively cover everything needed to fully answer the query?\n\n"
            f"Respond in JSON only:\n"
            f"{{\n  \"covered\": true or false,\n  \"coverage_gaps\": [list of missing aspects as short strings]\n}}\n\n"
            f"No explanation. JSON only."
        )

        try:
            client = genai.Client(api_key=get_gemini_key())
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            text = response.text.strip()
            
            # Clean JSON
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(text)
            covered = data.get("covered", True)
            gaps = data.get("coverage_gaps", [])
            
            return EvaluationResult(
                check_name="completeness_grounding",
                passed=covered,
                score=1.0 if covered else 0.0,
                reason="Evidence complete" if covered else f"Missing: {', '.join(gaps)}",
                suggestion="gap_analysis" if not covered else ""
            ), gaps

        except Exception as e:
            self.logger.warning(f"Gemini completeness check failed: {e}")
            # Requirement: assume covered=true on failure
            return EvaluationResult(
                check_name="completeness_grounding",
                passed=True,
                score=1.0,
                reason="Check failed, assumed covered",
                suggestion=""
            ), []

    def _check_freshness(self, classification, results: list) -> EvaluationResult:
        """
        Check 3: Non-LLM metadata check for temporal relevance.
        """
        self.logger.info("Running Check 3: Freshness...")
        self._live_fetch_needed = False
        
        # Check for LIVE_FETCH_SIGNAL sentinel first at the START of the method
        for r in results:
            cid = r.chunk_id if hasattr(r, "chunk_id") else (r.get("chunk_id", "") if isinstance(r, dict) else "")
            if cid == "LIVE_FETCH_SIGNAL":
                self.logger.info("Sentinel LIVE_FETCH_SIGNAL detected: triggering live fetch immediately.")
                self._live_fetch_needed = True
                return EvaluationResult(
                    check_name="freshness",
                    passed=False,
                    score=0.0,
                    reason="Temporal query: insufficient corpus coverage",
                    suggestion="live_fetch"
                )

        if not results:
            return EvaluationResult(
                check_name="freshness",
                passed=True,
                score=1.0,
                reason="No results to check",
                suggestion=""
            )

            
        # 1. Determine common topic cluster from results
        clusters = [r.topic_cluster if hasattr(r, 'topic_cluster') else r.get('topic_cluster', 'unknown') for r in results]
        main_cluster = max(set(clusters), key=clusters.count) if clusters else "default"
            
        # 2. Topic velocity thresholds
        thresholds = {
            "immunotherapy":     {"min_year": 2020, "min_freshness": 0.6},
            "drug_interactions": {"min_year": 2018, "min_freshness": 0.4},
            "genomics":          {"min_year": 2015, "min_freshness": 0.3},
            "default":           {"min_year": 2018, "min_freshness": 0.4}
        }
        
        t = thresholds.get(main_cluster, thresholds["default"])
        
        # 3. Count fresh chunks
        fresh_count = 0
        for r in results:
            year = r.year if hasattr(r, 'year') else r.get('year', 0)
            freshness = r.freshness_score if hasattr(r, 'freshness_score') else r.get('freshness_score', 0.0)
            contra = r.contradiction_flag if hasattr(r, 'contradiction_flag') else r.get('contradiction_flag', False)
            
            if year >= t["min_year"] and freshness >= t["min_freshness"] and not contra:
                fresh_count += 1
                
        # 4. Check requirement based on query type
        query_type = classification.query_type if hasattr(classification, 'query_type') else classification.get('query_type', 'simple_factual')
        required_count = 3 if query_type == "temporal" else 2
        
        passed = fresh_count >= required_count
        
        return EvaluationResult(
            check_name="freshness",
            passed=passed,
            score=fresh_count / len(results) if results else 0.0,
            reason=f"{fresh_count} of {len(results)} chunks meet freshness threshold",
            suggestion="live_fetch" if not passed else ""
        )

    def _check_calibration(self, results: list, user_id: str = "") -> tuple[EvaluationResult, float]:
        """
        Check 4: Metadata check to calibrate confidence based on Agent 6 learning curves.
        """
        self.logger.info("Running Check 4: Calibration...")
        if not results:
            return EvaluationResult(
                check_name="calibration",
                passed=True,
                score=0.5,
                reason="No results",
                suggestion=""
            ), 0.5
            
        # Step 1: Determine common topic cluster
        clusters = [r.topic_cluster if hasattr(r, 'topic_cluster') else r.get('topic_cluster', 'unknown') for r in results]
        main_cluster = max(set(clusters), key=clusters.count) if clusters else "immunotherapy"
        
        # Step 2: Read Agent 6 calibration
        try:
            from agents.agent6_learning import Agent6Learning
            agent6 = Agent6Learning()
            cal_point = agent6.get_calibration(main_cluster, user_id)
        except Exception as e:
            self.logger.warning(f"Failed to read from Agent 6: {e}")
            cal_point = None
            
        scores = [r.score if hasattr(r, 'score') else r.get('score', 0.0) for r in results]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        # Step 3: If calibration data exists
        if cal_point and cal_point.sample_size >= 5:
            calibrated = cal_point.actual_pass_rate * (0.5 + 0.5 * avg_score)
            expressed = cal_point.expressed_confidence
            self.logger.info(f"Using Agent 6 calibration for {main_cluster}: expressed={expressed:.2f} actual={cal_point.actual_pass_rate:.2f}")
            reason = f"Confidence {calibrated:.2f} dynamically calibrated by Agent 6 for {main_cluster}"
            
        # Step 4: Fallback
        else:
            self.logger.info(f"No Agent 6 calibration yet for {main_cluster} - using corpus count fallback")
            try:
                from database.supabase_client import SupabaseManager
                sb = SupabaseManager()
                response = sb.client.table("ingestion_logs").select("id", count="exact").eq("topic_cluster", main_cluster).eq("status", "success").execute()
                count = response.count if response.count is not None else 0
            except Exception as e:
                self.logger.warning(f"Supabase calibration query failed: {e}")
                count = -1
                
            if count >= 500: base = 0.90
            elif count >= 200: base = 0.82
            elif count >= 100: base = 0.75
            elif count >= 50:  base = 0.65
            elif count >= 0:   base = 0.50
            else:              base = 0.70
            
            calibrated = base * (0.5 + 0.5 * avg_score)
            expressed = calibrated
            reason = f"Confidence {calibrated:.2f} based on corpus size fallback"
            
        # Step 5: Cap at 0.95 maximum
        calibrated = min(calibrated, 0.95)
        
        # Step 6: Log drift warning
        diff = abs(expressed - calibrated)
        if diff > 0.15:
            self.logger.warning(f"Calibration drift detected: {main_cluster} expressed {expressed:.2f} but calibrated to {calibrated:.2f}")

        # Calculate confidence interval:
        sample_size = cal_point.sample_size if cal_point else 0
        import math
        p = calibrated
        n = sample_size
        
        if n >= 30:
            z = 1.96
            center = (p + (z*z)/(2*n)) / (1 + (z*z)/n)
            margin = z * math.sqrt(p*(1-p)/n + (z*z)/(4*n*n)) / (1 + (z*z)/n)
            lower = max(0.0, center - margin)
            upper = min(1.0, center + margin)
        elif n >= 10:
            margin = 1.96 * math.sqrt(p*(1-p)/n)
            lower = max(0.0, p - margin)
            upper = min(1.0, p + margin)
        else:
            lower = max(0.0, p - 0.20)
            upper = min(1.0, p + 0.20)

        return EvaluationResult(
            check_name="calibration",
            passed=True,
            score=calibrated,
            reason=reason,
            suggestion="",
            confidence_lower=lower,
            confidence_upper=upper
        ), calibrated

    def _check_cross_chunk_contradiction(self, results: list) -> tuple[EvaluationResult, bool, list[str]]:
        """
        Check 5: LLM check to see if retrieved chunks disagree with each other.
        """
        self.logger.info("Running Check 5: Cross-Chunk Contradiction...")
        if len(results) < 3:
            return EvaluationResult(
                check_name="cross_chunk_contradiction",
                passed=True,
                score=1.0,
                reason="Too few chunks to check for contradictions",
                suggestion=""
            ), False, []
            
        evidence_text = ""
        chunk_map = {}
        paper_map = {}
        topic_map = {}
        for i, r in enumerate(results):
            text = r.text if hasattr(r, 'text') else r.get('text', '')
            c_id = r.chunk_id if hasattr(r, 'chunk_id') else r.get('chunk_id', f"chunk_{i}")
            p_id = r.paper_id if hasattr(r, 'paper_id') else r.get('paper_id', '')
            t_c = r.topic_cluster if hasattr(r, 'topic_cluster') else r.get('topic_cluster', 'immunotherapy')
            evidence_text += f"{i}. {text}\n"
            chunk_map[i] = c_id
            paper_map[i] = p_id
            topic_map[i] = t_c

        prompt = (
            f"Do any of these texts make contradictory factual claims?\n\n"
            f"{evidence_text}\n"
            f"Respond JSON only:\n"
            f"{{\n  \"contradiction_found\": true or false,\n  \"conflicting_pairs\": [[index_a, index_b]]\n}}"
        )

        try:
            client = genai.Client(api_key=get_gemini_key())
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            text = response.text.strip()
            
            # Clean JSON
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
                
            data = json.loads(text)
            found = data.get("contradiction_found", False)
            pairs = data.get("conflicting_pairs", [])
            
            contra_ids = []
            reason = "No contradictions"
            if found and pairs:
                for a, b in pairs:
                    if a in chunk_map: contra_ids.append(chunk_map[a])
                    if b in chunk_map: contra_ids.append(chunk_map[b])
                    
                    # Log to Neo4j
                    p_a = paper_map.get(a)
                    p_b = paper_map.get(b)
                    if p_a and p_b and p_a != p_b:
                        try:
                            from database.neo4j_client import Neo4jManager
                            neo4j = Neo4jManager()
                            neo4j.create_contradiction_relationship(
                                paper_id_a=p_a,
                                paper_id_b=p_b,
                                confidence=0.75,
                                topic=topic_map.get(a, "immunotherapy")
                            )
                        except Exception as neo_err:
                            self.logger.warning(f"Neo4j contradiction logging failed: {neo_err}")
                            
                reason = f"Contradiction between chunks {', '.join(set(contra_ids))}"
                
            return EvaluationResult(
                check_name="cross_chunk_contradiction",
                passed=True, # Informational
                score=0.0 if found else 1.0,
                reason=reason,
                suggestion=""
            ), found, list(set(contra_ids))

        except Exception as e:
            self.logger.warning(f"Gemini contradiction check failed: {e}")
            return EvaluationResult(
                check_name="cross_chunk_contradiction",
                passed=True,
                score=1.0,
                reason="Check failed, assumed no contradiction",
                suggestion=""
            ), False, []

    def _check_batch_relevance(self, query: str, results: list) -> EvaluationResult:
        """
        Check 1 (Batch): Verified if the chunks are actually about the query using Gemini in a single batch call.
        """
        self.logger.info("Running Check 1: Batch Retrieval Relevance...")
        if not results:
            return EvaluationResult(
                check_name="retrieval_relevance",
                passed=False,
                score=0.0,
                reason="No chunks to evaluate",
                suggestion="broaden_query"
            )
            
        evidence_text = ""
        for i, r in enumerate(results):
            text = r.text if hasattr(r, 'text') else r.get('text', '')
            evidence_text += f"Chunk {i}: {text}\n\n"
            
        prompt = (
            f"Query: {query}\n\n"
            f"Evidence Chunks:\n{evidence_text}\n"
            f"For each chunk, determine if it is directly relevant to answering the query. "
            f"Respond in JSON format as a list of boolean values indicating relevance (true/false) for each chunk in order.\n"
            f"Example format:\n"
            f"[true, false, true]\n"
            f"Do not include any explanation. Respond ONLY with the JSON array."
        )
        
        try:
            client = genai.Client(api_key=get_gemini_key())
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            text = response.text.strip()
            
            # Clean JSON
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
                
            relevance_list = json.loads(text)
            if not isinstance(relevance_list, list):
                raise ValueError("Relevance output is not a JSON list")
                
            # If the list length doesn't match results length, try to pad or truncate
            if len(relevance_list) < len(results):
                relevance_list += [True] * (len(results) - len(relevance_list))
            elif len(relevance_list) > len(results):
                relevance_list = relevance_list[:len(results)]
                
            yes_count = sum(1 for is_rel in relevance_list if is_rel)
        except Exception as e:
            self.logger.warning(f"Batch relevance check failed, falling back to all-relevant: {e}")
            yes_count = len(results)
            
        ratio = yes_count / len(results) if results else 0.0
        passed = ratio >= 0.6
        
        return EvaluationResult(
            check_name="retrieval_relevance",
            passed=passed,
            score=ratio,
            reason=f"{yes_count} of {len(results)} chunks relevant",
            suggestion="rewrite_query" if not passed else ""
        )

    def _check_contradiction(self, query: str, results: list) -> tuple[EvaluationResult, bool, list[str]]:
        return self._check_cross_chunk_contradiction(results)

    def _check_consolidated_quality(self, query: str, results: list) -> tuple[EvaluationResult, EvaluationResult, tuple[EvaluationResult, bool, list[str]], list[str]]:
        """
        Runs batch relevance, completeness grounding, and cross-chunk contradiction checks
        consolidated into a single, highly optimized LLM call to save API costs and latency.
        """
        self.logger.info("Running Consolidated Quality Check (Relevance + Completeness + Contradiction)...")
        if not results:
            fallback_rel = EvaluationResult(check_name="retrieval_relevance", passed=False, score=0.0, reason="No chunks to evaluate", suggestion="broaden_query")
            fallback_comp = EvaluationResult(check_name="completeness_grounding", passed=False, score=0.0, reason="No chunks to evaluate", suggestion="broaden_query")
            fallback_contra = EvaluationResult(check_name="cross_chunk_contradiction", passed=True, score=1.0, reason="No chunks to evaluate", suggestion="")
            return fallback_rel, fallback_comp, (fallback_contra, False, []), []

        evidence_text = ""
        chunk_map = {}
        paper_map = {}
        topic_map = {}
        for i, r in enumerate(results):
            text = r.text if hasattr(r, 'text') else r.get('text', '')
            c_id = r.chunk_id if hasattr(r, 'chunk_id') else r.get('chunk_id', f"chunk_{i}")
            p_id = r.paper_id if hasattr(r, 'paper_id') else r.get('paper_id', '')
            t_c = r.topic_cluster if hasattr(r, 'topic_cluster') else r.get('topic_cluster', 'immunotherapy')
            evidence_text += f"Chunk {i}: {text}\n\n"
            chunk_map[i] = c_id
            paper_map[i] = p_id
            topic_map[i] = t_c

        prompt = f"""You are an advanced biomedical Quality Gate system. Analyze the following retrieved evidence chunks against the user query.

Query: {query}

Evidence Chunks:
{evidence_text}

You must evaluate three criteria:
1. Relevance: For each chunk in order, determine if it is directly relevant to answering the query.
2. Completeness: Does this evidence collectively cover everything needed to fully answer the query? If not, identify the specific coverage gaps.
3. Cross-Chunk Contradiction: Do any of these chunks make mutually exclusive or contradictory factual claims with one another? If yes, identify the conflicting chunk index pairs.

Respond in JSON format ONLY matching the following schema exactly:
{{
  "relevance": [true, false, true],
  "completeness": {{
    "covered": true,
    "coverage_gaps": []
  }},
  "contradiction": {{
    "contradiction_found": false,
    "conflicting_pairs": []
  }}
}}

Rules:
- The "relevance" list length must match the number of chunks ({len(results)}) exactly.
- "conflicting_pairs" must be a list of lists of index integers, e.g., [[0, 2]] if Chunk 0 and Chunk 2 contradict.
- Respond with standard JSON ONLY. Do not include markdown code block formatting (like ```json). No explanation."""

        try:
            client = genai.Client(api_key=get_gemini_key())
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            text = response.text.strip()
            
            # Clean JSON
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
                
            data = json.loads(text)
            
            # 1. Parse Relevance
            relevance_list = data.get("relevance", [])
            if len(relevance_list) < len(results):
                relevance_list += [True] * (len(results) - len(relevance_list))
            else:
                relevance_list = relevance_list[:len(results)]
            yes_count = sum(1 for is_rel in relevance_list if is_rel)
            ratio = yes_count / len(results) if results else 0.0
            rel_passed = ratio >= 0.6
            rel_res = EvaluationResult(
                check_name="retrieval_relevance",
                passed=rel_passed,
                score=ratio,
                reason=f"{yes_count} of {len(results)} chunks relevant",
                suggestion="rewrite_query" if not rel_passed else ""
            )
            
            # 2. Parse Completeness
            comp_data = data.get("completeness", {})
            covered = comp_data.get("covered", True)
            gaps = comp_data.get("coverage_gaps", [])
            comp_res = EvaluationResult(
                check_name="completeness_grounding",
                passed=covered,
                score=1.0 if covered else 0.0,
                reason="Evidence complete" if covered else f"Missing: {', '.join(gaps)}",
                suggestion="gap_analysis" if not covered else ""
            )
            
            # 3. Parse Contradiction
            contra_data = data.get("contradiction", {})
            found = contra_data.get("contradiction_found", False)
            pairs = contra_data.get("conflicting_pairs", [])
            
            contra_ids = []
            reason = "No contradictions"
            if found and pairs:
                for pair in pairs:
                    if len(pair) >= 2:
                        a, b = pair[0], pair[1]
                        if a in chunk_map: contra_ids.append(chunk_map[a])
                        if b in chunk_map: contra_ids.append(chunk_map[b])
                        
                        # Log to Neo4j
                        p_a = paper_map.get(a)
                        p_b = paper_map.get(b)
                        if p_a and p_b and p_a != p_b:
                            try:
                                from database.neo4j_client import Neo4jManager
                                neo4j = Neo4jManager()
                                neo4j.create_contradiction_relationship(
                                    paper_id_a=p_a,
                                    paper_id_b=p_b,
                                    confidence=0.75,
                                    topic=topic_map.get(a, "immunotherapy")
                                )
                            except Exception as neo_err:
                                self.logger.warning(f"Neo4j contradiction logging failed: {neo_err}")
                reason = f"Contradiction between chunks {', '.join(set(contra_ids))}"
                
            contra_res = EvaluationResult(
                check_name="cross_chunk_contradiction",
                passed=True,  # Informational
                score=0.0 if found else 1.0,
                reason=reason,
                suggestion=""
            )
            
            return rel_res, comp_res, (contra_res, found, list(set(contra_ids))), gaps
            
        except Exception as e:
            self.logger.warning(f"Consolidated quality check failed, falling back: {e}")
            # Fallbacks
            fallback_rel = EvaluationResult(check_name="retrieval_relevance", passed=True, score=1.0, reason="Assumed relevant on fallback", suggestion="")
            fallback_comp = EvaluationResult(check_name="completeness_grounding", passed=True, score=1.0, reason="Assumed covered on fallback", suggestion="")
            fallback_contra = EvaluationResult(check_name="cross_chunk_contradiction", passed=True, score=1.0, reason="Assumed no contradiction on fallback", suggestion="")
            return fallback_rel, fallback_comp, (fallback_contra, False, []), []

    async def evaluate(self,
                 query: str, 
                 classification, 
                 retrieval_results: list,
                 user_id: str = ""):
        from agents.models import Agent2Result
        import asyncio
        self.logger.info(f"Evaluating quality for {len(retrieval_results)} retrieved chunks...")
        
        try:
            self._live_fetch_needed = False

            has_sentinel = False
            for r in retrieval_results:
                cid = r.chunk_id if hasattr(r, "chunk_id") else (r.get("chunk_id", "") if isinstance(r, dict) else "")
                if cid == "LIVE_FETCH_SIGNAL":
                    has_sentinel = True
                    break
                    
            clean_results = [r for r in retrieval_results if not (hasattr(r, "chunk_id") and getattr(r, "chunk_id") == "LIVE_FETCH_SIGNAL")]
            
            # Check 3 (Freshness) and Check 4 (Calibration) are metadata/db operations, run concurrently with consolidated prompt check
            fresh_task = asyncio.to_thread(self._check_freshness, classification, clean_results)
            cal_task = asyncio.to_thread(self._check_calibration, clean_results, user_id)
            consolidated_task = asyncio.to_thread(self._check_consolidated_quality, query, clean_results)
            
            res = await asyncio.gather(fresh_task, cal_task, consolidated_task)
            fresh_res, cal_res_tuple, consolidated_res = res
            
            cal_res, cal_conf = cal_res_tuple
            rel_res, comp_res, contra_res_tuple, coverage_gaps = consolidated_res
            contra_res, contra_found, contra_chunks = contra_res_tuple
            
            checks = [rel_res, comp_res, fresh_res, cal_res, contra_res]
            
            if rel_res.score >= 0.70 and comp_res.passed:
                all_passed = True
                failed_check = "none"
                self.logger.info("FAST-TRACK: Relevance >= 0.70 and completeness passed. Bypassing Agent 3.")
            else:
                all_passed = all(c.passed for c in [rel_res, comp_res, fresh_res, cal_res])
                failed_check = next((c.check_name for c in checks if not c.passed), "")
                
            return Agent2Result(
                all_passed=all_passed,
                failed_check=failed_check,
                checks=checks,
                calibrated_confidence=cal_conf,
                confidence_lower=max(0.0, cal_conf - 0.2),
                confidence_upper=min(1.0, cal_conf + 0.2),
                contradiction_found=contra_found,
                contradicting_chunks=contra_chunks,
                live_fetch_needed=self._live_fetch_needed or has_sentinel,
                coverage_gaps=coverage_gaps,
                retrieval_results=clean_results
            )
            
        except Exception as e:
            self.logger.error(f"Agent 2 evaluation pipeline failed: {e}")
            return Agent2Result(
                all_passed=False,
                failed_check="pipeline_error",
                checks=[],
                calibrated_confidence=0.0
            )

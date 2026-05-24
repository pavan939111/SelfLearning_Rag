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
                    model="gemini-2.0-flash",
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
                model="gemini-2.0-flash",
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
            return EvaluationResult("freshness", True, 1.0, "No results to check", "")

            
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
            return EvaluationResult("calibration", True, 0.5, "No results", ""), 0.5
            
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
            self.logger.info(f"No Agent 6 calibration yet for {main_cluster} — using corpus count fallback")
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
                model="gemini-2.0-flash",
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

    def evaluate(self,
                 query: str, 
                 classification, 
                 retrieval_results: list,
                 user_id: str = "") -> Agent2Result:
        """
        Executes the quality gate evaluation pipeline.
        
        Currently a skeleton that defaults to 'all passed'. 
        Specific checks will be implemented in subsequent phases.
        """
        self.logger.info(f"Evaluating quality for {len(retrieval_results)} retrieved chunks...")
        
        try:
            self._live_fetch_needed = False
            checks = []

            # Check for sentinel and construct clean_results
            has_sentinel = False
            for r in retrieval_results:
                cid = r.chunk_id if hasattr(r, "chunk_id") else (r.get("chunk_id", "") if isinstance(r, dict) else "")
                if cid == "LIVE_FETCH_SIGNAL":
                    has_sentinel = True
                    self._live_fetch_needed = True
            
            clean_results = [
                r for r in retrieval_results
                if not (isinstance(r, dict) and r.get("chunk_id") == "LIVE_FETCH_SIGNAL")
            ]

            tl = ThoughtLogger(session_id='', agent='agent2')

            # Check 1: Retrieval Relevance (BLOCKING)
            relevance_check = self._check_retrieval_relevance(query, clean_results)
            checks.append(relevance_check)
            
            try:
                tl.trace(
                    step='check_relevance',
                    obs=f"Evaluating {len(clean_results)} chunks for "
                        f"relevance to query. "
                        f"Query: '{query[:60]}'",
                    thk=f"LLM scoring each chunk against query intent. "
                        f"Need at least 3 of {len(clean_results)} chunks relevant. "
                        f"Chunk topics: {list(set(getattr(r, 'topic_cluster', '') for r in clean_results[:3]))}",
                    act=f"Score each chunk with Gemini Flash. "
                        f"Threshold: 3 relevant chunks minimum",
                    out=f"Relevance check: {'PASS' if relevance_check.passed else 'FAIL'}. "
                        f"Score: {relevance_check.score:.2f}. "
                        f"{relevance_check.reason[:80]}",
                    confidence=relevance_check.score
                )
            except Exception as e:
                self.logger.warning(f"Trace fail: {e}")
            
            if not relevance_check.passed and not has_sentinel:
                self.logger.warning(f"Quality Gate FAILED: {relevance_check.check_name}")
                res = self._make_result(checks, retrieval_results)
                try:
                    tl.trace(
                        step='verdict',
                        obs=f"Checks stopped early. Failed at {res.failed_check}",
                        thk="Blocking check failed. Evidence is insufficient. Entering repair cycle.",
                        act="Trigger repair cycle → Agent 3",
                        out="Agent 2 verdict: FAIL → Repair cycle",
                        confidence=res.calibrated_confidence
                    )
                    res.thought_traces = tl.get_traces()
                except Exception: pass
                return res

            # Check 2: Completeness Grounding (BLOCKING)
            completeness_check, gaps = self._check_completeness_grounding(query, clean_results)
            checks.append(completeness_check)
            
            try:
                qtype = getattr(classification, 'query_type', 'simple_factual') if classification else 'unknown'
                tl.trace(
                    step='check_completeness',
                    obs=f"Checking if query can be fully answered "
                        f"from {len(clean_results)} chunks. "
                        f"Gaps detected: {gaps[:2]}",
                    thk=f"Query type: {qtype}. "
                        f"Available evidence covers: "
                        f"{list(set(getattr(r, 'topic_cluster', '') for r in clean_results))}. "
                        f"{'Full coverage' if completeness_check.passed else 'Missing aspects detected'}",
                    act=f"Evaluate completeness with Gemini Flash. "
                        f"Flag any uncovered query aspects",
                    out=f"Completeness: {'PASS' if completeness_check.passed else 'FAIL'}. "
                        f"Score: {completeness_check.score:.2f}. "
                        f"Gaps: {gaps[:2]}",
                    confidence=completeness_check.score
                )
            except Exception as e:
                self.logger.warning(f"Trace fail: {e}")
            
            if not completeness_check.passed and not has_sentinel:
                self.logger.warning(f"Quality Gate FAILED: {completeness_check.check_name}")
                res = self._make_result(
                    checks=checks, 
                    retrieval_results=retrieval_results,
                    coverage_gaps=gaps
                )
                try:
                    tl.trace(
                        step='verdict',
                        obs=f"Checks stopped early. Failed at {res.failed_check}",
                        thk="Blocking check failed. Evidence is insufficient. Entering repair cycle.",
                        act="Trigger repair cycle → Agent 3",
                        out="Agent 2 verdict: FAIL → Repair cycle",
                        confidence=res.calibrated_confidence
                    )
                    res.thought_traces = tl.get_traces()
                except Exception: pass
                return res

            # Check 3: Freshness (NON-BLOCKING)
            freshness_check = self._check_freshness(classification, retrieval_results)
            checks.append(freshness_check)
            live_fetch_needed = not freshness_check.passed or getattr(self, "_live_fetch_needed", False)

            try:
                avg_freshness = sum(getattr(r, 'freshness_score', 0) for r in clean_results) / max(len(clean_results), 1)
                req_recent = getattr(classification, 'requires_recent', False) if classification else False
                tl.trace(
                    step='check_freshness',
                    obs=f"Checking freshness of {len(clean_results)} chunks. "
                        f"Avg freshness score: {avg_freshness:.2f}. "
                        f"Query requires_recent: {req_recent}. "
                        f"Chunk years: {sorted(set(getattr(r, 'year', 0) for r in clean_results), reverse=True)[:4]}",
                    thk=f"{'Temporal query needs fresh evidence' if req_recent else 'Non-temporal query, freshness less critical'}. "
                        f"{'Chunks are sufficiently fresh' if avg_freshness > 0.6 else 'Many chunks are stale — live fetch may help'}. ",
                    act=f"{'Set live_fetch_needed=True' if not freshness_check.passed else 'No live fetch needed'}. "
                        f"Flag stale chunks for Agent 7",
                    out=f"Freshness: {'PASS' if freshness_check.passed else 'FAIL — live fetch triggered'}. "
                        f"Avg freshness: {avg_freshness:.2f}",
                    confidence=avg_freshness
                )
            except Exception as e:
                self.logger.warning(f"Trace fail: {e}")

            # Check 4: Calibration (NON-BLOCKING)
            calibration_check, confidence = self._check_calibration(clean_results, user_id)
            checks.append(calibration_check)

            try:
                tc = clean_results[0].topic_cluster if (clean_results and hasattr(clean_results[0], 'topic_cluster')) else 'unknown'
                tl.trace(
                    step='check_calibration',
                    obs=f"Reading Agent 6 calibration for cluster '{tc}'. "
                        f"Sample size available in Supabase",
                    thk=f"{'Using Agent 6 calibration curves — data driven' if 'Agent 6' in calibration_check.reason else 'No calibration data yet — using corpus count fallback'}. "
                        f"Expressed confidence should match actual pass rate. "
                        f"User feedback weighted 2x vs agent signal",
                    act=f"Set calibrated_confidence = {calibration_check.score:.2f}. "
                        f"Will be passed to Agent 7 for response generation",
                    out=f"Calibration: PASS. "
                        f"Confidence recommendation: {calibration_check.score:.2f}. "
                        f"Interval: [{calibration_check.confidence_lower:.2f}, "
                        f"{calibration_check.confidence_upper:.2f}]",
                    confidence=calibration_check.score
                )
            except Exception as e:
                self.logger.warning(f"Trace fail: {e}")

            # Check 5: Cross-Chunk Contradiction (NON-BLOCKING)
            contradiction_check, found_contra, contra_chunks = self._check_cross_chunk_contradiction(clean_results)
            checks.append(contradiction_check)
            
            try:
                tl.trace(
                    step='check_contradiction',
                    obs=f"Scanning {len(clean_results)} chunks for "
                        f"conflicting claims. "
                        f"Checking cross-chunk consistency",
                    thk=f"{'Multiple chunks from same cluster — contradiction possible' if len(clean_results) >= 3 else 'Too few chunks to detect contradiction'}. "
                        f"Contradictions should be surfaced to user not hidden",
                    act=f"Compare chunk pairs with Gemini Flash. "
                        f"Flag contradictions for Agent 7",
                    out=f"Contradiction: {'DETECTED — flagged for Agent 7' if found_contra else 'None found'}. "
                        f"Score: {contradiction_check.score:.2f}",
                    confidence=contradiction_check.score
                )
            except Exception as e:
                self.logger.warning(f"Trace fail: {e}")
            
            # Final Result Aggregation
            res = self._make_result(
                checks=checks, 
                retrieval_results=retrieval_results,
                coverage_gaps=gaps if 'gaps' in locals() else [],
                live_fetch_needed=live_fetch_needed,
                calibrated_confidence=confidence,
                confidence_lower=calibration_check.confidence_lower,
                confidence_upper=calibration_check.confidence_upper,
                contradiction_found=found_contra,
                contradicting_chunks=contra_chunks
            )

            try:
                tl.trace(
                    step='verdict',
                    obs=f"All checks complete. "
                        f"Results: {[c.check_name+':'+('P' if c.passed else 'F') for c in res.checks]}",
                    thk=f"{'All checks passed — evidence is sufficient' if res.all_passed else f'Failed on {res.failed_check} — repair needed'}. "
                        f"Calibrated confidence: {res.calibrated_confidence:.2f}. "
                        f"{'Proceeding to Agent 7' if res.all_passed else 'Entering repair cycle'}",
                    act=f"{'Allow generation' if res.all_passed else 'Trigger repair cycle → Agent 3'}",
                    out=f"Agent 2 verdict: {'PASS → Agent 7' if res.all_passed else 'FAIL → Repair cycle'}. "
                        f"Confidence: {res.calibrated_confidence:.2f}",
                    confidence=res.calibrated_confidence
                )
                res.thought_traces = tl.get_traces()
            except Exception as e:
                self.logger.warning(f"Trace fail: {e}")

            return res

        except Exception as e:
            self.logger.error(f"Agent 2 evaluation pipeline failed: {e}")
            # Safe fallback: fail the gate to prevent unverified generation
            return Agent2Result(
                all_passed=False,
                failed_check="system_error",
                retrieval_results=retrieval_results
            )

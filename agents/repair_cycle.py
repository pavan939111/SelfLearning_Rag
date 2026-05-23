from agents.models import (
    CycleResult, DiagnosisResult, FormulationResult
)
from pydantic import ValidationError

from config import get_config
from utils.logger import get_logger
from agents.agent2_evaluator import Agent2Evaluator
from agents.agent3_classifier import Agent3Classifier
from agents.agent4a_formulator import Agent4AFormulator
from agents.agent1_retrieval import HybridRetriever

class RepairCycle:
    """
    Orchestrates the A2->A3->A4A internal repair cycle.
    Attempts to iteratively improve retrieval quality up to max_iterations.
    """
    def __init__(self, max_iterations: int = 2):
        self.config = get_config()
        self.logger = get_logger(__name__)
        self.max_iterations = max_iterations
        
        # Instantiate agents
        self.evaluator = Agent2Evaluator()
        self.agent3 = Agent3Classifier()
        self.agent4a = Agent4AFormulator()
        self.retriever = HybridRetriever()

    def _deduplicate_chunks(self, chunks: list) -> list:
        """Removes duplicate chunks based on chunk_id."""
        seen_ids = set()
        unique = []
        for c in chunks:
            cid = getattr(c, 'chunk_id', None) if hasattr(c, 'chunk_id') else c.get('chunk_id', '')
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                unique.append(c)
            elif not cid:
                # If no ID, append it anyway to avoid losing data
                unique.append(c)
        return unique
        
    def _get_avg_score(self, chunks: list) -> float:
        """Helper to calculate average score for best-effort fallback."""
        if not chunks:
            return 0.0
        scores = [getattr(c, 'score', 0.0) if hasattr(c, 'score') else c.get('score', 0.0) for c in chunks]
        return sum(scores) / len(scores)

    def run(self, query: str, classification, initial_results: list, session_id: str = "unknown") -> CycleResult:
        self.logger.info("Starting Autonomous Repair Cycle...")
        
        try:
            current_chunks = initial_results.copy()
            all_chunks_seen = self._deduplicate_chunks(initial_results.copy())
            diagnosis_history = []
            
            best_chunks_so_far = current_chunks.copy()
            best_score = self._get_avg_score(best_chunks_so_far)
            
            iterations = 0
            
            while True:
                # Step 1: Run Agent 2 (Quality Gate)
                agent2_result = self.evaluator.evaluate(query, classification, current_chunks)
                
                # Step 2: Check Exit Conditions
                # EXIT 1: Agent 2 Passes
                if agent2_result.all_passed:
                    self.logger.info(f"Cycle {iterations}: exit=agent2_passed chunks={len(current_chunks)}")
                    return CycleResult(
                        final_chunks=current_chunks,
                        agent2_result=agent2_result,
                        iterations_run=iterations,
                        exit_reason="agent2_passed",
                        diagnosis_history=diagnosis_history,
                        all_chunks_seen=all_chunks_seen
                    )
                    
                # EXIT 2: Max Iterations Reached
                if iterations >= self.max_iterations:
                    self.logger.warning(f"Cycle {iterations}: exit=max_cycles chunks={len(best_chunks_so_far)}")
                    return CycleResult(
                        final_chunks=best_chunks_so_far,
                        agent2_result=agent2_result,
                        iterations_run=iterations,
                        exit_reason="max_cycles",
                        diagnosis_history=diagnosis_history,
                        all_chunks_seen=all_chunks_seen
                    )
                    
                # Step 3: Run Agent 3 Diagnosis
                try:
                    diagnosis = self.agent3.diagnose(query, classification, current_chunks, agent2_result)
                except ValidationError as e:
                    self.logger.error(f"Agent 3 returned invalid data: {e}")
                    diagnosis = DiagnosisResult(
                        failure_class='C',
                        root_cause='unknown',
                        confidence=0.5,
                        route_to='escalate'
                    )
                diagnosis_history.append(diagnosis)
                
                # EXIT 3: Class A or B Diagnosis (External problem, internal repair won't help)
                # If it's routed anywhere except 4A, we must exit
                if diagnosis.route_to != "4A":
                    self.logger.info(f"Cycle {iterations}: exit=class_ab_exit chunks={len(current_chunks)}")
                    
                    agent4b_action = "none"
                    try:
                        from agents.agent4b_repair import Agent4BRepair
                        agent4b = Agent4BRepair()
                        queue_result = agent4b.queue_repair(diagnosis, query, session_id)
                        agent4b_action = queue_result.get("action", "none")
                    except Exception as e:
                        self.logger.error(f"Failed to invoke Agent 4B: {e}")
                        
                    return CycleResult(
                        final_chunks=current_chunks,
                        agent2_result=agent2_result,
                        iterations_run=iterations,
                        exit_reason="class_ab_exit",
                        diagnosis_history=diagnosis_history,
                        all_chunks_seen=all_chunks_seen,
                        agent4b_action=agent4b_action
                    )
                    
                # Step 4: Run Agent 4A Formulation
                self.logger.info(f"Cycle {iterations}: Running Agent 4A Formulation...")
                try:
                    formulation = self.agent4a.formulate(query, classification, current_chunks, agent2_result, diagnosis)
                except ValidationError as e:
                    self.logger.error(f"Agent 4A returned invalid data: {e}")
                    formulation = FormulationResult(
                        original_query=query,
                        gaps_identified=['unknown']
                    )
                
                if getattr(formulation, "used_live_fetch", False):
                    if formulation.live_fetch_result and formulation.live_fetch_result.success:
                        live_chunks = formulation.live_fetch_result.chunks_returned
                        
                        existing_ids = set()
                        for c in current_chunks:
                            cid = ""
                            if isinstance(c, dict):
                                cid = c.get('chunk_id', '')
                            elif hasattr(c, 'chunk_id'):
                                cid = getattr(c, 'chunk_id', '')
                            if cid:
                                existing_ids.add(cid)
                                
                        new_chunks = [
                            c for c in live_chunks
                            if c.get('chunk_id', '') not in existing_ids
                        ]
                        
                        # Merge live chunks with current chunks
                        current_chunks = list(current_chunks) + new_chunks
                        all_chunks_seen.extend(new_chunks)
                        
                        self.logger.info(
                            f"Merged {len(new_chunks)} live chunks "
                            f"with {len(current_chunks) - len(new_chunks)} "
                            f"existing chunks"
                        )
                    else:
                        self.logger.warning(
                            "Live fetch failed — continuing with original chunks"
                        )
                    
                    # Continue to next iteration of cycle
                    # Agent 2 will re-evaluate the merged chunks
                    iterations += 1
                    continue
                
                # Step 5: Re-retrieve using Agent 4A sub-queries
                new_chunks = []
                for sq in formulation.sub_queries:
                    sq_results = self.retriever.retrieve(
                        query=sq.query_text,
                        classification=classification,
                        filter_config=sq.filter_config,
                        top_k=5
                    )
                    new_chunks.extend(sq_results)
                    
                # Step 6: MERGE and DEDUPLICATE
                combined = current_chunks + new_chunks
                current_chunks = self._deduplicate_chunks(combined)
                
                # Keep top 10 chunks to avoid context bloat
                def get_score(c):
                    return getattr(c, 'fusion_score', getattr(c, 'score', 0.0)) if hasattr(c, 'fusion_score') or hasattr(c, 'score') else c.get('fusion_score', c.get('score', 0.0))
                
                current_chunks = sorted(current_chunks, key=get_score, reverse=True)[:10]
                
                # Update trackers
                all_chunks_seen = self._deduplicate_chunks(all_chunks_seen + current_chunks)
                
                curr_score = self._get_avg_score(current_chunks)
                if curr_score > best_score:
                    best_score = curr_score
                    best_chunks_so_far = current_chunks.copy()
                
                # Step 7: Increment
                iterations += 1

        except Exception as e:
            self.logger.error(f"Repair Cycle crashed: {e}")
            # Fallback safely
            return CycleResult(
                final_chunks=initial_results,
                agent2_result=None,
                iterations_run=0,
                exit_reason="system_error",
                diagnosis_history=[],
                all_chunks_seen=initial_results
            )

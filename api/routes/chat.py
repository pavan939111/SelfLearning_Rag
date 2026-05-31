import time
import asyncio
import json
from pydantic import BaseModel
from typing import Optional
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.models.requests import ChatRequest
from api.models.responses import ChatResponse
from config import get_config
from utils.logger import get_logger

# Import LangGraph compiled graph
from agents.orchestrator import app_graph, AgentState

# Import Agents & Tools
from agents.agent1_retrieval import QueryClassifier, MetadataPreFilter, HybridRetriever
from agents.agent2_evaluator import Agent2Evaluator
from agents.agent7_generator import Agent7Generator
from agents.conversation_memory import ConversationMemory, SessionTopicModel, FollowUpResolver
from agents.cache_manager import CacheManager
from ingestion.embedder import BiomedicalEmbedder
from agents.agent6_learning import Agent6Learning
from database.neo4j_client import Neo4jManager

logger = get_logger(__name__)
router = APIRouter()

# Initialize singletons ONCE at module level to prevent memory leaks / slow cold starts
logger.info("Initializing agents for Chat Route...")
classifier = QueryClassifier()
pre_filter = MetadataPreFilter()
retriever = HybridRetriever()
evaluator = Agent2Evaluator()
generator = Agent7Generator()
memory = ConversationMemory()
topic_model = SessionTopicModel()
resolver = FollowUpResolver()
cache = CacheManager()
embedder = BiomedicalEmbedder()
agent6 = Agent6Learning()
neo4j_manager = Neo4jManager()

class FeedbackRequest(BaseModel):
    session_id: str
    query: str
    answer: str
    rating: int
    topic_cluster: Optional[str] = None
    confidence: Optional[float] = None
    cycle_ran: Optional[bool] = None
    cache_hit: Optional[bool] = None
    user_id: Optional[str] = None

async def _observe_async(session_id, query, classification, agent2_result, cycle_result):
    try:
        agent6.observe_query_result(
            session_id, query, classification,
            agent2_result, cycle_result
        )
    except Exception:
        pass

def _filter_speculative_results(results: list, filter_config) -> list:
    if not filter_config:
        return results
        
    matched = []
    for chunk in results:
        mismatch = False
        
        # Check topic cluster if specified
        if filter_config.topic_cluster:
            cluster = getattr(chunk, 'topic_cluster', '') if not isinstance(chunk, dict) else chunk.get('topic_cluster', '')
            if cluster != filter_config.topic_cluster:
                mismatch = True
                
        # Check min_year
        if filter_config.min_year is not None:
            year = getattr(chunk, 'year', 0) if not isinstance(chunk, dict) else chunk.get('year', 0)
            if year < filter_config.min_year:
                mismatch = True
                
        # Check must_conditions manually if any are different
        for cond in filter_config.must_conditions:
            key = cond.get("key")
            if key == "topic_cluster":
                expected = cond.get("match")
                actual = getattr(chunk, 'topic_cluster', '') if not isinstance(chunk, dict) else chunk.get('topic_cluster', '')
                if actual != expected:
                    mismatch = True
            elif key == "year":
                rng = cond.get("range", {})
                gte = rng.get("gte")
                lte = rng.get("lte")
                actual = getattr(chunk, 'year', 0) if not isinstance(chunk, dict) else chunk.get('year', 0)
                if gte is not None and actual < gte:
                    mismatch = True
                if lte is not None and actual > lte:
                    mismatch = True
                    
        if not mismatch:
            matched.append(chunk)
            
    return matched

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Main endpoint for chatting with Self-Learning and Self-Healing RAG.
    Delegates orchestration to the Compiled LangGraph StateGraph engine.
    """
    start_time = time.time()
    try:
        # Load conversation history
        history = memory.get_history_for_agent7(request.session_id)
        
        # Resolve follow-up queries
        original_query = request.query
        resolved_query = resolver.resolve_follow_up(original_query, request.session_id, history)
        follow_up_resolved = resolved_query != original_query
        if follow_up_resolved:
            logger.info(f"Follow-up resolved: '{original_query}' -> '{resolved_query}'")
            
        # STEP 1 - Proactive Semantic Cache Lookup (runs instantly before LLM classification)
        cache_hit = False
        retrieved_chunks = []
        classification = None
        agent2_result = None
        prefetched_neo4j_metadata = None
        
        try:
            query_embedding = embedder.embed_text(resolved_query)
            cached_chunks = cache.get(query_embedding)
        except Exception as cache_err:
            logger.warning(f"Cache lookup failed: {cache_err}")
            cached_chunks = None
            
        if cached_chunks:
            logger.info("Semantic cache HIT! Classifying query to validate cached chunks...")
            classification = classifier.classify(resolved_query)
            
            if getattr(classification, 'domain_rejected', False):
                processing_time = int((time.time() - start_time) * 1000)
                return ChatResponse(
                    session_id=request.session_id,
                    query=request.query,
                    answer=classification.rejection_message,
                    citations=[],
                    confidence=0.0,
                    confidence_lower=0.0,
                    confidence_upper=0.0,
                    has_gaps=False,
                    gap_acknowledgment="",
                    has_contradiction=False,
                    contradiction_note="",
                    output_format='prose',
                    cache_hit=False,
                    cycle_ran=False,
                    cycle_exit_reason="",
                    processing_time_ms=processing_time,
                    query_type='rejected',
                    chunks_used=0,
                    claim_provenance=[],
                    query_suggestions=[
                        'How does pembrolizumab work?',
                        'What are drug interactions with warfarin?',
                        'What is CRISPR-Cas9 used for?',
                    ],
                    domain_rejected=True,
                )
                
            # Evaluate freshness and completeness grounding checks on cached chunks
            try:
                freshness_check = evaluator._check_freshness(classification, cached_chunks)
                completeness_check, gaps = evaluator._check_completeness_grounding(resolved_query, cached_chunks)
                
                if freshness_check.passed and completeness_check.passed:
                    logger.info("Cached chunks PASSED all quality validation gates. Serving from cache.")
                    from agents.models import Agent2Result
                    calibration_check, confidence = evaluator._check_calibration(cached_chunks)
                    
                    agent2_result = Agent2Result(
                        all_passed=True,
                        failed_check="",
                        checks=[completeness_check, freshness_check, calibration_check],
                        retrieval_results=cached_chunks,
                        calibrated_confidence=confidence,
                        live_fetch_needed=False
                    )
                    retrieved_chunks = cached_chunks
                    cache_hit = True
                    
                    # Prefetch Neo4j metadata for cached chunks
                    paper_ids = list(set(getattr(c, 'paper_id', '') if not isinstance(c, dict) else c.get('paper_id', '') for c in cached_chunks))
                    paper_ids = [pid for pid in paper_ids if pid]
                    try:
                        prefetched_neo4j_metadata = neo4j_manager.get_papers_metadata(paper_ids)
                    except Exception as neo_err:
                        logger.warning(f"Failed to prefetch paper titles: {neo_err}")
                else:
                    logger.info("Cached chunks failed quality checks. Proceeding to full retrieval.")
            except Exception as eval_cache_err:
                logger.warning(f"Error evaluating cached chunks: {eval_cache_err}. Proceeding to full retrieval.")
                
        # STEP 2 - Proactive Contradiction Check via Neo4j
        topic_has_contradictions = False
        proactive_contradiction_note = ""
        contradicting_papers_count = 0
        try:
            topic_cluster = getattr(classification, 'topic_cluster', 'default') if classification else 'default'
            topic_papers = neo4j_manager.get_cluster_papers(topic_cluster, limit=20)
            
            if topic_papers:
                for paper_id in topic_papers[:10]:
                    neighbors = neo4j_manager.get_contradiction_neighbors([paper_id])
                    if neighbors:
                        topic_has_contradictions = True
                        contradicting_papers_count += len(neighbors)
                        
            if topic_has_contradictions:
                proactive_contradiction_note = (
                    "Note: This topic has known contradicting findings in our knowledge base. "
                    "I will present multiple perspectives where evidence conflicts."
                )
        except Exception as e:
            logger.warning(f"Proactive contradiction check failed: {e}")
            
        # STEP 3 - Formulate Initial State for LangGraph
        initial_state = {
            "query": resolved_query,
            "session_id": request.session_id,
            "user_id": request.user_id or "",
            "history": history,
            "classification": classification,
            "retrieval_results": retrieved_chunks,
            "agent2_result": agent2_result,
            "quality_gate_passed": cache_hit,
            "diagnosis": None,
            "repair_attempts": 0,
            "final_response": None,
            "prefetched_neo4j_metadata": prefetched_neo4j_metadata,
            "cache_hit": cache_hit,
            "topic_has_contradictions": topic_has_contradictions,
            "proactive_contradiction_note": proactive_contradiction_note,
            "thought_traces": [],
            "top_k": request.top_k or 5,
            "stream_mode": False,
            "start_time": start_time
        }
        
        # Invoke app_graph
        config_data = {"configurable": {"thread_id": request.session_id}}
        final_state = await app_graph.ainvoke(initial_state, config=config_data)
        
        # Extract results
        response = final_state.get("final_response")
        classification = final_state.get("classification")
        agent2_result = final_state.get("agent2_result")
        retrieved_chunks = final_state.get("retrieval_results", [])
        
        # Check domain rejected in graph
        if classification and getattr(classification, 'domain_rejected', False):
            processing_time = int((time.time() - start_time) * 1000)
            return ChatResponse(
                session_id=request.session_id,
                query=request.query,
                answer=classification.rejection_message or response.answer,
                citations=[],
                confidence=0.0,
                confidence_lower=0.0,
                confidence_upper=0.0,
                has_gaps=False,
                gap_acknowledgment="",
                has_contradiction=False,
                contradiction_note="",
                output_format='prose',
                cache_hit=False,
                cycle_ran=False,
                cycle_exit_reason="",
                processing_time_ms=processing_time,
                query_type='rejected',
                chunks_used=0,
                claim_provenance=[],
                query_suggestions=[
                    'How does pembrolizumab work?',
                    'What are drug interactions with warfarin?',
                    'What is CRISPR-Cas9 used for?',
                ],
                domain_rejected=True,
            )
            
        # Calculate cycle details
        cycle_ran = final_state.get("repair_attempts", 0) > 0
        cycle_exit_reason = ""
        if cycle_ran:
            if final_state.get("quality_gate_passed"):
                cycle_exit_reason = "agent2_passed"
            else:
                cycle_exit_reason = "max_iterations"
                
            # Log autonomous failure recovery to Supabase
            try:
                from database.supabase_client import SupabaseManager
                sb = SupabaseManager()
                if sb.client:
                    diag = final_state.get("diagnosis")
                    root_cause = diag.root_cause if diag else "unknown"
                    failed_check = agent2_result.failed_check if agent2_result else "unknown"
                    sb.client.table("agent_failures").insert({
                        "session_id": request.session_id,
                        "query": resolved_query,
                        "failed_check": failed_check,
                        "root_cause": root_cause,
                        "exit_reason": cycle_exit_reason,
                        "resolved": cycle_exit_reason == "agent2_passed"
                    }).execute()
            except Exception as e:
                logger.error(f"Failed to log agent failure to Supabase: {e}")
                
        # Save memory
        memory.add_turn(
            session_id=request.session_id,
            role="user",
            content=original_query,
            query_type=classification.query_type if classification else "unknown",
            confidence=None
        )
        memory.add_turn(
            session_id=request.session_id,
            role="assistant",
            content=response.answer,
            query_type=None,
            confidence=response.confidence
        )
        
        # Update topic model
        topic_model.update_session_model(
            session_id=request.session_id,
            query=resolved_query,
            response=response.answer
        )
        
        # Retrieval Bias applied
        bias_state = topic_model.get_retrieval_bias(request.session_id, resolved_query)
        session_topic = bias_state.get("preferred_cluster", "default") if bias_state else "default"
        session_bias_applied = len(bias_state) > 0 if bias_state else False
        
        # Graph expansion details
        graph_papers_added = sum(1 for r in retrieved_chunks if getattr(r, 'from_graph', False)) if retrieved_chunks else 0
        graph_expansion_used = graph_papers_added > 0
        
        # Non-blocking observation task
        asyncio.create_task(
            _observe_async(
                session_id=request.session_id,
                query=resolved_query,
                classification=classification,
                agent2_result=agent2_result,
                cycle_result=None
            )
        )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return ChatResponse(
            session_id=request.session_id,
            query=original_query,
            answer=response.answer,
            citations=response.citations,
            confidence=response.confidence,
            confidence_lower=getattr(response, 'confidence_lower', response.confidence),
            confidence_upper=getattr(response, 'confidence_upper', response.confidence),
            has_gaps=response.has_gaps,
            gap_acknowledgment=response.gap_acknowledgment,
            has_contradiction=response.has_contradiction,
            contradiction_note=response.contradiction_note,
            query_type=classification.query_type if classification else "unknown",
            chunks_used=response.chunks_used,
            cycle_ran=cycle_ran,
            cycle_exit_reason=cycle_exit_reason,
            processing_time_ms=processing_time_ms,
            cache_hit=final_state.get("cache_hit", False),
            session_bias_applied=session_bias_applied,
            session_topic=session_topic,
            follow_up_resolved=follow_up_resolved,
            resolved_query=resolved_query if follow_up_resolved else "",
            graph_expansion_used=graph_expansion_used,
            graph_papers_added=graph_papers_added,
            output_format=response.output_format,
            claim_provenance=[vars(p) if not isinstance(p, dict) else p for p in response.claim_provenance] if response.claim_provenance else [],
            query_suggestions=response.query_suggestions or [],
            proactive_contradiction_detected=topic_has_contradictions,
            contradicting_papers_count=contradicting_papers_count
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        processing_time_ms = int((time.time() - start_time) * 1000)
        return ChatResponse(
            session_id=request.session_id,
            query=request.query,
            answer="An error occurred while synthesizing evidence. Please try again.",
            citations=[],
            confidence=0.0,
            has_gaps=False,
            gap_acknowledgment="",
            has_contradiction=False,
            contradiction_note="",
            query_type="unknown",
            chunks_used=0,
            cycle_ran=False,
            cycle_exit_reason="error",
            processing_time_ms=processing_time_ms,
            cache_hit=False,
            session_bias_applied=False,
            session_topic="",
            follow_up_resolved=False,
            resolved_query="",
            graph_expansion_used=False,
            graph_papers_added=0,
            output_format="prose",
            claim_provenance=[],
            proactive_contradiction_detected=False,
            contradicting_papers_count=0
        )

@router.get("/chat/stream")
async def chat_stream(session_id: str, query: str):
    """
    SSE stream endpoint using LangGraph StateGraph engine.
    """
    async def event_generator():
        try:
            start = time.time()
            
            # Step 1 - Proactive Semantic Cache Lookup
            query_embedding = embedder.embed_text(query)
            cached = cache.get(query_embedding)
            prefetched_neo4j_metadata = None
            classification = None
            cache_hit = False
            agent2_result = None
            
            if cached:
                yield f"data: {json.dumps({'type': 'event', 'agent': 'cache', 'step': 'hit', 'status': 'complete', 'detail': f'Cache hit - serving from cache', 'duration_ms': int((time.time()-start)*1000)})}\n\n"
                
                # Start classification concurrently since we need it to evaluate cached chunks
                classification_task = asyncio.create_task(asyncio.to_thread(classifier.classify, query))
                
                # Start Neo4j prefetch concurrently since we need it for generation
                paper_ids = list(set(getattr(c, 'paper_id', '') if not isinstance(c, dict) else c.get('paper_id', '') for c in cached))
                paper_ids = [pid for pid in paper_ids if pid]
                
                async def fetch_neo4j_meta(pids):
                    if not pids:
                        return {}
                    try:
                        return neo4j_manager.get_papers_metadata(pids)
                    except Exception as neo_err:
                        logger.warning(f"Failed to prefetch paper titles from Neo4j: {neo_err}")
                        return {}
                
                neo4j_task = asyncio.create_task(fetch_neo4j_meta(paper_ids))
                
                classification = await classification_task
                prefetched_neo4j_metadata = await neo4j_task
                
                # Yield thought traces and events for classification
                if hasattr(classification, 'thought_traces'):
                    for t in classification.thought_traces:
                        yield f"data: {json.dumps({'type': 'thought', 'agent': t.agent, 'step': t.step, 'obs': t.obs, 'thk': t.thk, 'act': t.act, 'out': t.out, 'confidence': t.confidence, 'duration_ms': t.duration_ms})}\n\n"
                
                yield f"data: {json.dumps({'type': 'event', 'agent': 'agent1', 'step': 'classify', 'status': 'complete', 'detail': f'Query type: {classification.query_type}', 'duration_ms': int((time.time()-start)*1000)})}\n\n"
                
                # Evaluate freshness and completeness grounding checks on cached chunks
                freshness_check = evaluator._check_freshness(classification, cached)
                completeness_check, gaps = evaluator._check_completeness_grounding(query, cached)
                
                if freshness_check.passed and completeness_check.passed:
                    from agents.models import Agent2Result
                    calibration_check, confidence = evaluator._check_calibration(cached)
                    agent2_result = Agent2Result(
                        all_passed=True,
                        failed_check="",
                        checks=[completeness_check, freshness_check, calibration_check],
                        retrieval_results=cached,
                        calibrated_confidence=confidence,
                        live_fetch_needed=False
                    )
                    
                    retrieved_chunks = cached
                    cache_hit = True
                else:
                    cached = None
                    
            if not cached:
                yield f"data: {json.dumps({'type': 'event', 'agent': 'cache', 'step': 'miss', 'status': 'info', 'detail': 'Speculative retrieval initiated', 'duration_ms': int((time.time()-start)*1000)})}\n\n"
                retrieved_chunks = []
                classification = None
                
            # Proactive Contradiction Check via Neo4j
            topic_has_contradictions = False
            proactive_contradiction_note = ""
            contradicting_papers_count = 0
            try:
                topic_cluster = getattr(classification, 'topic_cluster', 'default') if classification else 'default'
                topic_papers = neo4j_manager.get_cluster_papers(topic_cluster, limit=20)
                
                if topic_papers:
                    for paper_id in topic_papers[:10]:
                        neighbors = neo4j_manager.get_contradiction_neighbors([paper_id])
                        if neighbors:
                            topic_has_contradictions = True
                            contradicting_papers_count += len(neighbors)
                            
                if topic_has_contradictions:
                    proactive_contradiction_note = (
                        "Note: This topic has known contradicting findings in our knowledge base. "
                        "I will present multiple perspectives where evidence conflicts."
                    )
            except Exception as e:
                logger.warning(f"Proactive contradiction check failed: {e}")
                
            # Initialize State Graph
            initial_state = {
                "query": query,
                "session_id": session_id,
                "user_id": "",
                "history": memory.get_history_for_agent7(session_id),
                "classification": classification,
                "retrieval_results": retrieved_chunks,
                "agent2_result": agent2_result,
                "quality_gate_passed": cache_hit,
                "diagnosis": None,
                "repair_attempts": 0,
                "final_response": None,
                "prefetched_neo4j_metadata": prefetched_neo4j_metadata,
                "cache_hit": cache_hit,
                "topic_has_contradictions": topic_has_contradictions,
                "proactive_contradiction_note": proactive_contradiction_note,
                "thought_traces": [],
                "top_k": 5,
                "stream_mode": True,
                "start_time": start
            }
            
            config_data = {"configurable": {"thread_id": session_id}}
            final_state = dict(initial_state)
            
            # Stream updates from Compiled LangGraph
            async for chunk in app_graph.astream(initial_state, config=config_data, stream_mode="updates"):
                for key, val in chunk.items():
                    final_state.update(val)
                    
                    if key == "speculative_retrieve":
                        cls = val.get("classification")
                        if cls:
                            if hasattr(cls, 'thought_traces'):
                                for t in cls.thought_traces:
                                    yield f"data: {json.dumps({'type': 'thought', 'agent': t.agent, 'step': t.step, 'obs': t.obs, 'thk': t.thk, 'act': t.act, 'out': t.out, 'confidence': t.confidence, 'duration_ms': t.duration_ms})}\n\n"
                            yield f"data: {json.dumps({'type': 'event', 'agent': 'agent1', 'step': 'classify', 'status': 'complete', 'detail': f'Query type: {cls.query_type}', 'duration_ms': int((time.time()-start)*1000)})}\n\n"
                            
                    elif key == "quality_gate":
                        a2_res = val.get("agent2_result")
                        if a2_res:
                            if hasattr(a2_res, 'thought_traces'):
                                for tr in a2_res.thought_traces:
                                    yield f"data: {json.dumps({'type': 'thought', 'agent': tr.agent, 'step': tr.step, 'obs': tr.obs, 'thk': tr.thk, 'act': tr.act, 'out': tr.out, 'confidence': tr.confidence, 'duration_ms': tr.duration_ms})}\n\n"
                            
                            status = 'pass' if val.get("quality_gate_passed") else 'fail'
                            failed = a2_res.failed_check if not val.get("quality_gate_passed") else 'none'
                            yield f"data: {json.dumps({'type': 'event', 'agent': 'agent2', 'step': 'evaluate', 'status': status, 'detail': f'Quality gate: {status.upper()} - {failed}', 'checks': [{'name': c.check_name, 'passed': c.passed, 'score': round(c.score,2)} for c in a2_res.checks], 'duration_ms': int((time.time()-start)*1000)})}\n\n"
                            
                    elif key == "diagnosis":
                        diag = val.get("diagnosis")
                        if diag:
                            if hasattr(diag, 'thought_traces'):
                                for tr in diag.thought_traces:
                                    yield f"data: {json.dumps({'type': 'thought', 'agent': tr.agent, 'step': tr.step, 'obs': tr.obs, 'thk': tr.thk, 'act': tr.act, 'out': tr.out, 'confidence': tr.confidence, 'duration_ms': tr.duration_ms})}\n\n"
                            yield f"data: {json.dumps({'type': 'event', 'agent': 'agent3', 'step': 'diagnose', 'status': 'complete', 'detail': f'Root cause: {diag.root_cause} (Class {diag.failure_class})', 'confidence': diag.confidence, 'duration_ms': int((time.time()-start)*1000)})}\n\n"
                            
                    elif key == "repair_retry":
                        attempts = val.get("repair_attempts", 1)
                        detail_str = f"Repair cycle retry completed (Attempt {attempts})"
                        event_data = {
                            "type": "event",
                            "agent": "agent4a",
                            "step": "repair",
                            "status": "complete",
                            "detail": detail_str,
                            "duration_ms": int((time.time() - start) * 1000)
                        }
                        yield f"data: {json.dumps(event_data)}\n\n"
                        
                    elif key == "generator":
                        resp = val.get("final_response")
                        if resp:
                            if hasattr(resp, 'thought_traces'):
                                for tr in resp.thought_traces:
                                    yield f"data: {json.dumps({'type': 'thought', 'agent': tr.agent, 'step': tr.step, 'obs': tr.obs, 'thk': tr.thk, 'act': tr.act, 'out': tr.out, 'confidence': tr.confidence, 'duration_ms': tr.duration_ms})}\n\n"
                            yield f"data: {json.dumps({'type': 'event', 'agent': 'agent7', 'step': 'generate', 'status': 'complete', 'detail': f'Response ready - {len(resp.citations)} citations', 'duration_ms': int((time.time()-start)*1000)})}\n\n"
            
            # Post-graph execution completion
            response = final_state.get("final_response")
            classification = final_state.get("classification")
            agent2_result = final_state.get("agent2_result")
            retrieved_chunks = final_state.get("retrieval_results", [])
            cache_hit = final_state.get("cache_hit", False)
            cycle_ran = final_state.get("repair_attempts", 0) > 0
            
            # Final Event with conversional text response
            yield f"data: {json.dumps({'type': 'event', 'agent': 'system', 'step': 'answer', 'status': 'done', 'answer': response.answer, 'citations': response.citations, 'confidence': response.confidence, 'has_gaps': response.has_gaps, 'gap_acknowledgment': response.gap_acknowledgment, 'has_contradiction': response.has_contradiction, 'contradiction_note': response.contradiction_note, 'cycle_ran': cycle_ran, 'cache_hit': cache_hit, 'processing_time_ms': int((time.time()-start)*1000), 'output_format': response.output_format, 'claim_provenance': [], 'proactive_contradiction_detected': topic_has_contradictions})}\n\n"
            
            # Extract and stream claim provenance asynchronously
            try:
                provenance = await asyncio.to_thread(
                    generator._extract_claim_provenance,
                    response.answer,
                    retrieved_chunks
                )
                yield f"data: {json.dumps({'type': 'provenance', 'provenance': [vars(p) if not isinstance(p, dict) else p for p in provenance] if provenance else []})}\n\n"
            except Exception as prov_err:
                logger.error(f"Error in async claim provenance stream: {prov_err}")
                yield f"data: {json.dumps({'type': 'provenance', 'provenance': []})}\n\n"
                
            # Save memory
            memory.add_turn(session_id, 'user', query, classification.query_type if classification else 'unknown', 0.0)
            memory.add_turn(session_id, 'assistant', response.answer, '', response.confidence)
            
            # Persist Thought traces
            try:
                all_traces = list(final_state.get("thought_traces", []))
                if hasattr(response, 'thought_traces'):
                    all_traces.extend(response.thought_traces)
                    
                if all_traces:
                    tl = ThoughtLogger(session_id, 'system')
                    tl.traces = all_traces
                    sb = SupabaseManager()
                    tl.persist(sb)
            except Exception as e:
                logger.warning(f"Trace persist error: {e}")
                
        except Exception as e:
            logger.error(f"Error in chat stream: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'event', 'agent': 'system', 'step': 'error', 'status': 'error', 'detail': str(e)})}\n\n"
            
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )

@router.post("/chat/feedback")
async def chat_feedback(request: FeedbackRequest):
    """
    Records user thumbs up / thumbs down feedback.
    Never crashes, best-effort insert into Supabase.
    """
    try:
        from database.supabase_client import SupabaseManager
        sb = SupabaseManager()
        if sb.client:
            sb.client.table("user_feedback").insert({
                "session_id": request.session_id,
                "query": request.query,
                "answer": request.answer,
                "rating": request.rating,
                "topic_cluster": request.topic_cluster,
                "confidence": request.confidence,
                "cycle_ran": request.cycle_ran,
                "cache_hit": request.cache_hit
            }).execute()
        logger.info(f"Feedback recorded: {request.rating} for session {request.session_id}")
        
        async def _feedback_learning_async():
            try:
                from agents.agent6_learning import Agent6Learning
                agent6_inst = Agent6Learning()
                agent6_inst.observe_user_feedback(
                    session_id=request.session_id,
                    query=request.query,
                    rating=request.rating,
                    topic_cluster=request.topic_cluster or 'unknown',
                    confidence=request.confidence or 0.0,
                    cycle_ran=request.cycle_ran or False
                )
                if request.user_id:
                    agent6_inst.update_personal_profile(
                        user_id=request.user_id,
                        query=request.query,
                        topic_cluster=request.topic_cluster or 'unknown',
                        rating=request.rating
                    )
            except Exception as e:
                logger.error(f"Agent6 feedback learning error: {e}")
        
        asyncio.create_task(_feedback_learning_async())
        
    except Exception as e:
        logger.error(f"Failed to record feedback to Supabase: {e}")
    
    # Always return success
    return {"success": True, "message": "Feedback recorded"}

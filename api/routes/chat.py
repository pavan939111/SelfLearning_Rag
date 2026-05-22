import time
import asyncio
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from api.models.requests import ChatRequest
from api.models.responses import ChatResponse
from utils.logger import get_logger

# Import Agents
from agents.agent1_retrieval import QueryClassifier, MetadataPreFilter, HybridRetriever
from agents.agent2_evaluator import Agent2Evaluator
from agents.repair_cycle import RepairCycle
from agents.agent7_generator import Agent7Generator
from agents.conversation_memory import ConversationMemory
from agents.cache_manager import CacheManager
from ingestion.embedder import BiomedicalEmbedder
from agents.agent6_learning import Agent6Learning

logger = get_logger(__name__)
router = APIRouter()

# Initialize agents ONCE at module level to prevent memory leaks / slow cold starts
logger.info("Initializing agents for Chat Route...")
classifier = QueryClassifier()
pre_filter = MetadataPreFilter()
retriever = HybridRetriever()
evaluator = Agent2Evaluator()
cycle = RepairCycle()
generator = Agent7Generator()
memory = ConversationMemory()

cache = CacheManager()
embedder = BiomedicalEmbedder()
agent6 = Agent6Learning()

async def _observe_async(session_id, query, classification, agent2_result, cycle_result):
    try:
        agent6.observe_query_result(
            session_id, query, classification,
            agent2_result, cycle_result
        )
    except Exception:
        pass

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Main endpoint for chatting with FailureRAG.
    Executes the complete Retrieval -> Quality Gate -> Repair -> Generation pipeline.
    """
    start_time = time.time()
    cache_hit = False
    
    try:
        # Step 3: Load conversation history
        history = memory.get_history_for_agent7(request.session_id)
        
        # Step 3.5: Classify the query (always needed for classification query_type & freshness validation)
        classification = classifier.classify(request.query)
        
        # STEP 1 — Before Agent 1: Cache lookup
        cached_chunks = None
        query_embedding = None
        try:
            query_embedding = embedder.embed_text(request.query)
            cached_chunks = cache.get(query_embedding)
        except Exception as cache_err:
            logger.warning(f"Cache lookup failed: {cache_err}")
            
        agent2_result = None
        initial_results = None
        
        # STEP 2 — If cache hit
        if cached_chunks is not None:
            logger.info("Semantic cache HIT! Evaluating cached chunks...")
            try:
                # Run Agent 2 with only freshness and completeness grounding checks
                freshness_check = evaluator._check_freshness(classification, cached_chunks)
                completeness_check, gaps = evaluator._check_completeness_grounding(request.query, cached_chunks)
                
                if freshness_check.passed and completeness_check.passed:
                    logger.info("Cached chunks PASSED all quality validation gates. Serving from cache.")
                    # Build Agent2Result representing cache success
                    from agents.agent2_evaluator import Agent2Result
                    calibration_check, confidence = evaluator._check_calibration(cached_chunks)
                    
                    agent2_result = Agent2Result(
                        all_passed=True,
                        failed_check="",
                        checks=[completeness_check, freshness_check, calibration_check],
                        retrieval_results=cached_chunks,
                        calibrated_confidence=confidence,
                        live_fetch_needed=False
                    )
                    
                    cache_hit = True
                    initial_results = cached_chunks
                else:
                    logger.info("Cached chunks failed quality checks (stale or incomplete). Proceeding to full retrieval.")
            except Exception as eval_cache_err:
                logger.warning(f"Error evaluating cached chunks: {eval_cache_err}. Proceeding to full retrieval.")
                
        # STEP 3 — If cache miss (or stale cache)
        if agent2_result is None or not cache_hit:
            logger.info("Cache MISS or stale. Executing full retrieval and validation flow...")
            
            # Step 4: Agent 1 - Classify and Retrieve
            filter_config = pre_filter.build_filter(classification)
            initial_results = retriever.retrieve(
                query=request.query, 
                classification=classification, 
                filter_config=filter_config, 
                top_k=request.top_k
            )
            
            # Step 5: Agent 2 - Evaluate chunks (Quality Gate)
            agent2_result = evaluator.evaluate(request.query, classification, initial_results)
            
            # Write to cache on pass
            if agent2_result.all_passed:
                try:
                    clusters = [r.topic_cluster if hasattr(r, 'topic_cluster') else r.get('topic_cluster', 'unknown') for r in initial_results]
                    topic_cluster = max(set(clusters), key=clusters.count) if clusters else "default"
                    cache.set(query_embedding, initial_results, topic_cluster)
                except Exception as cache_write_err:
                    logger.warning(f"Failed to write to cache: {cache_write_err}")
                    
        # Step 6: Repair Cycle (only runs if cache miss and Agent 2 failed)
        cycle_result = None
        cycle_ran = False
        cycle_exit_reason = ""
        initial_failed_check = ""
        
        if not agent2_result.all_passed:
            initial_failed_check = agent2_result.failed_check
            logger.info("Agent 2 flagged issues. Initiating Repair Cycle...")
            cycle_result = cycle.run(request.query, classification, initial_results, request.session_id)
            cycle_ran = True
            cycle_exit_reason = cycle_result.exit_reason
            
            # Make sure agent2_result reflects the final outcome from the cycle
            if cycle_result.agent2_result:
                agent2_result = cycle_result.agent2_result
                
            # Log the autonomous failure recovery to Supabase for the Admin Dashboard
            try:
                from database.supabase_client import SupabaseManager
                sb = SupabaseManager()
                if sb.client:
                    root_cause = cycle_result.diagnosis_history[-1].root_cause if getattr(cycle_result, 'diagnosis_history', []) else ""
                    sb.client.table("agent_failures").insert({
                        "session_id": request.session_id,
                        "query": request.query,
                        "failed_check": initial_failed_check,
                        "root_cause": root_cause,
                        "exit_reason": cycle_exit_reason,
                        "resolved": cycle_exit_reason == "agent2_passed"
                    }).execute()
            except Exception as e:
                logger.error(f"Failed to log agent failure to Supabase: {e}")
                
        # Step 7: Agent 7 - Generate final response
        response = generator.generate(
            query=request.query,
            classification=classification,
            agent2_result=agent2_result,
            cycle_result=cycle_result,
            conversation_history=history
        )
        
        # Step 8: Save conversation memory
        memory.add_turn(
            session_id=request.session_id, 
            role="user", 
            content=request.query, 
            query_type=classification.query_type, 
            confidence=None
        )
        memory.add_turn(
            session_id=request.session_id, 
            role="assistant", 
            content=response.answer, 
            query_type=None, 
            confidence=response.confidence
        )
        
        # Step 9: Build and return Response
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Non-blocking observation
        import asyncio
        asyncio.create_task(
            _observe_async(
                session_id=request.session_id,
                query=request.query,
                classification=classification,
                agent2_result=agent2_result,
                cycle_result=cycle_result
            )
        )
        
        return ChatResponse(
            session_id=request.session_id,
            query=request.query,
            answer=response.answer,
            citations=response.citations,
            confidence=response.confidence,
            has_gaps=response.has_gaps,
            gap_acknowledgment=response.gap_acknowledgment,
            has_contradiction=response.has_contradiction,
            contradiction_note=response.contradiction_note,
            query_type=classification.query_type if classification else "unknown",
            chunks_used=response.chunks_used,
            cycle_ran=cycle_ran,
            cycle_exit_reason=cycle_exit_reason,
            processing_time_ms=processing_time_ms,
            cache_hit=cache_hit
        )
        
    except Exception as e:
        # Step 10: Graceful fallback on any exception
        logger.error(f"Error in chat endpoint: {e}")
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return ChatResponse(
            session_id=request.session_id,
            query=request.query,
            answer="An error occurred. Please try again.",
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
            cache_hit=False
        )

@router.get("/chat/stream")
async def chat_stream(session_id: str, query: str):
    
    async def event_generator():
        try:
            start = time.time()
            
            # Step 1 — Classification
            classification = classifier.classify(query)
            yield f"data: {json.dumps({'agent': 'agent1', 'step': 'classify', 'status': 'complete', 'detail': f'Query type: {classification.query_type}', 'duration_ms': int((time.time()-start)*1000)})}\n\n"
            await asyncio.sleep(0.1)
            
            # Step 2 — Cache check
            query_embedding = embedder.embed_text(query)
            cached = cache.get(query_embedding)
            if cached:
                yield f"data: {json.dumps({'agent': 'cache', 'step': 'hit', 'status': 'complete', 'detail': f'Cache hit — skipping retrieval', 'duration_ms': int((time.time()-start)*1000)})}\n\n"
                retrieval_results = cached
                cache_hit = True
            else:
                yield f"data: {json.dumps({'agent': 'cache', 'step': 'miss', 'status': 'info', 'detail': 'Cache miss — running full retrieval', 'duration_ms': int((time.time()-start)*1000)})}\n\n"
                
                # Step 3 — Retrieval
                t = time.time()
                filter_config = pre_filter.build_filter(classification)
                retrieval_results = retriever.retrieve(query, classification, filter_config, top_k=5)
                yield f"data: {json.dumps({'agent': 'agent1', 'step': 'retrieve', 'status': 'complete', 'detail': f'Retrieved {len(retrieval_results)} chunks — avg score {sum(r.score for r in retrieval_results)/max(len(retrieval_results),1):.3f}', 'duration_ms': int((time.time()-t)*1000)})}\n\n"
                cache_hit = False
                await asyncio.sleep(0.1)
            
            # Step 4 — Agent 2
            t = time.time()
            agent2_result = evaluator.evaluate(query, classification, retrieval_results)
            status = 'pass' if agent2_result.all_passed else 'fail'
            failed = agent2_result.failed_check if not agent2_result.all_passed else 'none'
            yield f"data: {json.dumps({'agent': 'agent2', 'step': 'evaluate', 'status': status, 'detail': f'Quality gate: {status.upper()} — {failed}', 'checks': [{'name': c.check_name, 'passed': c.passed, 'score': round(c.score,2)} for c in agent2_result.checks], 'duration_ms': int((time.time()-t)*1000)})}\n\n"
            await asyncio.sleep(0.1)
            
            # Step 5 — Repair cycle if needed
            cycle_result = None
            if not agent2_result.all_passed:
                t = time.time()
                yield f"data: {json.dumps({'agent': 'agent3', 'step': 'diagnose', 'status': 'running', 'detail': 'Running root cause diagnosis...', 'duration_ms': 0})}\n\n"
                
                cycle_result = cycle.run(query, classification, retrieval_results, session_id)
                
                if cycle_result.diagnosis_history:
                    d = cycle_result.diagnosis_history[0]
                    yield f"data: {json.dumps({'agent': 'agent3', 'step': 'diagnose', 'status': 'complete', 'detail': f'Root cause: {d.root_cause} (Class {d.failure_class})', 'confidence': d.confidence, 'duration_ms': int((time.time()-t)*1000)})}\n\n"
                
                yield f"data: {json.dumps({'agent': 'agent4a', 'step': 'repair', 'status': 'complete', 'detail': f'Repair cycle: {cycle_result.exit_reason} after {cycle_result.iterations_run} iterations', 'duration_ms': int((time.time()-t)*1000)})}\n\n"
                
                retrieval_results = cycle_result.final_chunks
                agent2_result_final = cycle_result.agent2_result
            else:
                agent2_result_final = agent2_result
                if not cache_hit:
                    topic = retrieval_results[0].topic_cluster if retrieval_results else 'immunotherapy'
                    cache.set(query_embedding, retrieval_results, topic)
            
            # Step 6 — Generation
            t = time.time()
            yield f"data: {json.dumps({'agent': 'agent7', 'step': 'generate', 'status': 'running', 'detail': 'Generating conversational response...', 'duration_ms': 0})}\n\n"
            
            history = memory.get_history_for_agent7(session_id)
            response = generator.generate(
                query=query,
                classification=classification,
                agent2_result=agent2_result_final,
                cycle_result=cycle_result,
                conversation_history=history
            )
            
            memory.add_turn(session_id, 'user', query, classification.query_type, 0.0)
            memory.add_turn(session_id, 'assistant', response.answer, '', response.confidence)
            
            yield f"data: {json.dumps({'agent': 'agent7', 'step': 'generate', 'status': 'complete', 'detail': f'Response ready — {len(response.citations)} citations', 'duration_ms': int((time.time()-t)*1000)})}\n\n"
            
            # Final answer
            yield f"data: {json.dumps({'agent': 'system', 'step': 'answer', 'status': 'done', 'answer': response.answer, 'citations': response.citations, 'confidence': response.confidence, 'has_gaps': response.has_gaps, 'gap_acknowledgment': response.gap_acknowledgment, 'has_contradiction': response.has_contradiction, 'contradiction_note': response.contradiction_note, 'cycle_ran': cycle_result is not None, 'cache_hit': cache_hit, 'processing_time_ms': int((time.time()-start)*1000)})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'agent': 'system', 'step': 'error', 'status': 'error', 'detail': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )

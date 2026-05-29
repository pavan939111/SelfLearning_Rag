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

# Import Agents
from agents.models import PipelineState
from agents.agent1_retrieval import QueryClassifier, MetadataPreFilter, HybridRetriever
from agents.agent2_evaluator import Agent2Evaluator
from agents.repair_cycle import RepairCycle
from agents.agent7_generator import Agent7Generator
from agents.conversation_memory import ConversationMemory, SessionTopicModel, FollowUpResolver
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
topic_model = SessionTopicModel()
resolver = FollowUpResolver()

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
    Executes the complete Retrieval -> Quality Gate -> Repair -> Generation pipeline.
    """
    start_time = time.time()
    cache_hit = False
    prefetched_neo4j_metadata = None
    
    try:
        # Step 3: Load conversation history
        history = memory.get_history_for_agent7(request.session_id)
        
        # Step 3.2: Resolve follow-up queries
        original_query = request.query
        resolved_query = resolver.resolve_follow_up(original_query, request.session_id, history)
        follow_up_resolved = resolved_query != original_query
        if follow_up_resolved:
            logger.info(f"Follow-up resolved: '{original_query}' -> '{resolved_query}'")
            
        # Initialize PipelineState
        state = PipelineState(
            query=resolved_query,
            session_id=request.session_id,
            resolved_query=resolved_query if follow_up_resolved else "",
            follow_up_resolved=follow_up_resolved
        )
        
        # STEP 1 - Proactive Semantic Cache Lookup (runs instantly before LLM classification)
        query_embedding = None
        cached_chunks = None
        try:
            query_embedding = embedder.embed_text(state.query)
            cached_chunks = cache.get(query_embedding)
        except Exception as cache_err:
            logger.warning(f"Cache lookup failed: {cache_err}")
            
        # STEP 2 - If Cache Hit, evaluate cached chunks
        if cached_chunks:
            logger.info("Semantic cache HIT! Classifying query to validate cached chunks...")
            state.classification = classifier.classify(state.query)
            
            if getattr(state.classification, 'domain_rejected', False):
                processing_time = int((time.time() - start_time) * 1000)
                return ChatResponse(
                    session_id=request.session_id,
                    query=request.query,
                    answer=state.classification.rejection_message,
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
                
            # Prefetch Neo4j metadata for cached chunks concurrently
            paper_ids = list(set(getattr(c, 'paper_id', '') if not isinstance(c, dict) else c.get('paper_id', '') for c in cached_chunks))
            paper_ids = [pid for pid in paper_ids if pid]
            
            async def fetch_neo4j_meta(pids):
                if not pids:
                    return {}
                try:
                    from database.neo4j_client import Neo4jManager
                    neo4j = Neo4jManager()
                    return neo4j.get_papers_metadata(pids)
                except Exception as neo_err:
                    logger.warning(f"Failed to prefetch paper titles from Neo4j: {neo_err}")
                    return {}
                    
            neo4j_task = asyncio.create_task(fetch_neo4j_meta(paper_ids))
            
            try:
                # Run Agent 2 with only freshness and completeness grounding checks
                freshness_check = evaluator._check_freshness(state.classification, cached_chunks)
                completeness_check, gaps = evaluator._check_completeness_grounding(state.query, cached_chunks)
                
                if freshness_check.passed and completeness_check.passed:
                    logger.info("Cached chunks PASSED all quality validation gates. Serving from cache.")
                    from agents.models import Agent2Result
                    calibration_check, confidence = evaluator._check_calibration(cached_chunks)
                    
                    state.agent2_result = Agent2Result(
                        all_passed=True,
                        failed_check="",
                        checks=[completeness_check, freshness_check, calibration_check],
                        retrieval_results=cached_chunks,
                        calibrated_confidence=confidence,
                        live_fetch_needed=False
                    )
                    state.retrieval_results = cached_chunks
                    state.cache_hit = True
                    prefetched_neo4j_metadata = await neo4j_task
                else:
                    logger.info("Cached chunks failed quality checks (stale or incomplete). Proceeding to full retrieval.")
                    neo4j_task.cancel()
            except Exception as eval_cache_err:
                logger.warning(f"Error evaluating cached chunks: {eval_cache_err}. Proceeding to full retrieval.")
                neo4j_task.cancel()
                
        # STEP 3 - If cache miss or stale cache
        if state.agent2_result is None or not state.cache_hit:
            logger.info("Cache MISS or stale. Executing parallel speculative classification and retrieval...")
            
            # Start query classification (LLM call) and speculative unfiltered semantic retrieval concurrently
            if state.classification is None:
                classification_task = asyncio.create_task(asyncio.to_thread(classifier.classify, state.query))
            else:
                async def get_existing_classification():
                    return state.classification
                classification_task = asyncio.create_task(get_existing_classification())
                
            speculative_retrieval_task = asyncio.create_task(retriever.retrieve(
                query=state.query,
                classification=None,
                filter_config=None,
                top_k=request.top_k,
                session_id=state.session_id
            ))
            
            classification, speculative_results = await asyncio.gather(classification_task, speculative_retrieval_task)
            state.classification = classification
            
            # Step 3.5: Handle domain rejection
            if getattr(state.classification, 'domain_rejected', False):
                processing_time = int((time.time() - start_time) * 1000)
                return ChatResponse(
                    session_id=request.session_id,
                    query=request.query,
                    answer=state.classification.rejection_message,
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
                
            # Apply filter checks on speculative results
            filter_config = pre_filter.build_filter(state.classification)
            matched_results = _filter_speculative_results(speculative_results, filter_config)
            
            if len(matched_results) >= 3:
                logger.info(f"Speculative search MATCHED filter criteria. Utilizing {len(matched_results)} matching chunks.")
                state.retrieval_results = matched_results
            else:
                logger.info(f"Speculative search missed filters (only {len(matched_results)} matched). Performing filtered fallback retrieval...")
                state.retrieval_results = await retriever.retrieve(
                    query=state.query,
                    classification=state.classification,
                    filter_config=filter_config,
                    top_k=request.top_k,
                    session_id=state.session_id
                )
                
            # STEP 4 - Parallel prefetch Neo4j metadata alongside Agent 2 Quality Gate evaluation
            paper_ids = list(set(getattr(c, 'paper_id', '') if not isinstance(c, dict) else c.get('paper_id', '') for c in state.retrieval_results))
            paper_ids = [pid for pid in paper_ids if pid]
            
            async def fetch_neo4j_meta(pids):
                if not pids:
                    return {}
                try:
                    from database.neo4j_client import Neo4jManager
                    neo4j = Neo4jManager()
                    return neo4j.get_papers_metadata(pids)
                except Exception as neo_err:
                    logger.warning(f"Failed to prefetch paper titles from Neo4j: {neo_err}")
                    return {}
                    
            neo4j_task = asyncio.create_task(fetch_neo4j_meta(paper_ids))
            
            # Evaluate chunks concurrently with Neo4j lookup
            agent2_eval_task = asyncio.create_task(evaluator.evaluate(
                state.query,
                state.classification,
                state.retrieval_results,
                user_id=request.user_id
            ))
            
            state.agent2_result, prefetched_neo4j_metadata = await asyncio.gather(agent2_eval_task, neo4j_task)
            
            # Write to cache on pass asynchronously
            if state.agent2_result.all_passed:
                try:
                    clusters = [r.topic_cluster if hasattr(r, 'topic_cluster') else r.get('topic_cluster', 'unknown') for r in state.retrieval_results]
                    topic_cluster = max(set(clusters), key=clusters.count) if clusters else "default"
                    asyncio.create_task(asyncio.to_thread(cache.set, query_embedding, state.retrieval_results, topic_cluster))
                except Exception as cache_write_err:
                    logger.warning(f"Failed to write to cache: {cache_write_err}")
                    
        # Step 3.6: Proactive contradiction check via Neo4j
        contradicting_papers_count = 0
        try:
            from database.neo4j_client import Neo4jManager
            neo4j = Neo4jManager()
            topic_cluster = getattr(state.classification, 'topic_cluster', 'default')
            topic_papers = neo4j.get_cluster_papers(topic_cluster, limit=20)
            
            if topic_papers:
                for paper_id in topic_papers[:10]:
                    neighbors = neo4j.get_contradiction_neighbors([paper_id])
                    if neighbors:
                        state.topic_has_contradictions = True
                        contradicting_papers_count += len(neighbors)
                        
            if state.topic_has_contradictions:
                state.proactive_contradiction_note = (
                    "Note: This topic has known contradicting findings in our knowledge base. "
                    "I will present multiple perspectives where evidence conflicts."
                )
        except Exception as e:
            logger.warning(f"Proactive contradiction check failed: {e}")
            
        # Step 6: Repair Cycle (only runs if cache miss and Agent 2 failed)
        cycle_ran = False
        cycle_exit_reason = ""
        initial_failed_check = ""
        
        if not state.agent2_result.all_passed:
            initial_failed_check = state.agent2_result.failed_check
            logger.info("Agent 2 flagged issues. Initiating Repair Cycle...")
            state.cycle_result = await cycle.run(state.query, state.classification, state.retrieval_results, state.session_id)
            cycle_ran = True
            cycle_exit_reason = state.cycle_result.exit_reason
            
            # Make sure agent2_result reflects the final outcome from the cycle
            if state.cycle_result.agent2_result:
                state.agent2_result = state.cycle_result.agent2_result
                
            # Log the autonomous failure recovery to Supabase for the Admin Dashboard
            try:
                from database.supabase_client import SupabaseManager
                sb = SupabaseManager()
                if sb.client:
                    root_cause = state.cycle_result.diagnosis_history[-1].root_cause if getattr(state.cycle_result, 'diagnosis_history', []) else ""
                    sb.client.table("agent_failures").insert({
                        "session_id": state.session_id,
                        "query": state.query,
                        "failed_check": initial_failed_check,
                        "root_cause": root_cause,
                        "exit_reason": cycle_exit_reason,
                        "resolved": cycle_exit_reason == "agent2_passed"
                    }).execute()
            except Exception as e:
                logger.error(f"Failed to log agent failure to Supabase: {e}")
                
        # Step 6.5: Get Personal Context for Generation
        personal_context_msg = ""
        if request.user_id:
            from agents.agent6_learning import Agent6Learning
            agent6 = Agent6Learning()
            personal = agent6.get_personal_context(request.user_id)
            preferred = personal.get("preferred_cluster")
            if preferred:
                personal_context_msg = f"This researcher frequently works with {preferred} literature."
                
        # Step 7: Agent 7 - Generate final response
        history_with_context = list(history)
        if personal_context_msg:
            history_with_context.append({"role": "system", "content": personal_context_msg})
            
        state.response = await generator.generate(
            query=state.query,
            classification=state.classification,
            agent2_result=state.agent2_result,
            cycle_result=state.cycle_result,
            conversation_history=history_with_context,
            proactive_contradiction_note=state.proactive_contradiction_note,
            prefetched_neo4j_metadata=prefetched_neo4j_metadata
        )
        
        # Step 8: Save conversation memory
        memory.add_turn(
            session_id=state.session_id,
            role="user",
            content=state.query,
            query_type=state.classification.query_type,
            confidence=None
        )
        memory.add_turn(
            session_id=state.session_id,
            role="assistant",
            content=state.response.answer,
            query_type=None,
            confidence=state.response.confidence
        )
        
        # Step 9: Build and return Response
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Step 8.5: Update session topic model
        topic_model.update_session_model(
            session_id=state.session_id,
            query=state.query,
            response=state.response.answer
        )
        
        # Get final bias state for response
        bias_state = topic_model.get_retrieval_bias(state.session_id, state.query)
        state.session_topic = bias_state.get("preferred_cluster", "default") if bias_state else "default"
        state.session_bias_applied = len(bias_state) > 0 if bias_state else False
        
        # Calculate graph expansion metrics
        final_chunks = state.cycle_result.final_chunks if state.cycle_result else (state.agent2_result.retrieval_results if state.agent2_result else state.retrieval_results)
        graph_papers_added = sum(1 for r in final_chunks if getattr(r, 'from_graph', False)) if final_chunks else 0
        graph_expansion_used = graph_papers_added > 0
        
        # Non-blocking observation
        asyncio.create_task(
            _observe_async(
                session_id=state.session_id,
                query=state.query,
                classification=state.classification,
                agent2_result=state.agent2_result,
                cycle_result=state.cycle_result
            )
        )
        
        return ChatResponse(
            session_id=state.session_id,
            query=original_query,
            answer=state.response.answer,
            citations=state.response.citations,
            confidence=state.response.confidence,
            confidence_lower=getattr(state.response, 'confidence_lower', state.response.confidence),
            confidence_upper=getattr(state.response, 'confidence_upper', state.response.confidence),
            has_gaps=state.response.has_gaps,
            gap_acknowledgment=state.response.gap_acknowledgment,
            has_contradiction=state.response.has_contradiction,
            contradiction_note=state.response.contradiction_note,
            query_type=state.classification.query_type if state.classification else "unknown",
            chunks_used=state.response.chunks_used,
            cycle_ran=cycle_ran,
            cycle_exit_reason=cycle_exit_reason,
            processing_time_ms=processing_time_ms,
            cache_hit=state.cache_hit,
            session_bias_applied=state.session_bias_applied,
            session_topic=state.session_topic,
            follow_up_resolved=state.follow_up_resolved,
            resolved_query=state.resolved_query,
            graph_expansion_used=graph_expansion_used,
            graph_papers_added=graph_papers_added,
            output_format=state.response.output_format,
            claim_provenance=[vars(p) if not isinstance(p, dict) else p for p in state.response.claim_provenance] if state.response.claim_provenance else [],
            query_suggestions=state.response.query_suggestions or [],
            proactive_contradiction_detected=state.topic_has_contradictions,
            contradicting_papers_count=contradicting_papers_count
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

@router.get("/chat/stream")
async def chat_stream(session_id: str, query: str):
    
    async def event_generator():
        try:
            start = time.time()
            
            # Step 1 - Proactive Semantic Cache Lookup
            query_embedding = embedder.embed_text(query)
            cached = cache.get(query_embedding)
            prefetched_neo4j_metadata = None
            classification = None
            
            if cached:
                yield f"data: {json.dumps({'type': 'event', 'agent': 'cache', 'step': 'hit', 'status': 'complete', 'detail': f'Cache hit - skipping retrieval', 'duration_ms': int((time.time()-start)*1000)})}\n\n"
                
                # Start classification concurrently since we need it to evaluate cached chunks
                classification_task = asyncio.create_task(asyncio.to_thread(classifier.classify, query))
                
                # Start Neo4j prefetch concurrently since we need it for generation
                paper_ids = list(set(getattr(c, 'paper_id', '') if not isinstance(c, dict) else c.get('paper_id', '') for c in cached))
                paper_ids = [pid for pid in paper_ids if pid]
                
                async def fetch_neo4j_meta(pids):
                    if not pids:
                        return {}
                    try:
                        from database.neo4j_client import Neo4jManager
                        neo4j = Neo4jManager()
                        return neo4j.get_papers_metadata(pids)
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
                    
                    retrieval_results = cached
                    agent2_result_final = agent2_result
                    cycle_result = None
                    cache_hit = True
                else:
                    cached = None
                    
            if not cached:
                # If classification is not already run (e.g. from cache hit failure fallback), run it now in parallel with speculative retrieval
                if classification is None:
                    classification_task = asyncio.create_task(asyncio.to_thread(classifier.classify, query))
                else:
                    async def get_existing_classification():
                        return classification
                    classification_task = asyncio.create_task(get_existing_classification())
                
                speculative_retrieval_task = asyncio.create_task(retriever.retrieve(
                    query=query,
                    classification=None,
                    filter_config=None,
                    top_k=5,
                    session_id=session_id
                ))
                
                classification, speculative_results = await asyncio.gather(classification_task, speculative_retrieval_task)
                
                # Yield classification thought traces and event
                if hasattr(classification, 'thought_traces'):
                    for t in classification.thought_traces:
                        yield f"data: {json.dumps({'type': 'thought', 'agent': t.agent, 'step': t.step, 'obs': t.obs, 'thk': t.thk, 'act': t.act, 'out': t.out, 'confidence': t.confidence, 'duration_ms': t.duration_ms})}\n\n"
                        
                yield f"data: {json.dumps({'type': 'event', 'agent': 'agent1', 'step': 'classify', 'status': 'complete', 'detail': f'Query type: {classification.query_type}', 'duration_ms': int((time.time()-start)*1000)})}\n\n"
                
                # Speculative filter matching
                filter_config = pre_filter.build_filter(classification)
                matched_results = _filter_speculative_results(speculative_results, filter_config)
                
                if len(matched_results) >= 3:
                    yield f"data: {json.dumps({'type': 'event', 'agent': 'cache', 'step': 'miss', 'status': 'info', 'detail': f'Speculative retrieval matched filters ({len(matched_results)} chunks)', 'duration_ms': int((time.time()-start)*1000)})}\n\n"
                    retrieval_results = matched_results
                else:
                    yield f"data: {json.dumps({'type': 'event', 'agent': 'cache', 'step': 'miss', 'status': 'info', 'detail': f'Speculative retrieval missed filters (only {len(matched_results)} matched). Running filtered retrieval...', 'duration_ms': int((time.time()-start)*1000)})}\n\n"
                    
                    # Filtered fallback
                    retrieval_results = await retriever.retrieve(
                        query=query,
                        classification=classification,
                        filter_config=filter_config,
                        top_k=5,
                        session_id=session_id
                    )
                
                cache_hit = False
                
                # Parallel prefetch Neo4j metadata alongside Agent 2 Quality Gate
                paper_ids = list(set(getattr(c, 'paper_id', '') if not isinstance(c, dict) else c.get('paper_id', '') for c in retrieval_results))
                paper_ids = [pid for pid in paper_ids if pid]
                
                async def fetch_neo4j_meta(pids):
                    if not pids:
                        return {}
                    try:
                        from database.neo4j_client import Neo4jManager
                        neo4j = Neo4jManager()
                        return neo4j.get_papers_metadata(pids)
                    except Exception as neo_err:
                        logger.warning(f"Failed to prefetch paper titles from Neo4j: {neo_err}")
                        return {}
                
                neo4j_task = asyncio.create_task(fetch_neo4j_meta(paper_ids))
                
                # Quality Gate evaluate concurrently with Neo4j prefetch
                t_eval = time.time()
                agent2_task = asyncio.create_task(evaluator.evaluate(query, classification, retrieval_results))
                
                agent2_result, prefetched_neo4j_metadata = await asyncio.gather(agent2_task, neo4j_task)
                
                if hasattr(agent2_result, 'thought_traces'):
                    for tr in agent2_result.thought_traces:
                        yield f"data: {json.dumps({'type': 'thought', 'agent': tr.agent, 'step': tr.step, 'obs': tr.obs, 'thk': tr.thk, 'act': tr.act, 'out': tr.out, 'confidence': tr.confidence, 'duration_ms': tr.duration_ms})}\n\n"
                        
                status = 'pass' if agent2_result.all_passed else 'fail'
                failed = agent2_result.failed_check if not agent2_result.all_passed else 'none'
                yield f"data: {json.dumps({'type': 'event', 'agent': 'agent2', 'step': 'evaluate', 'status': status, 'detail': f'Quality gate: {status.upper()} - {failed}', 'checks': [{'name': c.check_name, 'passed': c.passed, 'score': round(c.score,2)} for c in agent2_result.checks], 'duration_ms': int((time.time()-t_eval)*1000)})}\n\n"
                
                # Repair cycle if needed
                cycle_result = None
                if not agent2_result.all_passed:
                    t_rep = time.time()
                    yield f"data: {json.dumps({'type': 'event', 'agent': 'agent3', 'step': 'diagnose', 'status': 'running', 'detail': 'Running root cause diagnosis...', 'duration_ms': 0})}\n\n"
                    
                    cycle_result = await cycle.run(query, classification, retrieval_results, session_id)
                    
                    if cycle_result.diagnosis_history:
                        d = cycle_result.diagnosis_history[0]
                        if hasattr(d, 'thought_traces'):
                            for tr in d.thought_traces:
                                yield f"data: {json.dumps({'type': 'thought', 'agent': tr.agent, 'step': tr.step, 'obs': tr.obs, 'thk': tr.thk, 'act': tr.act, 'out': tr.out, 'confidence': tr.confidence, 'duration_ms': tr.duration_ms})}\n\n"
                        yield f"data: {json.dumps({'type': 'event', 'agent': 'agent3', 'step': 'diagnose', 'status': 'complete', 'detail': f'Root cause: {d.root_cause} (Class {d.failure_class})', 'confidence': d.confidence, 'duration_ms': int((time.time()-t_rep)*1000)})}\n\n"
                    
                    yield f"data: {json.dumps({'type': 'event', 'agent': 'agent4a', 'step': 'repair', 'status': 'complete', 'detail': f'Repair cycle: {cycle_result.exit_reason} after {cycle_result.iterations_run} iterations', 'duration_ms': int((time.time()-t_rep)*1000)})}\n\n"
                    
                    retrieval_results = cycle_result.final_chunks
                    agent2_result_final = cycle_result.agent2_result
                else:
                    agent2_result_final = agent2_result
                    if not cache_hit:
                        topic = retrieval_results[0].topic_cluster if retrieval_results else 'immunotherapy'
                        asyncio.create_task(asyncio.to_thread(cache.set, query_embedding, retrieval_results, topic))
            
            # Step 6 - Generation
            t = time.time()
            yield f"data: {json.dumps({'type': 'event', 'agent': 'agent7', 'step': 'generate', 'status': 'running', 'detail': 'Generating conversational response...', 'duration_ms': 0})}\n\n"
            
            history = memory.get_history_for_agent7(session_id)
            response = await generator.generate(
                query=query,
                classification=classification,
                agent2_result=agent2_result_final,
                cycle_result=cycle_result,
                conversation_history=history,
                extract_provenance=False, # Stream-first claim provenance optimization
                prefetched_neo4j_metadata=prefetched_neo4j_metadata
            )
            
            memory.add_turn(session_id, 'user', query, classification.query_type, 0.0)
            memory.add_turn(session_id, 'assistant', response.answer, '', response.confidence)
            if hasattr(response, 'thought_traces'):
                for tr in response.thought_traces:
                    yield f"data: {json.dumps({'type': 'thought', 'agent': tr.agent, 'step': tr.step, 'obs': tr.obs, 'thk': tr.thk, 'act': tr.act, 'out': tr.out, 'confidence': tr.confidence, 'duration_ms': tr.duration_ms})}\n\n"

            yield f"data: {json.dumps({'type': 'event', 'agent': 'agent7', 'step': 'generate', 'status': 'complete', 'detail': f'Response ready - {len(response.citations)} citations', 'duration_ms': int((time.time()-t)*1000)})}\n\n"
            
            # Final answer (Done event, instant conversational text output)
            yield f"data: {json.dumps({'type': 'event', 'agent': 'system', 'step': 'answer', 'status': 'done', 'answer': response.answer, 'citations': response.citations, 'confidence': response.confidence, 'has_gaps': response.has_gaps, 'gap_acknowledgment': response.gap_acknowledgment, 'has_contradiction': response.has_contradiction, 'contradiction_note': response.contradiction_note, 'cycle_ran': cycle_result is not None, 'cache_hit': cache_hit, 'processing_time_ms': int((time.time()-start)*1000), 'output_format': response.output_format, 'claim_provenance': [], 'proactive_contradiction_detected': False})}\n\n"
            
            # Now asynchronously extract claim provenance and stream the event
            try:
                provenance = await asyncio.to_thread(
                    generator._extract_claim_provenance,
                    response.answer,
                    retrieval_results
                )
                yield f"data: {json.dumps({'type': 'provenance', 'provenance': [vars(p) if not isinstance(p, dict) else p for p in provenance] if provenance else []})}\n\n"
            except Exception as prov_err:
                logger.error(f"Error in async claim provenance stream: {prov_err}")
                yield f"data: {json.dumps({'type': 'provenance', 'provenance': []})}\n\n"
            
            # Non-blocking trace persist here
            try:
                # gather all traces
                all_traces = []
                if hasattr(classification, 'thought_traces'): all_traces.extend(classification.thought_traces)
                if hasattr(agent2_result_final, 'thought_traces'): all_traces.extend(agent2_result_final.thought_traces)
                if cycle_result and cycle_result.diagnosis_history and hasattr(cycle_result.diagnosis_history[-1], 'thought_traces'):
                    all_traces.extend(cycle_result.diagnosis_history[-1].thought_traces)
                if hasattr(response, 'thought_traces'): all_traces.extend(response.thought_traces)
                
                if all_traces:
                    from utils.thought_logger import ThoughtLogger
                    tl = ThoughtLogger(session_id, 'system')
                    tl.traces = all_traces
                    from database.supabase_client import SupabaseManager
                    sb = SupabaseManager()
                    tl.persist(sb)
            except Exception as e:
                logger.warning(f"Trace persist error: {e}")
            
        except Exception as e:
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

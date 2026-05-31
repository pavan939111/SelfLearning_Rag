import asyncio
import json
import time
from typing import TypedDict, List, Optional, Any
from google.genai import errors

from config import get_config
from utils.logger import get_logger
from utils.thought_logger import ThoughtLogger

from agents.agent1_retrieval import QueryClassifier, MetadataPreFilter, HybridRetriever
from agents.agent2_evaluator import Agent2Evaluator
from agents.agent3_classifier import Agent3Classifier
from agents.agent4a_formulator import Agent4AFormulator
from agents.agent7_generator import Agent7Generator
from agents.conversation_memory import ConversationMemory
from agents.cache_manager import CacheManager
from ingestion.embedder import BiomedicalEmbedder
from agents.agent6_learning import Agent6Learning

from agents.models import (
    RetrievalResult, EvaluationResult, DiagnosisResult,
    ThoughtTrace, Agent2Result, GeneratedResponse, SubQuery, FormulationResult
)

# 1. State Schema
class AgentState(TypedDict):
    query: str
    session_id: str
    user_id: str
    history: List[Any]
    
    # State flags and data
    classification: Optional[Any]
    retrieval_results: List[RetrievalResult]
    agent2_result: Optional[Agent2Result]
    quality_gate_passed: bool
    diagnosis: Optional[DiagnosisResult]
    repair_attempts: int
    final_response: Optional[GeneratedResponse]
    prefetched_neo4j_metadata: Optional[dict]
    
    # Caching and Contradiction tracking
    cache_hit: bool
    topic_has_contradictions: bool
    proactive_contradiction_note: str
    
    # Trace Logging
    thought_traces: List[ThoughtTrace]
    
    # Runtime Configurations
    top_k: int
    stream_mode: bool
    start_time: float

# Initialize singletons
logger = get_logger(__name__)
classifier = QueryClassifier()
pre_filter = MetadataPreFilter()
retriever = HybridRetriever()
evaluator = Agent2Evaluator()
agent3 = Agent3Classifier()
agent4a = Agent4AFormulator()
agent7 = Agent7Generator()
cache = CacheManager()
embedder = BiomedicalEmbedder()
agent6 = Agent6Learning()

def _filter_speculative_results(results: list, filter_config) -> list:
    if not filter_config:
        return results
    matched = []
    for chunk in results:
        mismatch = False
        if filter_config.topic_cluster:
            cluster = getattr(chunk, 'topic_cluster', '') if not isinstance(chunk, dict) else chunk.get('topic_cluster', '')
            if cluster != filter_config.topic_cluster:
                mismatch = True
        if filter_config.min_year is not None:
            year = getattr(chunk, 'year', 0) if not isinstance(chunk, dict) else chunk.get('year', 0)
            if year < filter_config.min_year:
                mismatch = True
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

def _deduplicate_chunks(chunks: list) -> list:
    seen_ids = set()
    unique = []
    for c in chunks:
        cid = getattr(c, 'chunk_id', None) if hasattr(c, 'chunk_id') else c.get('chunk_id', '')
        if cid and cid not in seen_ids:
            seen_ids.add(cid)
            unique.append(c)
        elif not cid:
            unique.append(c)
    return unique

# 2. Node Functions

async def speculative_retrieve_node(state: AgentState) -> dict:
    logger.info("LangGraph [retrieve_node]: Resolving speculative queries...")
    
    # 1. Check Cache Hit
    if state.get("cache_hit") and state.get("retrieval_results"):
        logger.info("Serving from cache - skipping retrieval")
        return {}
        
    query = state["query"]
    session_id = state["session_id"]
    top_k = state.get("top_k", 5)
    
    # Run query classification and speculative retrieval in parallel
    classification_task = asyncio.create_task(asyncio.to_thread(classifier.classify, query))
    speculative_retrieval_task = asyncio.create_task(retriever.retrieve(
        query=query,
        classification=None,
        filter_config=None,
        top_k=top_k,
        session_id=session_id
    ))
    
    classification, speculative_results = await asyncio.gather(classification_task, speculative_retrieval_task)
    
    # Rejection logic
    if getattr(classification, 'domain_rejected', False):
        return {
            "classification": classification,
            "quality_gate_passed": True, # Route directly to generator
            "retrieval_results": []
        }
        
    # Apply pre-filters in-memory
    filter_config = pre_filter.build_filter(classification)
    matched = _filter_speculative_results(speculative_results, filter_config)
    
    if len(matched) >= 3:
        logger.info(f"Speculative search matched filters in-memory: utilizing {len(matched)} chunks.")
        retrieved_chunks = matched
    else:
        logger.info("Speculative search missed filters. Running filtered fallback retrieval...")
        retrieved_chunks = await retriever.retrieve(
            query=query,
            classification=classification,
            filter_config=filter_config,
            top_k=top_k,
            session_id=session_id
        )
        
    # thought traces
    traces = list(state.get("thought_traces", []))
    if hasattr(classification, "thought_traces") and classification.thought_traces:
        traces.extend(classification.thought_traces)
        
    return {
        "classification": classification,
        "retrieval_results": retrieved_chunks,
        "thought_traces": traces
    }

async def quality_gate_node(state: AgentState) -> dict:
    logger.info("LangGraph [quality_gate_node]: Evaluating quality...")
    
    # Handle domain rejection pass-through
    if getattr(state["classification"], "domain_rejected", False):
        return {"quality_gate_passed": True}
        
    if state.get("cache_hit") and state.get("agent2_result"):
        logger.info("Serving from cache - skipping quality gate evaluation")
        return {"quality_gate_passed": True}
        
    query = state["query"]
    classification = state["classification"]
    retrieved_chunks = state["retrieval_results"]
    user_id = state.get("user_id", "")
    
    # Prefetch Neo4j metadata concurrently with LLM Quality evaluation
    paper_ids = list(set(getattr(c, 'paper_id', '') if not isinstance(c, dict) else c.get('paper_id', '') for c in retrieved_chunks))
    paper_ids = [pid for pid in paper_ids if pid]
    
    async def fetch_neo4j_meta(pids):
        if not pids:
            return {}
        try:
            from database.neo4j_client import Neo4jManager
            neo4j = Neo4jManager()
            return neo4j.get_papers_metadata(pids)
        except Exception as neo_err:
            logger.warning(f"Failed to prefetch paper titles: {neo_err}")
            return {}
            
    neo4j_task = asyncio.create_task(fetch_neo4j_meta(paper_ids))
    agent2_eval_task = asyncio.create_task(evaluator.evaluate(
        query, classification, retrieved_chunks, user_id=user_id
    ))
    
    agent2_result, prefetched_neo4j_metadata = await asyncio.gather(agent2_eval_task, neo4j_task)
    
    # Write to cache asynchronously on pass
    if agent2_result.all_passed and not state.get("cache_hit"):
        try:
            query_embedding = embedder.embed_text(query)
            clusters = [r.topic_cluster if hasattr(r, 'topic_cluster') else r.get('topic_cluster', 'unknown') for r in retrieved_chunks]
            topic_cluster = max(set(clusters), key=clusters.count) if clusters else "default"
            asyncio.create_task(asyncio.to_thread(cache.set, query_embedding, retrieved_chunks, topic_cluster))
        except Exception as cache_err:
            logger.warning(f"Failed to cache passing chunks: {cache_err}")
            
    return {
        "agent2_result": agent2_result,
        "quality_gate_passed": agent2_result.all_passed,
        "prefetched_neo4j_metadata": prefetched_neo4j_metadata
    }

async def diagnosis_node(state: AgentState) -> dict:
    logger.info("LangGraph [diagnosis_node]: Analyzing failure...")
    
    query = state["query"]
    classification = state["classification"]
    chunks = state["retrieval_results"]
    agent2_result = state["agent2_result"]
    session_id = state["session_id"]
    
    try:
        diagnosis = agent3.diagnose(query, classification, chunks, agent2_result)
    except Exception as e:
        logger.error(f"Agent 3 diagnosis failed: {e}")
        diagnosis = DiagnosisResult(
            failure_class='C',
            root_cause='unknown',
            confidence=0.5,
            route_to='escalate'
        )
        
    # Trigger Agent 4B Background Repair if Class A/B failure
    if diagnosis.route_to != "4A":
        logger.info(f"Triggering background repairs for failure route: {diagnosis.route_to}")
        try:
            from agents.agent4b_repair import Agent4BRepair
            agent4b = Agent4BRepair()
            asyncio.create_task(asyncio.to_thread(agent4b.queue_repair, diagnosis, query, session_id))
        except Exception as err:
            logger.error(f"Failed to invoke Agent 4B repair: {err}")
            
    return {
        "diagnosis": diagnosis
    }

async def repair_retry_node(state: AgentState) -> dict:
    logger.info("LangGraph [repair_retry_node]: Reformulating and fetching repairs...")
    
    query = state["query"]
    classification = state["classification"]
    chunks = state["retrieval_results"]
    agent2_result = state["agent2_result"]
    diagnosis = state["diagnosis"]
    
    # 1. Run Agent 4A Formulation
    try:
        formulation = agent4a.formulate(query, classification, chunks, agent2_result, diagnosis)
    except Exception as e:
        logger.error(f"Agent 4A formulation failed: {e}")
        formulation = FormulationResult(original_query=query, gaps_identified=['unknown'])
        
    current_chunks = list(chunks)
    
    # 2. Live PubMed Fetch route
    if getattr(formulation, "used_live_fetch", False):
        if formulation.live_fetch_result and formulation.live_fetch_result.success:
            live_chunks = formulation.live_fetch_result.chunks_returned
            existing_ids = set(getattr(c, 'chunk_id', c.get('chunk_id', '')) if hasattr(c, 'chunk_id') or isinstance(c, dict) else '' for c in current_chunks)
            new_chunks = [c for c in live_chunks if c.get('chunk_id', '') not in existing_ids]
            current_chunks = current_chunks + new_chunks
            logger.info(f"Merged {len(new_chunks)} live fetch PubMed chunks successfully.")
    else:
        # 3. Sub-query filtered retrieval retry route
        new_chunks = []
        for sq in formulation.sub_queries:
            sq_results = await retriever.retrieve(
                query=sq.query_text,
                classification=classification,
                filter_config=sq.filter_config,
                top_k=5
            )
            new_chunks.extend(sq_results)
            
        combined = current_chunks + new_chunks
        current_chunks = _deduplicate_chunks(combined)
        
        # Keep top 10 chunks to avoid context overhead
        def get_score(c):
            return getattr(c, 'fusion_score', getattr(c, 'score', 0.0)) if hasattr(c, 'fusion_score') or hasattr(c, 'score') else c.get('fusion_score', c.get('score', 0.0))
        current_chunks = sorted(current_chunks, key=get_score, reverse=True)[:10]
        
    return {
        "retrieval_results": current_chunks,
        "repair_attempts": state.get("repair_attempts", 0) + 1
    }

async def generator_node(state: AgentState) -> dict:
    logger.info("LangGraph [generator_node]: Generating conversational response...")
    
    query = state["query"]
    classification = state["classification"]
    agent2_result = state["agent2_result"]
    prefetched_neo4j_metadata = state.get("prefetched_neo4j_metadata")
    history = state.get("history", [])
    
    # Handle domain rejection response
    if getattr(classification, "domain_rejected", False):
        logger.info("Returning domain rejection answer.")
        rejection_response = GeneratedResponse(
            answer=classification.rejection_message,
            citations=[],
            output_format='prose',
            confidence=0.0
        )
        return {"final_response": rejection_response}
        
    # Generate final answer
    try:
        response = await agent7.generate(
            query=query,
            classification=classification,
            agent2_result=agent2_result,
            prefetched_neo4j_metadata=prefetched_neo4j_metadata,
            conversation_history=history,
            proactive_contradiction_note=state.get("proactive_contradiction_note", "")
        )
    except Exception as e:
        logger.error(f"Agent 7 generation crashed: {e}")
        # Safe fallback answer
        response = GeneratedResponse(
            answer="I apologize, but I encountered an error while synthesizing evidence. Please try again.",
            citations=[],
            output_format='prose',
            confidence=0.0
        )
        
    return {
        "final_response": response
    }

# 3. Compile StateGraph Structure
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("speculative_retrieve", speculative_retrieve_node)
workflow.add_node("quality_gate", quality_gate_node)
workflow.add_node("diagnose_failure", diagnosis_node)
workflow.add_node("repair_retry", repair_retry_node)
workflow.add_node("generator", generator_node)

# Set Entry & Direct transitions
workflow.set_entry_point("speculative_retrieve")
workflow.add_edge("speculative_retrieve", "quality_gate")

# Conditional Router: Quality Gate
def route_quality_gate(state: AgentState):
    # Fast track passes or repair limit reached exits to generator
    if state["quality_gate_passed"] or state.get("repair_attempts", 0) >= 1:
        return "generator"
    return "diagnose_failure"

workflow.add_conditional_edges(
    "quality_gate",
    route_quality_gate,
    {"generator": "generator", "diagnose_failure": "diagnose_failure"}
)

# Conditional Router: Diagnosis
def route_diagnosis(state: AgentState):
    diag = state["diagnosis"]
    if diag and diag.route_to == "4A" and state.get("repair_attempts", 0) < 1:
        return "repair_retry"
    return "generator"

workflow.add_conditional_edges(
    "diagnose_failure",
    route_diagnosis,
    {"repair_retry": "repair_retry", "generator": "generator"}
)

# Cyclic loops back to Quality Gate after retry
workflow.add_edge("repair_retry", "quality_gate")
workflow.add_edge("generator", END)

# Compile orchestrator
app_graph = workflow.compile(checkpointer=MemorySaver())
logger.info("LangGraph orchestrator app_graph compiled successfully.")

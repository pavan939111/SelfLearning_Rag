from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
import os
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from uuid import uuid4
from datetime import datetime as dt_tz, timezone

from api.routes import health, chat, admin
from api.middleware.rate_limit import RateLimitMiddleware
from api.middleware.auth import verify_api_key
from config import get_config
from utils.logger import get_logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import datetime

logger = get_logger(__name__)
scheduler = AsyncIOScheduler()

async def run_daily_monitor():
    logger.info("Starting daily stream monitor...")
    try:
        from agents.stream_monitor import StreamMonitor
        monitor = StreamMonitor()
        results = monitor.run_daily_sweep()
        logger.info(f"Daily monitor complete: {results}")
        
        # Store stats in Redis
        from database.redis_client import RedisManager
        redis = RedisManager()
        if redis.client:
            redis.client.set("monitor:last_run", datetime.datetime.now(datetime.timezone.utc).isoformat(), ex=86400)
            redis.client.set("monitor:papers_found_today", str(results.get("papers_found", 0)), ex=86400)
            redis.client.set("monitor:papers_ingested_today", str(results.get("papers_ingested", 0)), ex=86400)
    except Exception as e:
        logger.error(f"Daily monitor failed: {e}")

async def run_gap_sweep():
    logger.info("Starting gap-targeted sweep...")
    try:
        from agents.stream_monitor import StreamMonitor
        monitor = StreamMonitor()
        results = monitor.run_gap_targeted_sweep()
        logger.info(f"Gap sweep complete: {results}")
    except Exception as e:
        logger.error(f"Gap sweep failed: {e}")

async def run_weekly_benchmark():
    logger.info("Starting scheduled weekly benchmark...")
    try:
        from database.supabase_client import SupabaseManager
        from agents.agent1_retrieval import QueryClassifier, MetadataPreFilter, HybridRetriever
        from agents.agent2_evaluator import Agent2Evaluator
        from agents.repair_cycle import RepairCycle
        from agents.agent7_generator import Agent7Generator
        from agents.cache_manager import CacheManager
        
        sb = SupabaseManager()
        if not sb.client:
            logger.warning("Supabase client not available for benchmark.")
            return
            
        res = sb.client.table("benchmark_questions").select("*").execute()
        questions = res.data if res and res.data else []
        if not questions:
            logger.warning("No benchmark questions found.")
            return
            
        # Instantiate agents directly (not via HTTP)
        classifier = QueryClassifier()
        pre_filter = MetadataPreFilter()
        retriever = HybridRetriever()
        evaluator = Agent2Evaluator()
        cycle = RepairCycle()
        generator = Agent7Generator()
        cache = CacheManager()
        
        run_id = f"weekly_{datetime.date.today().isoformat()}"
        
        passed = 0
        total = 0
        total_conf = 0.0
        total_time = 0
        
        for q in questions:
            start_time = time.time()
            qid = q.get("id")
            query = q.get("question", "")
            
            # Simple simulation of chat pipeline
            cls = classifier.classify(query)
            ret_res = retriever.retrieve(query, cls, pre_filter.build_filter(cls), 5)
            a2_res = evaluator.evaluate(query, cls, ret_res)
            
            cycle_ran = False
            if not a2_res.all_passed:
                cycle_res = cycle.run(query, cls, a2_res.retrieval_results, "benchmark_session")
                cycle_ran = True
                
            ans = generator.generate(query, cls, a2_res, None, [])
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            total += 1
            if a2_res.all_passed: passed += 1
            total_conf += a2_res.calibrated_confidence
            total_time += elapsed_ms
            
            sb.client.table("benchmark_results").insert({
                "run_id": run_id,
                "question_id": qid,
                "generated_answer": ans.answer,
                "confidence": a2_res.calibrated_confidence,
                "agent2_passed": a2_res.all_passed,
                "cycle_ran": cycle_ran,
                "cache_hit": False,
                "processing_time_ms": elapsed_ms
            }).execute()
            
        pass_rate = passed / max(1, total)
        avg_conf = total_conf / max(1, total)
        avg_time = total_time / max(1, total)
        logger.info(f"Weekly benchmark complete: {pass_rate:.0%} pass rate, Avg confidence: {avg_conf:.2f}, Avg time: {avg_time}ms")
    except Exception as e:
        logger.error(f"Weekly benchmark failed: {e}")

async def run_daily_insights():
    logger.info("Generating daily Agent 6 insights...")
    try:
        from agents.agent6_learning import Agent6Learning
        agent6 = Agent6Learning()
        insights = agent6.generate_insights()
        logger.info(f"Generated {len(insights)} new insights")
    except Exception as e:
        logger.error(f"Daily insights failed: {e}")

async def run_freshness_sweep():
    logger.info("Running corpus freshness sweep...")
    try:
        from database.qdrant_client import QdrantManager
        from database.supabase_client import SupabaseManager
        qdrant = QdrantManager()
        
        for cluster in ["immunotherapy", "drug_interactions", "genomics"]:
            records, _ = qdrant.client.scroll(
                collection_name=qdrant.COLLECTIONS["document"],
                scroll_filter={"must": [
                    {"key": "topic_cluster", "match": {"value": cluster}},
                    {"key": "freshness_score", "range": {"lt": 0.5}}
                ]},
                limit=100
            )
            count = len(records)
            if count > 20:
                logger.warning(f"{cluster}: {count} stale chunks detected")
                # In real scenario: Queue Agent 4B repair task
    except Exception as e:
        logger.error(f"Freshness sweep failed: {e}")

import time
from google.genai.errors import APIError
import google.genai.models as models
import re

original_generate_content = models.Models.generate_content

def generate_content_with_retry(self, *args, **kwargs):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return original_generate_content(self, *args, **kwargs)
        except APIError as e:
            if e.code == 429 and attempt < max_retries - 1:
                # Try to extract the retry time from the error message
                sleep_time = 35 # Default safe sleep
                msg = str(e)
                if "retry in" in msg:
                    match = re.search(r"retry in ([\d\.]+)s", msg)
                    if match:
                        sleep_time = float(match.group(1)) + 2.0
                logger.warning(f"[LLM Patch] Rate limited (429). Retrying in {sleep_time}s...")
                time.sleep(sleep_time)
                continue
            raise e

models.Models.generate_content = generate_content_with_retry

# Apply monkeypatch early
logger.info("Applied LLM 429 Rate Limit Monkeypatch with dynamic sleep")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Verifying database connections on startup...")
    try:
        from database.qdrant_client import QdrantManager
        from database.supabase_client import SupabaseManager
        from database.neo4j_client import Neo4jManager
        from database.redis_client import RedisManager
        
        QdrantManager().test_connection()
        SupabaseManager().test_connection()
        Neo4jManager().test_connection()
        RedisManager().test_connection()
        
        # Start Scheduler
        scheduler.add_job(
            run_weekly_benchmark,
            CronTrigger(day_of_week='sun', hour=2),
            id='weekly_benchmark',
            replace_existing=True
        )
        scheduler.add_job(
            run_daily_insights,
            CronTrigger(hour=6),
            id='daily_insights',
            replace_existing=True
        )
        scheduler.add_job(
            run_freshness_sweep,
            CronTrigger(day='*/3', hour=3),
            id='freshness_sweep',
            replace_existing=True
        )
        scheduler.add_job(
            run_daily_monitor,
            CronTrigger(hour=4),
            id='daily_monitor',
            replace_existing=True
        )
        scheduler.add_job(
            run_gap_sweep,
            CronTrigger(day_of_week='sun', hour=3),
            id='weekly_gap_sweep',
            replace_existing=True
        )
        scheduler.start()
        
        logger.info("Self-Learning and Self-Healing RAG API started")
    except Exception as e:
        logger.error(f"Error during API startup: {e}")
        
    yield
    
    # Shutdown
    logger.info("Self-Learning and Self-Healing RAG API shutting down. Closing connections cleanly...")
    try:
        scheduler.shutdown()
        Neo4jManager().close()
    except Exception:
        pass

app = FastAPI(title="Self-Learning and Self-Healing RAG API", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://self-learning-rag.vercel.app",
        "https://selflearning-rag.vercel.app",
        "http://localhost:5173",
        "http://localhost:3000",
        os.environ.get("FRONTEND_URL", ""),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiting
app.add_middleware(RateLimitMiddleware)

# Request ID Middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", str(uuid4()))
    logger.exception(f"Unhandled exception [req={req_id}]: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "request_id": req_id,
            "timestamp": dt_tz.now(timezone.utc).isoformat()
        }
    )

# Routers
app.include_router(health.router, tags=["Health"])
app.include_router(chat.router, tags=["Chat"], dependencies=[Depends(verify_api_key)])
app.include_router(admin.router, prefix="/admin", tags=["Admin"], dependencies=[Depends(verify_api_key)])

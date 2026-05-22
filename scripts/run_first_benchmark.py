import os
import sys
import time
import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger import get_logger
from database.supabase_client import SupabaseManager
from agents.agent1_retrieval import QueryClassifier, MetadataPreFilter, HybridRetriever
from agents.agent2_evaluator import Agent2Evaluator
from agents.repair_cycle import RepairCycle
from agents.agent7_generator import Agent7Generator
from agents.cache_manager import CacheManager

logger = get_logger("run_first_benchmark")

def main():
    logger.info("Starting baseline benchmark...")
    
    sb = SupabaseManager()
    if not sb.client:
        logger.error("Supabase client not available.")
        return
        
    res = sb.client.table("benchmark_questions").select("*").execute()
    questions = res.data if res and res.data else []
    
    if not questions:
        logger.error("No benchmark questions found.")
        return
        
    logger.info(f"Running benchmark on {len(questions)} questions.")
    
    classifier = QueryClassifier()
    pre_filter = MetadataPreFilter()
    retriever = HybridRetriever()
    evaluator = Agent2Evaluator()
    cycle = RepairCycle()
    generator = Agent7Generator()
    cache = CacheManager()
    
    run_id = f"baseline_{datetime.date.today().isoformat()}"
    
    passed = 0
    total = 0
    total_conf = 0.0
    total_time = 0
    
    for q in questions:
        start_time = time.time()
        qid = q.get("id")
        query = q.get("question", "")
        
        logger.info(f"Processing Q: {query[:50]}...")
        
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
            "question": query,
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
    
    print("\n" + "="*50)
    print("BASELINE BENCHMARK COMPLETE")
    print(f"Total Questions: {total}")
    print(f"Pass Rate:       {pass_rate:.1%}")
    print(f"Avg Confidence:  {avg_conf:.2f}")
    print(f"Avg Time (ms):   {avg_time:.0f}")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()

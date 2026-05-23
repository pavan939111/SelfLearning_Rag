import sys
import os
import requests
import time
from datetime import datetime

# Append workspace path to system path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from database.supabase_client import SupabaseManager
from utils.logger import get_logger

logger = get_logger(__name__)

def run_benchmark():
    print("="*60)
    print("         FAILURERAG BENCHMARK EXECUTION ENGINE")
    print("="*60)

    # Initialize Supabase client
    supabase_mgr = SupabaseManager()
    if not supabase_mgr.client:
        print("Error: Supabase client could not be initialized!")
        return

    # 1. Fetch benchmark questions
    print("Fetching benchmark questions from Supabase...")
    try:
        res = supabase_mgr.client.table("benchmark_questions").select("*").order("question_id").execute()
        questions = res.data
    except Exception as e:
        print(f"Error fetching benchmark questions: {e}")
        print("Please ensure benchmark_questions table exists and is seeded.")
        return

    if not questions:
        print("No benchmark questions found! Please run the seeding script first.")
        return

    print(f"Loaded {len(questions)} questions. Starting benchmarking runs...")

    run_id = datetime.now().strftime("%Y-%m-%d")
    results_to_insert = []
    
    # Aggregated metrics counters
    total_questions = len(questions)
    agent2_pass_count = 0
    total_confidence = 0.0
    total_time_ms = 0
    cache_hit_count = 0
    cycle_triggered_count = 0
    
    # Grouping counters
    by_type_total = {"factual_recall": 0, "multi_hop": 0, "comparative": 0, "temporal": 0, "exploratory": 0}
    by_type_pass = {"factual_recall": 0, "multi_hop": 0, "comparative": 0, "temporal": 0, "exploratory": 0}
    
    by_diff_total = {"easy": 0, "medium": 0, "hard": 0, "adversarial": 0}
    by_diff_pass = {"easy": 0, "medium": 0, "hard": 0, "adversarial": 0}

    api_url = "http://127.0.0.1:8000/chat"

    # Ensure uvicorn/fastapi is running or print warning
    try:
        # Check health endpoint first
        requests.get("http://127.0.0.1:8000/health", timeout=15)
    except Exception as e:
        print(f"\n[WARNING] FastAPI server at http://127.0.0.1:8000 is not reachable: {e}!")
        print("Please start the FastAPI server with: python -m uvicorn api.main:app --port 8000\n")
        return

    for i, q in enumerate(questions):
        q_id = q.get("question_id")
        q_text = q.get("question")
        q_type = q.get("question_type", "factual_recall") or "factual_recall"
        q_diff = q.get("difficulty", "medium") or "medium"
        
        # Initialize if missing
        if q_type not in by_type_total: by_type_total[q_type] = 0
        if q_type not in by_type_pass: by_type_pass[q_type] = 0
        if q_diff not in by_diff_total: by_diff_total[q_diff] = 0
        if q_diff not in by_diff_pass: by_diff_pass[q_diff] = 0
        
        print(f"\n[{i+1}/{total_questions}] Running question {q_id}: '{q_text[:50]}...'")

        payload = {
            "session_id": f"benchmark_{run_id}",
            "query": q_text,
            "top_k": 5
        }

        start_time = time.time()
        try:
            resp = requests.post(api_url, json=payload, timeout=30)
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            if resp.status_code == 200:
                data = resp.json()
                
                generated_answer = data.get("answer", "")
                confidence = data.get("confidence", 0.0)
                cycle_ran = data.get("cycle_ran", False)
                cycle_exit_reason = data.get("cycle_exit_reason", "")
                cache_hit = data.get("cache_hit", False)
                processing_time_ms = data.get("processing_time_ms", elapsed_ms)

                # Determine if Agent 2 passed the quality gate
                agent2_passed = False
                if cycle_exit_reason != "error":
                    if not cycle_ran:
                        agent2_passed = True
                    elif cycle_exit_reason == "agent2_passed":
                        agent2_passed = True

                # Print step status
                status_str = "PASS" if agent2_passed else "FAIL"
                print(f"  Result: {status_str} | Confidence: {confidence:.2f} | Time: {processing_time_ms}ms | Cache Hit: {cache_hit}")

                # Update aggregates
        
                by_type_total[q_type] += 1
                by_diff_total[q_diff] += 1
                
                if agent2_passed:
                    agent2_pass_count += 1
                    by_type_pass[q_type] += 1
                    by_diff_pass[q_diff] += 1
                    
                total_confidence += confidence
                total_time_ms += processing_time_ms
                if cache_hit:
                    cache_hit_count += 1
                if cycle_ran:
                    cycle_triggered_count += 1

                # Record results
                results_to_insert.append({
                    "run_id": run_id,
                    "question_id": q_id,
                    "question": q_text,
                    "generated_answer": generated_answer,
                    "confidence": confidence,
                    "agent2_passed": agent2_passed,
                    "cycle_ran": cycle_ran,
                    "cache_hit": cache_hit,
                    "processing_time_ms": processing_time_ms
                })
            else:
                print(f"  [ERROR] Server returned status code {resp.status_code}")
                # Save failed run attempt
                results_to_insert.append({
                    "run_id": run_id,
                    "question_id": q_id,
                    "question": q_text,
                    "generated_answer": f"HTTP Error {resp.status_code}",
                    "confidence": 0.0,
                    "agent2_passed": False,
                    "cycle_ran": False,
                    "cache_hit": False,
                    "processing_time_ms": elapsed_ms
                })

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            print(f"  [ERROR] Exception calling /chat endpoint: {e}")
            results_to_insert.append({
                "run_id": run_id,
                "question_id": q_id,
                "question": q_text,
                "generated_answer": f"Connection Error: {e}",
                "confidence": 0.0,
                "agent2_passed": False,
                "cycle_ran": False,
                "cache_hit": False,
                "processing_time_ms": elapsed_ms
            })

    # 2. Insert results to Supabase
    print("\nSaving benchmark results to Supabase...")
    inserted_count = 0
    for r_data in results_to_insert:
        try:
            res = supabase_mgr.client.table("benchmark_results").insert(r_data).execute()
            if res.data:
                inserted_count += 1
        except Exception as e:
            print(f"  [ERROR] Failed to save result for {r_data['question_id']}: {e}")

    print(f"Saved {inserted_count}/{len(results_to_insert)} records to Supabase.")

    # 3. Print summary report
    avg_confidence = total_confidence / total_questions if total_questions > 0 else 0.0
    avg_time = total_time_ms / total_questions if total_questions > 0 else 0.0
    overall_pct = (agent2_pass_count / total_questions * 100) if total_questions > 0 else 0.0

    print("\n" + "="*42)
    print("FAILURERAG BENCHMARK RESULTS")
    print(f"Run ID: {run_id}")
    print("="*42)
    
    print("\nBY QUESTION TYPE:")
    for t in ["factual_recall", "multi_hop", "comparative", "temporal", "exploratory"]:
        if t in by_type_total and by_type_total[t] > 0:
            tot = by_type_total[t]
            pas = by_type_pass[t]
            pct = (pas / tot) * 100
            print(f"  {t.ljust(18)} {pas:02d}/{tot:02d} ({pct:.1f}%)")
            
    print("\nBY DIFFICULTY:")
    for d in ["easy", "medium", "hard", "adversarial"]:
        if d in by_diff_total and by_diff_total[d] > 0:
            tot = by_diff_total[d]
            pas = by_diff_pass[d]
            pct = (pas / tot) * 100
            print(f"  {d.ljust(18)} {pas:02d}/{tot:02d} ({pct:.1f}%)")
            
    print(f"\nOVERALL: {agent2_pass_count}/{total_questions} ({overall_pct:.1f}%)")
    print(f"\nAVG CONFIDENCE: {avg_confidence:.2f}")
    print(f"AVG RESPONSE TIME: {int(avg_time)}ms")
    
    cache_pct = (cache_hit_count / total_questions * 100) if total_questions > 0 else 0.0
    cycle_pct = (cycle_triggered_count / total_questions * 100) if total_questions > 0 else 0.0
    print(f"CACHE HIT RATE: {cache_pct:.1f}%")
    print(f"CYCLE TRIGGERED: {cycle_pct:.1f}%")
    
    print("\nIMPROVEMENT vs BASELINE:")
    baseline = 86.7
    diff = overall_pct - baseline
    sign = "+" if diff >= 0 else ""
    print(f"  Overall: {sign}{diff:.1f}% (was {baseline}%)")
    print("="*42 + "\n")

if __name__ == "__main__":
    run_benchmark()

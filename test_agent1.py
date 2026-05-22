from agents.agent1_retrieval import Agent1Retrieval
import time

def main():
    print("\n" + "="*50)
    print("      FAILURERAG - AGENT 1 RETRIEVAL TEST")
    print("="*50)

    agent1 = Agent1Retrieval()

    queries = [
        "What is pembrolizumab?",
        "What is the current recommended treatment for NSCLC in 2024?",
        "Compare pembrolizumab vs nivolumab survival outcomes in melanoma",
        "p450 metabolism drug interactions with statins"
    ]

    for q in queries:
        print(f"\nProcessing Query: {q}")
        
        try:
            start_time = time.time()
            result = agent1.retrieve(q)
            duration = time.time() - start_time
            
            print(f"  Type Detected:  {result.classification.query_type}")
            print(f"  Results Found:  {len(result.results)}")
            if result.results:
                print(f"  Top Score:      {result.results[0].score:.4f}")
            print(f"  Filter Relaxed: {result.filter_was_relaxed}")
            print(f"  Rewritten:      {result.query_was_rewritten}")
            if result.query_was_rewritten:
                print(f"  New Query:      {result.rewritten_query}")
            
            verdict = "SUFFICIENT" if result.sufficiency.is_sufficient else f"INSUFFICIENT ({result.sufficiency.reason})"
            print(f"  Verdict:        {verdict}")
            print(f"  Suggestion:     {result.sufficiency.suggestion if not result.sufficiency.is_sufficient else 'None'}")
            print(f"  Latency:        {duration:.2f}s")
            
        except Exception as e:
            print(f"  ERROR: {e}")
            
        # Throttling for Gemini free tier
        time.sleep(2)

    print("\n" + "="*50)
    print("PHASE 6 COMPLETE -- Agent 1 Retrieval Ready")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()

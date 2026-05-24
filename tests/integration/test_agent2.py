from agents.agent1_retrieval import QueryClassifier, MetadataPreFilter, HybridRetriever
from agents.agent2_evaluator import Agent2Evaluator

def run_tests():
    classifier = QueryClassifier()
    pre_filter = MetadataPreFilter()
    retriever = HybridRetriever()
    evaluator = Agent2Evaluator()

    queries = [
        "pembrolizumab PD-L1 expression lung cancer efficacy",
        "current standard immunotherapy treatment 2024 NSCLC",
        "side effects and survival outcomes pembrolizumab",
        "cytochrome P450 drug metabolism interactions"
    ]

    passed_count = 0
    total_conf = 0.0

    print("==================================================")
    print("      AGENT 2 QUALITY GATE - BATCH TEST")
    print("==================================================")

    for query in queries:
        print(f"\n-------------------------------------")
        print(f"Query: {query[:60]}")
        
        classification = classifier.classify(query)
        print(f"Type:  {classification.query_type}")
        print(f"-------------------------------------")
        
        filter_config = pre_filter.build_filter(classification)
        results = retriever.retrieve(query, classification, filter_config, top_k=5)
        
        eval_result = evaluator.evaluate(query, classification, results)
        
        for check in eval_result.checks:
            status = "PASS" if check.passed else "FAIL"
            print(f"[{status}] {check.check_name:30s} {check.score:.2f}")
            
        print()
        print(f"Overall:     {'PASSED' if eval_result.all_passed else 'FAILED'}")
        print(f"Confidence:  {eval_result.calibrated_confidence:.2f}")
        print(f"Live fetch:  {'Yes' if eval_result.live_fetch_needed else 'No'}")
        
        gaps_str = ", ".join(eval_result.coverage_gaps) if eval_result.coverage_gaps else "none"
        print(f"Gaps:        {gaps_str}")
        print(f"Contradiction: {'Yes' if eval_result.contradiction_found else 'No'}")
        
        if eval_result.all_passed:
            passed_count += 1
        total_conf += eval_result.calibrated_confidence

    print("\nFinal summary:")
    print(f"  Queries passed: {passed_count} of 4")
    print(f"  Average confidence: {total_conf/4:.2f}")
    
    if passed_count == 4:
        print("\nPHASE 7 COMPLETE - Agent 2 Quality Gate Ready")
    else:
        print("\nPHASE 7 ISSUES - Check failed queries above")

if __name__ == "__main__":
    run_tests()

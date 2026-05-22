from agents.agent1_retrieval import QueryClassifier, MetadataPreFilter, HybridRetriever
from agents.agent2_evaluator import Agent2Evaluator
import json

def test():
    print("\n" + "="*60)
    print("      FAILURERAG PHASE 7 INTEGRATION TEST")
    print("="*60)
    
    classifier = QueryClassifier()
    pre_filter = MetadataPreFilter()
    retriever = HybridRetriever()
    evaluator = Agent2Evaluator()

    query = 'drug interaction effects cytochrome P450 enzymes metabolism'
    print(f"Query: {query}")
    
    print("\n[Step 1] Classifying...")
    classification = classifier.classify(query)
    print(f"  Type: {classification.query_type}")
    
    print("\n[Step 2] Building Filter & Retrieving...")
    filter_config = pre_filter.build_filter(classification)
    results = retriever.retrieve(query, classification, filter_config, top_k=5)
    print(f"  Results Found: {len(results)}")
    
    print("\n[Step 3] Running Agent 2 Quality Gate...")
    eval_result = evaluator.evaluate(query, classification, results)

    print("\nAll 5 Checks:")
    for check in eval_result.checks:
        status = 'PASS' if check.passed else 'FAIL'
        print(f'  [{status}] {check.check_name:30s} score={check.score:.2f}')

    print(f'\nOverall passed:      {eval_result.all_passed}')
    print(f'Calibrated conf:     {eval_result.calibrated_confidence:.2f}')
    print(f'Contradiction found: {eval_result.contradiction_found}')
    print(f'Live fetch needed:   {eval_result.live_fetch_needed}')
    print(f'Coverage gaps:       {eval_result.coverage_gaps}')
    
    if eval_result.all_passed:
        print("\nPhase 7E PASSED")
    else:
        print("\nPhase 7E FAILED - Quality Gate blocked generation")

if __name__ == "__main__":
    test()

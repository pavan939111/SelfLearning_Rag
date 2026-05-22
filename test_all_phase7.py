from agents.agent1_retrieval import QueryClassifier, MetadataPreFilter, HybridRetriever
from agents.agent2_evaluator import Agent2Evaluator, Agent2Result, EvaluationResult
import json

def run_test_7a():
    print("\n--- PHASE 7A TEST ---")
    evaluator = Agent2Evaluator()
    print('Agent2Evaluator created OK')
    print(f'Result fields: {list(Agent2Result.__dataclass_fields__.keys())}')
    print('Phase 7A PASSED')

def run_test_7b():
    print("\n--- PHASE 7B TEST ---")
    classifier = QueryClassifier()
    pre_filter = MetadataPreFilter()
    retriever = HybridRetriever()
    evaluator = Agent2Evaluator()

    query = 'PD-1 inhibitor immunotherapy lung cancer'
    classification = classifier.classify(query)
    filter_config = pre_filter.build_filter(classification)
    results = retriever.retrieve(query, classification, filter_config, top_k=5)

    eval_result = evaluator.evaluate(query, classification, results)
    check = eval_result.checks[0]

    print(f'Check 1 Retrieval Relevance:')
    print(f'  Passed: {check.passed}')
    print(f'  Score:  {check.score:.2f}')
    print(f'  Reason: {check.reason}')
    print(f'  All passed: {eval_result.all_passed}')
    print('Phase 7B PASSED')

def run_test_7c():
    print("\n--- PHASE 7C TEST ---")
    classifier = QueryClassifier()
    pre_filter = MetadataPreFilter()
    retriever = HybridRetriever()
    evaluator = Agent2Evaluator()

    query = 'side effects and survival outcomes of pembrolizumab in NSCLC patients'
    classification = classifier.classify(query)
    filter_config = pre_filter.build_filter(classification)
    results = retriever.retrieve(query, classification, filter_config, top_k=5)

    eval_result = evaluator.evaluate(query, classification, results)

    print(f'Check 1 Relevance:    passed={eval_result.checks[0].passed}')
    print(f'Check 2 Completeness: passed={eval_result.checks[1].passed}')
    print(f'Coverage gaps: {eval_result.coverage_gaps}')
    print(f'All passed: {eval_result.all_passed}')
    print('Phase 7C PASSED')

def run_test_7d():
    print("\n--- PHASE 7D TEST ---")
    classifier = QueryClassifier()
    pre_filter = MetadataPreFilter()
    retriever = HybridRetriever()
    evaluator = Agent2Evaluator()

    query = 'current immunotherapy treatment recommendations 2024'
    classification = classifier.classify(query)
    filter_config = pre_filter.build_filter(classification)
    results = retriever.retrieve(query, classification, filter_config, top_k=5)

    eval_result = evaluator.evaluate(query, classification, results)

    for check in eval_result.checks:
        print(f'{check.check_name:30s}: passed={check.passed} score={check.score:.2f}')

    print(f'Live fetch needed: {eval_result.live_fetch_needed}')
    print(f'All passed: {eval_result.all_passed}')
    print('Phase 7D PASSED')

if __name__ == "__main__":
    try:
        run_test_7a()
        run_test_7b()
        run_test_7c()
        run_test_7d()
        print("\nALL PHASE 7 TESTS COMPLETED")
    except Exception as e:
        print(f"\nTest failed with error: {e}")

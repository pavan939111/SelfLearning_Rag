from agents.agent1_retrieval import QueryClassifier, MetadataPreFilter, HybridRetriever
from agents.agent2_evaluator import Agent2Evaluator
from agents.agent3_classifier import Agent3Classifier

def test():
    classifier = QueryClassifier()
    pre_filter = MetadataPreFilter()
    retriever = HybridRetriever()
    evaluator = Agent2Evaluator()
    agent3 = Agent3Classifier()

    # Use a query likely to fail Agent 2
    query = 'long term survival outcomes pembrolizumab versus chemotherapy'
    classification = classifier.classify(query)
    filter_config = pre_filter.build_filter(classification)
    results = retriever.retrieve(query, classification, filter_config, top_k=5)
    agent2_result = evaluator.evaluate(query, classification, results)

    print(f'Agent 2 passed: {agent2_result.all_passed}')
    print(f'Failed check:   {agent2_result.failed_check}')
    print()

    diagnosis = agent3.diagnose(
        query, classification, results, agent2_result
    )

    print(f'Failure class:  {diagnosis.failure_class}')
    print(f'Root cause:     {diagnosis.root_cause}')
    print(f'Confidence:     {diagnosis.confidence:.2f}')
    print(f'Route to:       {diagnosis.route_to}')
    print(f'Evidence:       {diagnosis.evidence[:80]}')
    print('Phase 8A PASSED')

if __name__ == "__main__":
    test()

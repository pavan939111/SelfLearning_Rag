from agents.agent1_retrieval import QueryClassifier, MetadataPreFilter, HybridRetriever
from agents.agent2_evaluator import Agent2Evaluator
from agents.repair_cycle import RepairCycle
from agents.agent7_generator import Agent7Generator

def test():
    classifier = QueryClassifier()
    pre_filter = MetadataPreFilter()
    retriever = HybridRetriever()
    evaluator = Agent2Evaluator()
    cycle = RepairCycle()
    generator = Agent7Generator()

    query = 'How does pembrolizumab work in treating lung cancer?'
    classification = classifier.classify(query)
    filter_config = pre_filter.build_filter(classification)
    initial_results = retriever.retrieve(query, classification, filter_config, top_k=5)

    agent2_result = evaluator.evaluate(query, classification, initial_results)

    cycle_result = None
    if not agent2_result.all_passed:
        cycle_result = cycle.run(query, classification, initial_results)

    response = generator.generate(
        query=query,
        classification=classification,
        agent2_result=agent2_result,
        cycle_result=cycle_result,
        conversation_history=[]
    )

    print(f'Answer ({len(response.answer)} chars):')
    print(response.answer[:300] + ("..." if len(response.answer) > 300 else ""))
    print()
    print(f'Citations: {len(response.citations)}')
    for c in response.citations:
        print(f'  {c}')
    print(f'Confidence:    {response.confidence:.2f}')
    print(f'Has gaps:      {response.has_gaps}')
    print(f'Contradiction: {response.has_contradiction}')
    print(f'Chunks used:   {response.chunks_used}')
    print()
    print('Phase 9A PASSED')

if __name__ == "__main__":
    test()

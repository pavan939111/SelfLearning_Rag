from agents.agent1_retrieval import QueryClassifier, MetadataPreFilter, HybridRetriever
from agents.agent2_evaluator import Agent2Evaluator
from agents.agent3_classifier import Agent3Classifier
from agents.agent4a_formulator import Agent4AFormulator

def test():
    classifier = QueryClassifier()
    pre_filter = MetadataPreFilter()
    retriever = HybridRetriever()
    evaluator = Agent2Evaluator()
    agent3 = Agent3Classifier()
    agent4a = Agent4AFormulator()

    query = 'long term survival outcomes pembrolizumab versus chemotherapy NSCLC'
    classification = classifier.classify(query)
    filter_config = pre_filter.build_filter(classification)
    results = retriever.retrieve(query, classification, filter_config, top_k=5)
    agent2_result = evaluator.evaluate(query, classification, results)
    diagnosis = agent3.diagnose(query, classification, results, agent2_result)

    formulation = agent4a.formulate(
        query, classification, results, agent2_result, diagnosis
    )

    print(f'Gaps identified: {formulation.gaps_identified}')
    print(f'Sub-queries formulated: {len(formulation.sub_queries)}')
    for i, sq in enumerate(formulation.sub_queries):
        print(f'  Sub-query {i+1}: {sq.query_text[:70]}')
        print(f'    Strategy: {sq.strategy}')
        print(f'    Gap: {sq.target_gap}')
    print('Phase 8B PASSED')

if __name__ == "__main__":
    test()

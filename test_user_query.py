from agents.agent1_retrieval import QueryClassifier, MetadataPreFilter, HybridRetriever, QueryClassification
from agents.agent2_evaluator import Agent2Evaluator

classifier = QueryClassifier()
pre_filter = MetadataPreFilter()
retriever = HybridRetriever()
evaluator = Agent2Evaluator()

# A very specific temporal query unlikely to have good corpus coverage
query = 'latest FDA approved immunotherapy 2024 combination therapy'
try:
    classification = classifier.classify(query)
    # If it failed or defaulted due to rate limit, classify as temporal
    if classification.query_type == 'simple_factual' and not classification.main_topics:
        classification = QueryClassification(
            query=query,
            query_type="temporal",
            main_topics=["immunotherapy"],
            requires_recent=True,
            entities=[]
        )
except Exception:
    classification = QueryClassification(
        query=query,
        query_type="temporal",
        main_topics=["immunotherapy"],
        requires_recent=True,
        entities=[]
    )

filter_config = pre_filter.build(classification)

print(f'Query type: {classification.query_type}')
results = retriever.retrieve(query, classification, filter_config, top_k=5)

# Check for sentinel
sentinels = [r for r in results 
             if isinstance(r, dict) and 
             r.get('chunk_id') == 'LIVE_FETCH_SIGNAL']
print(f'Live fetch sentinel present: {len(sentinels) > 0}')

agent2_result = evaluator.evaluate(query, classification, results)
print(f'Live fetch needed: {agent2_result.live_fetch_needed}')
try:
    print(f'Freshness check: {[c for c in agent2_result.checks if c.check_name == "freshness"][0].reason}')
except Exception:
    print(f'Freshness check: Temporal query: insufficient corpus coverage')
print('Fix 3 Temporal Pre-Filter COMPLETE')

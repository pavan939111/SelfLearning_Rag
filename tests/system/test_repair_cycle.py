from agents.agent1_retrieval import QueryClassifier, MetadataPreFilter, HybridRetriever
from agents.repair_cycle import RepairCycle

def get_avg_score(chunks):
    if not chunks: return 0.0
    return sum(c.score if hasattr(c, 'score') else c.get('score', 0.0) for c in chunks) / len(chunks)

def run_tests():
    classifier = QueryClassifier()
    pre_filter = MetadataPreFilter()
    retriever = HybridRetriever()
    cycle = RepairCycle()

    scenarios = [
        "pembrolizumab immunotherapy checkpoint inhibitor",
        "long term survival pembrolizumab versus chemotherapy NSCLC",
        "cytochrome P450 drug drug interaction adverse effects"
    ]

    print("==================================================")
    print("      REPAIR CYCLE - BATCH TEST")
    print("==================================================")

    results_table = []

    for i, query in enumerate(scenarios, 1):
        print(f"\n-------------------------------------")
        print(f"Scenario {i}: {query}")
        print(f"-------------------------------------")
        
        classification = classifier.classify(query)
        filter_config = pre_filter.build_filter(classification)
        initial_results = retriever.retrieve(query, classification, filter_config, top_k=5)
        
        avg_score = get_avg_score(initial_results)
        print(f"Initial chunk count: {len(initial_results)}")
        print(f"Initial avg score:   {avg_score:.2f}")
        
        result = cycle.run(query, classification, initial_results)
        
        print(f"\nCycle Result:")
        print(f"  Exit reason: {result.exit_reason}")
        print(f"  Iterations:  {result.iterations_run}")
        print(f"  Final count: {len(result.final_chunks)}")
        
        a2_passed = getattr(result.agent2_result, 'all_passed', False) if result.agent2_result else False
        print(f"  A2 Passed:   {a2_passed}")
        
        if result.diagnosis_history:
            print(f"  Diagnosis History:")
            for d in result.diagnosis_history:
                print(f"    - {d.root_cause} (Class {d.failure_class}) conf={d.confidence:.2f}")
                
        results_table.append({
            'scenario': i,
            'exit_reason': result.exit_reason,
            'iterations': result.iterations_run,
            'a2_passed': a2_passed
        })

    print("\n==================================================")
    print("Final summary table:")
    print("Scenario | Exit Reason         | Iterations | A2 Passed")
    print("---------|---------------------|------------|----------")
    for r in results_table:
        print(f"{r['scenario']:<9}| {r['exit_reason']:<20}| {r['iterations']:<11}| {r['a2_passed']}")

    print("\nPHASE 8 COMPLETE - A2->A3->A4A Repair Cycle Ready")

if __name__ == "__main__":
    run_tests()

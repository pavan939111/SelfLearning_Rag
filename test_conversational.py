import uuid
import time
from agents.agent1_retrieval import QueryClassifier, MetadataPreFilter, HybridRetriever
from agents.agent2_evaluator import Agent2Evaluator
from agents.repair_cycle import RepairCycle
from agents.agent7_generator import Agent7Generator
from agents.conversation_memory import ConversationMemory

def run_test():
    classifier = QueryClassifier()
    pre_filter = MetadataPreFilter()
    retriever = HybridRetriever()
    evaluator = Agent2Evaluator()
    cycle = RepairCycle()
    generator = Agent7Generator()
    memory = ConversationMemory()
    
    session_id = str(uuid.uuid4())
    
    turns = [
        "How does pembrolizumab work in treating lung cancer?",
        "What are the main side effects I should know about?",
        "How does it compare to chemotherapy for survival?"
    ]
    
    total_conf = 0.0
    
    print("==================================================")
    print("      CONVERSATIONAL PIPELINE END-TO-END TEST")
    print("==================================================")

    for i, query in enumerate(turns, 1):
        print(f"\n======================================")
        print(f"TURN {i}: {query}")
        print(f"======================================")
        
        # 1. Load history
        history = memory.get_history_for_agent7(session_id)
        
        # 2. Agent 1
        classification = classifier.classify(query)
        filter_config = pre_filter.build_filter(classification)
        initial_results = retriever.retrieve(query, classification, filter_config, top_k=5)
        
        # 3. Agent 2
        agent2_result = evaluator.evaluate(query, classification, initial_results)
        
        # 4. Repair Cycle
        cycle_result = None
        cycle_ran = "No"
        exit_reason = ""
        final_chunks = initial_results
        
        if not agent2_result.all_passed:
            cycle_result = cycle.run(query, classification, initial_results)
            cycle_ran = "Yes"
            exit_reason = f"({cycle_result.exit_reason})"
            final_chunks = cycle_result.final_chunks
            # update agent2_result to final if available
            if cycle_result.agent2_result:
                agent2_result = cycle_result.agent2_result
                
        # 5. Agent 7
        response = generator.generate(
            query=query,
            classification=classification,
            agent2_result=agent2_result,
            cycle_result=cycle_result,
            conversation_history=history
        )
        
        # 6. Save memory
        memory.add_turn(session_id, "user", query, classification.query_type, None)
        memory.add_turn(session_id, "assistant", response.answer, None, response.confidence)
        
        total_conf += response.confidence
        
        print(f"Query type:    {classification.query_type}")
        print(f"Chunks found:  {len(final_chunks)}")
        
        a2_status = "PASSED" if agent2_result.all_passed else "FAILED"
        fc = agent2_result.failed_check if not agent2_result.all_passed else ""
        a2_print = f"{a2_status} ({fc})" if fc else a2_status
        print(f"Agent 2:       {a2_print}")
        
        print(f"Cycle ran:     {cycle_ran} {exit_reason}")
        print("\nRESPONSE:")
        print(response.answer)
        print(f"\nCitations: {[c['citation'] for c in response.citations]}")
        print(f"Confidence: {response.confidence:.2f}")
        print(f"======================================")
        
        # Sleep to be gentler on the free API tier limits
        time.sleep(2)

    print(f"\nTotal turns completed: {len(turns)}")
    print(f"Average confidence: {total_conf/len(turns):.2f}")
    
    final_history = memory.get_history_for_agent7(session_id)
    memory_working = "Yes" if len(final_history) == 6 else "No"
    print(f"Conversation memory working: {memory_working}")
    
    memory.clear_session(session_id)
    print("\nPHASE 9 COMPLETE - Conversational RAG Pipeline Ready")

if __name__ == "__main__":
    run_test()

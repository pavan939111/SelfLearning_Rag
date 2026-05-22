import sys
from agents.agent4a_formulator import Agent4AFormulator
from agents.agent3_classifier import DiagnosisResult

def main():
    print("==================================================")
    print(" Testing Agent 4A Live PubMed Fetch (knowledge_drift)")
    print("==================================================")
    
    formulator = Agent4AFormulator()
    
    # Create a mock diagnosis showing knowledge_drift
    diagnosis = DiagnosisResult(
        failure_class="B",
        root_cause="knowledge_drift",
        confidence=0.9,
        evidence="Query relates to 2024 trial data not in the 2022 corpus.",
        route_to="4A"
    )
    
    # Query related to Pembrolizumab (should resolve immunotherapy topic cluster)
    query = "pembrolizumab clinical trial results 2024 lung cancer"
    
    class MockClassification:
        classification = "simple_factual"
        
    classification = MockClassification()
    
    print(f"Triggering formulation for query: '{query}'...")
    result = formulator.formulate(query, classification, [], None, diagnosis)
    
    print("\nFormulation Result:")
    print(f"  Used Live Fetch: {result.used_live_fetch}")
    print(f"  Gaps Identified: {result.gaps_identified}")
    
    if result.used_live_fetch:
        lf = result.live_fetch_result
        print(f"  Live Fetch Success: {lf.success}")
        print(f"  Papers Fetched: {lf.papers_fetched}")
        print(f"  Chunks Returned: {len(lf.chunks_returned)}")
        
        if lf.success and lf.chunks_returned:
            print("\nSample Chunk:")
            c = lf.chunks_returned[0]
            print(f"    Chunk ID: {c['chunk_id']}")
            print(f"    Paper ID: {c['paper_id']}")
            print(f"    Title: {c['title'][:80]}...")
            print(f"    Abstract length: {len(c['text'])} chars")
            print(f"    Topic Cluster: {c['topic_cluster']}")
            print(f"    Freshness Score: {c['freshness_score']}")
            
            # Verify required structure
            required_keys = [
                "chunk_id", "paper_id", "text", "title", "year", "journal",
                "score", "level", "section_type", "topic_cluster", 
                "freshness_score", "contradiction_flag", "evidence_level", "keyword_matches"
            ]
            missing = [k for k in required_keys if k not in c]
            if missing:
                print(f"    ERROR: Missing keys in chunk: {missing}")
            else:
                print("    All required chunk-like keys verified OK.")
                
            print("\nTEST PASSED successfully!")
        else:
            print("\nTEST FAILED - Live fetch was unsuccessful or returned no chunks.")
    else:
        print("\nTEST FAILED - Did not route to live fetch strategy.")

if __name__ == "__main__":
    main()

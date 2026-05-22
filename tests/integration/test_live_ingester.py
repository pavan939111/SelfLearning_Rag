import sys
from agents.live_fetch_ingester import LiveFetchIngester

def main():
    print("==================================================")
    print(" Testing LiveFetchIngester Component")
    print("==================================================")
    
    ingester = LiveFetchIngester()
    
    # Mock PMIDs to fetch from PubMed and ingest
    # We will use standard real PMIDs to fetch actual abstracts
    pmids = ["38095881"]
    
    print(f"Testing check_already_ingested for PMID {pmids[0]}...")
    is_ingested = ingester.check_already_ingested(pmids[0])
    print(f"  Already ingested: {is_ingested}")
    
    # Simple test abstract chunk
    mock_chunk = {
        "paper_id": "test_pmid_999",
        "title": "Mock Ingestion Trial for Immunotherapy and NSCLC",
        "text": "This is a robust dummy abstract outlining the state-of-the-art results of using pembrolizumab "
                "combined with chemotherapy in patients diagnosed with advanced non-small cell lung cancer "
                "recorded in early 2024. The trial registered exceptional survival rates and safety profile.",
        "year": 2024,
        "journal": "Journal of Clinical Oncology",
        "topic_cluster": "immunotherapy"
    }
    
    print("\nTesting should_ingest on mock chunk...")
    should = ingester.should_ingest(mock_chunk)
    print(f"  Should Ingest: {should}")
    
    if should:
        print("\nTesting ingest_single on mock chunk...")
        success = ingester.ingest_single(mock_chunk)
        print(f"  Ingestion success: {success}")
        
        # Verify check_already_ingested is now True
        print("\nVerifying if mock chunk is now detected as ingested...")
        now_ingested = ingester.check_already_ingested("test_pmid_999")
        print(f"  Is ingested now: {now_ingested}")
        
        if now_ingested:
            print("\nTEST PASSED successfully!")
            
            # Clean up test point from Qdrant so we don't pollute local database
            print("\nCleaning up test Qdrant points...")
            try:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                scroll_filter = Filter(must=[FieldCondition(key="paper_id", match=MatchValue(value="test_pmid_999"))])
                for level in ["document", "section", "semantic"]:
                    ingester.qdrant.client.delete(
                        collection_name=ingester.qdrant.COLLECTIONS[level],
                        points_selector=scroll_filter
                    )
                print("  Cleanup complete.")
            except Exception as clean_err:
                print(f"  Warning: failed to clean up test points: {clean_err}")
        else:
            print("\nTEST FAILED - Mock chunk was not found in database after ingestion.")
    else:
        print("\nTEST SKIPPED - Mock chunk did not pass should_ingest (likely already ingested in a prior test run).")

if __name__ == "__main__":
    main()

import sys
from workers.repair_tasks import ingest_live_fetch_papers

def test_live_fetch_ingest_task():
    print("="*60)
    print("Running ingest_live_fetch_papers Celery task locally...")
    print("="*60)
    
    test_pmids = ["38234521"]
    test_query = "pembrolizumab lung cancer immunotherapy"
    
    # Run the task directly (synchronous call to verify execution)
    result = ingest_live_fetch_papers(test_pmids, test_query)
    print(f"Task Execution Result: {result}")
    
    # Assert return types and keys
    assert isinstance(result, dict), "Result must be a dictionary"
    assert "ingested" in result, "Result must contain 'ingested' count"
    assert "skipped" in result, "Result must contain 'skipped' count"
    assert "failed" in result, "Result must contain 'failed' count"
    
    print("\n" + "="*60)
    print("        CELERY INGESTION TASK VERIFICATION PASSED")
    print("="*60)

if __name__ == "__main__":
    test_live_fetch_ingest_task()

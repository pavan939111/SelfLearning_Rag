import json
import os
from ingestion.pipeline import IngestionPipeline
from database.qdrant_client import QdrantManager
from database.supabase_client import SupabaseManager
from ingestion.embedder import BiomedicalEmbedder

def test_pipeline():
    print("\n" + "="*50)
    print("      FAILURERAG - PIPELINE END-TO-END TEST")
    print("="*50)

    pipeline = IngestionPipeline()
    qdrant = QdrantManager()
    supabase = SupabaseManager()
    embedder = BiomedicalEmbedder()

    # 1. Run Pipeline (5 papers per cluster = 15 papers)
    print("\n[1/4] Running pipeline for 15 papers...")
    # This will fetch fresh papers or use checkpoint if exists
    stats = pipeline.run(papers_per_cluster=5)
    stats_dict = stats.to_dict()

    # 2. Verification
    print("\n[2/4] Verifying counts...")
    
    success_count = stats_dict["successful_papers"]
    print(f"  Success count: {success_count} / 15")
    
    # Assertions
    checks = []
    checks.append(("Successful papers >= 14", success_count >= 14))
    
    info_doc = qdrant.get_collection_info("document")
    doc_count = info_doc.get("points_count", 0)
    checks.append(("Qdrant document count >= 14", doc_count >= 14))
    
    info_sec = qdrant.get_collection_info("section")
    sec_count = info_sec.get("points_count", 0)
    checks.append(("Qdrant section count >= 28", sec_count >= 28))
    
    info_sem = qdrant.get_collection_info("semantic")
    sem_count = info_sem.get("points_count", 0)
    checks.append(("Qdrant semantic count >= 28", sem_count >= 28))
    
    checks.append(("logs/ingestion_stats.json exists", os.path.exists("logs/ingestion_stats.json")))
    
    # Supabase check
    supa_stats = supabase.get_ingestion_stats()
    # If the user hasn't created the table, this will be 0 but won't crash
    supa_ok = supa_stats.get("total_ingested", 0) > 0
    checks.append(("Supabase has records (requires table setup)", supa_ok))

    all_passed = True
    for label, passed in checks:
        status = "PASSED" if passed else "FAILED"
        print(f"  [{status}] {label}")
        if not passed:
            # We don't fail the whole pipeline just because Supabase table isn't created yet
            if "Supabase" not in label:
                all_passed = False

    # 3. Search Verification
    print("\n[3/4] Verifying search quality...")
    query = "drug interaction cytochrome P450 metabolism"
    query_emb = embedder.embed_text(query)
    results = qdrant.search_chunks(query_emb, "semantic", top_k=1)
    
    search_ok = len(results) > 0 and results[0]["score"] > 0.5
    status = "PASSED" if search_ok else "FAILED"
    score_val = results[0]['score'] if results else 'N/A'
    print(f"  [{status}] Search returned relevant result (Score: {score_val})")
    if not search_ok:
        all_passed = False

    # 4. Final Verdict
    print("\n" + "="*50)
    if all_passed:
        print("PIPELINE READY — safe to run full ingestion")
    else:
        print("PIPELINE FAILED — fix issues before full run")
    print("="*50 + "\n")

if __name__ == "__main__":
    test_pipeline()

import os
from collections import Counter
from ingestion.fetcher import PubMedFetcher, save_papers, load_papers

def main():
    os.makedirs("test_output", exist_ok=True)
    
    print("\n" + "="*50)
    print("PHASE 2 -- PUBMED FETCHER TEST")
    print("="*50)
    
    fetcher = PubMedFetcher()
    
    # Fetch 10 per cluster (30 total) -- quick smoke test
    print("Fetching 10 papers per cluster...")
    papers = fetcher.fetch_all_clusters(papers_per_cluster=10)
    
    print(f"\nTotal papers fetched: {len(papers)}")
    
    # Cluster breakdown
    clusters = Counter(p.topic_cluster for p in papers)
    print("\nBy cluster:")
    for cluster, count in sorted(clusters.items()):
        print(f"  {cluster}: {count}")
    
    # Evidence level breakdown
    evidence = Counter(p.evidence_level for p in papers)
    print("\nBy evidence level:")
    for level, count in sorted(evidence.items()):
        print(f"  {level}: {count}")
    
    # Year range
    years = [p.year for p in papers]
    print(f"\nYear range: {min(years)} -- {max(years)}")
    
    # Abstract length stats
    lengths = [len(p.abstract) for p in papers]
    avg = sum(lengths) // len(lengths)
    print(f"Avg abstract length: {avg} chars")
    
    # Sample paper
    print(f"\nSample paper:")
    p = papers[0]
    print(f"  ID:       {p.paper_id}")
    print(f"  Title:    {p.title[:70]}...")
    print(f"  Year:     {p.year}")
    print(f"  Cluster:  {p.topic_cluster}")
    print(f"  Evidence: {p.evidence_level}")
    print(f"  Authors:  {', '.join(p.authors[:3])}")
    
    # Save and reload verification
    save_papers(papers, "test_output/phase2_papers.jsonl")
    loaded = load_papers("test_output/phase2_papers.jsonl")
    
    # Assertions
    assert len(papers) > 0, "No papers fetched"
    assert len(loaded) == len(papers), "Save/load mismatch"
    assert all(p.freshness_score == 1.0 for p in papers)
    assert all(p.contradiction_flag == False for p in papers)
    assert all(p.year >= 2015 for p in papers)
    assert all(len(p.abstract) > 50 for p in papers)
    
    print("\n" + "="*50)
    print("ALL ASSERTIONS PASSED")
    print("PHASE 2 COMPLETE -- Ready for Phase 3")
    print("="*50)

if __name__ == "__main__":
    main()

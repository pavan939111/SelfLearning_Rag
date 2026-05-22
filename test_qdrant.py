from database.qdrant_client import QdrantManager
from ingestion.embedder import BiomedicalEmbedder
from ingestion.fetcher import load_papers
from ingestion.chunker import HierarchicalChunker

def main():
    print("\n" + "="*52)
    print("PHASE 4 -- QDRANT VECTOR INDEXING TEST")
    print("="*52)

    qdrant = QdrantManager()
    embedder = BiomedicalEmbedder()
    chunker = HierarchicalChunker()

    papers = load_papers("test_output/phase2_papers.jsonl")

    # Process 3 papers
    test_papers = papers[:3]
    level_counts = {
        "document": 0,
        "section": 0,
        "semantic": 0,
        "proposition": 0
    }

    print(f"\nIngesting {len(test_papers)} papers into Qdrant...")

    for paper in test_papers:
        result = chunker.chunk_paper(paper)

        for level in ["document", "section", "semantic", "proposition"]:
            if level == "document":
                chunks = result["document"]
            elif level == "section":
                chunks = result["sections"]
            elif level == "semantic":
                chunks = result["semantic"]
            else:
                chunks = result["propositions"]

            chunk_embeddings = embedder.embed_chunks(chunks)
            inserted = qdrant.insert_chunks(chunk_embeddings, level)
            level_counts[level] += inserted

    print("\nInserted counts:")
    for level, count in level_counts.items():
        print(f"  {level:15s}: {count} points")

    # Verify collections in Qdrant
    print("\nQdrant collection state:")
    for level in ["document", "section", "semantic", "proposition"]:
        info = qdrant.get_collection_info(level)
        print(f"  {level:15s}: {info.get('points_count', 0)} points")

    # Search verification
    print("\nSearch verification:")
    query = "PD-1 inhibitor pembrolizumab lung cancer survival"
    query_emb = embedder.embed_text(query)

    for level in ["document", "section", "semantic"]:
        results = qdrant.search_chunks(
            query_emb, level, top_k=2,
            filters={"topic_cluster": "immunotherapy"}
        )
        print(f"\n  {level} search ({len(results)} results):")
        for r in results:
            print(f"    Score: {r['score']:.4f}")
            print(f"    Text:  {r['text'][:65]}...")
            assert r["score"] > 0.0
            assert r["contradiction_flag"] == False
            assert r["freshness_score"] == 1.0

    print("\n" + "="*52)
    print("ALL ASSERTIONS PASSED")
    print("PHASE 4 COMPLETE -- Ready for Phase 5")
    print("="*52)

if __name__ == "__main__":
    main()

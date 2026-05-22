import os
import json
from collections import defaultdict
from ingestion.fetcher import load_papers
from ingestion.chunker import HierarchicalChunker, ChunkLevel

def main():
    os.makedirs("test_output", exist_ok=True)

    papers = load_papers("test_output/phase2_papers.jsonl")
    chunker = HierarchicalChunker()

    print("\n" + "="*52)
    print("PHASE 3 -- HIERARCHICAL CHUNKER TEST")
    print("="*52)

    # Test on 3 papers only
    # Proposition extraction uses Gemini so keep small
    test_papers = papers[:3]

    all_chunks: dict[str, list] = defaultdict(list)
    total_chars = 0

    for paper in test_papers:
        print(f"\nChunking: {paper.paper_id}")
        print(f"  Title: {paper.title[:55]}...")

        result = chunker.chunk_paper(paper)

        for level, chunks in result.items():
            all_chunks[level].extend(chunks)
            print(f"  {level}: {len(chunks)} chunks")

        paper_total = sum(
            len(c) for c in result.values()
        )
        total_chars += sum(
            ch.char_count
            for chunks in result.values()
            for ch in chunks
        )

    print("\n" + "-"*52)
    print("TOTALS across 3 papers:")
    grand_total = 0
    for level in ["document", "sections", "semantic", "propositions"]:
        n = len(all_chunks[level])
        grand_total += n
        print(f"  {level:15s}: {n} chunks")
    print(f"  {'TOTAL':15s}: {grand_total} chunks")
    print(f"  Total chars indexed: {total_chars}")

    print("\n" + "-"*52)
    print("HIERARCHY VERIFICATION:")

    # Document level
    doc = all_chunks["document"][0]
    assert doc.level == ChunkLevel.DOCUMENT
    assert doc.parent_chunk_id == ""
    assert len(doc.text) > 50
    print("  L1 Document    OK")

    # Section level
    sec = all_chunks["sections"][0]
    assert sec.level == ChunkLevel.SECTION
    assert sec.parent_chunk_id == all_chunks["document"][0].chunk_id
    print("  L2 Section     OK")

    # Semantic level
    sem = all_chunks["semantic"][0]
    assert sem.level == ChunkLevel.SEMANTIC
    assert sem.parent_chunk_id.startswith(
        all_chunks["sections"][0].paper_id
    )
    print("  L3A Semantic   OK")

    # Proposition level
    prop = all_chunks["propositions"][0]
    assert prop.level == ChunkLevel.PROPOSITION
    assert len(prop.text) >= 20
    print("  L3B Proposition OK")

    # Metadata consistency
    for level, chunks in all_chunks.items():
        for ch in chunks:
            assert ch.freshness_score == 1.0
            assert ch.contradiction_flag == False
            assert ch.year >= 2015
            assert ch.topic_cluster in [
                "immunotherapy",
                "drug_interactions",
                "genomics"
            ]
    print("  Metadata       OK")

    # Save sample to file
    sample = []
    for level in ["document", "sections", "semantic", "propositions"]:
        if all_chunks[level]:
            sample.append(all_chunks[level][0].to_dict())

    with open("test_output/phase3_sample_chunks.json", "w") as f:
        json.dump(sample, f, indent=2)
    print("\nSample saved: test_output/phase3_sample_chunks.json")

    print("\n" + "="*52)
    print("ALL ASSERTIONS PASSED")
    print("PHASE 3 COMPLETE -- Ready for Phase 4")
    print("="*52)

if __name__ == "__main__":
    main()

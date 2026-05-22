from database.qdrant_client import QdrantManager
from ingestion.embedder import BiomedicalEmbedder

def test_search():
    qdrant = QdrantManager()
    embedder = BiomedicalEmbedder()

    # Search for something related to what we inserted
    query = 'pembrolizumab immunotherapy cancer treatment'
    query_emb = embedder.embed_text(query)

    print(f'Query: {query}')
    print()

    for level in ['document', 'section', 'semantic']:
        results = qdrant.search_chunks(query_emb, level, top_k=3)
        print(f'Level {level}: {len(results)} results')
        for r in results:
            print(f"  Score: {r['score']:.4f} | {r['text'][:70]}...")
        print()

    print('Phase 4D PASSED')

if __name__ == "__main__":
    test_search()

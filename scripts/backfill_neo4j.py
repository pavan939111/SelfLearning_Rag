import sys
import os
sys.path.append("c:/Users/mahip/OneDrive/Desktop/SelfLearning_Rag")

from ingestion.fetcher import load_papers
from database.neo4j_client import Neo4jManager

def backfill():
    print("="*60)
    print("           NEO4J CORPUS BACKFILL SCRIPT")
    print("="*60)
    
    # 1. Load papers
    filepath = "logs/fetched_papers.jsonl"
    if not os.path.exists(filepath):
        print(f"Error: corpus file {filepath} not found!")
        return
        
    print(f"Loading papers from {filepath}...")
    papers = load_papers(filepath)
    print(f"Loaded {len(papers)} papers total.")
    
    # 2. Connect to Neo4j
    print("Connecting to Neo4j database...")
    neo4j = Neo4jManager()
    if not neo4j.driver:
        print("Error: Could not establish Neo4j driver connection!")
        return
        
    # Check current count before backfill
    initial_count = neo4j.get_paper_count()
    print(f"Initial paper nodes in Neo4j: {initial_count}")
    
    # 3. Create papers batch
    print(f"Backfilling {len(papers)} papers to Neo4j...")
    batch_size = 50
    inserted_count = 0
    
    for i in range(0, len(papers), batch_size):
        batch = papers[i:i + batch_size]
        count = neo4j.create_papers_batch(batch)
        inserted_count += count
        
        # Print progress every 100 papers
        if (i + len(batch)) % 100 == 0 or (i + len(batch)) == len(papers):
            print(f"  Processed {i + len(batch)} / {len(papers)} papers (successfully merged {inserted_count} nodes)...")
            
    # 4. Create topic clusters and relationships
    print("Creating TopicCluster nodes and connecting Paper nodes...")
    clusters_success = neo4j.create_topic_cluster_nodes()
    if clusters_success:
        print("Successfully created topic clusters and BELONGS_TO relationships!")
    else:
        print("Warning: Topic cluster node/relationship creation failed.")
        
    # Check final count after backfill
    final_count = neo4j.get_paper_count()
    print(f"Final paper nodes in Neo4j: {final_count}")
    print(f"Total newly merged paper nodes: {final_count - initial_count}")
    
    neo4j.close()
    print("="*60)
    print("         NEO4J BACKFILL COMPLETE SUCCESSFULLY!")
    print("="*60)

if __name__ == "__main__":
    backfill()

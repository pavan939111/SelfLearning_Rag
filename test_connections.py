import sys
from database.qdrant_client import QdrantManager
from database.supabase_client import SupabaseManager
from database.neo4j_client import Neo4jManager
from database.redis_client import RedisManager
from config import get_config

def run_tests():
    print("\n  ==================================")
    print("  FAILURERAG -- CONNECTION TEST")
    print("  ==================================")
    
    results = {}
    
    # Initialize Managers
    qdrant = QdrantManager()
    supabase = SupabaseManager()
    neo4j = Neo4jManager()
    redis_mgr = RedisManager()
    
    # Run tests
    results["Qdrant Cloud "] = qdrant.test_connection()
    results["Supabase     "] = supabase.test_connection()
    results["Neo4j AuraDB "] = neo4j.test_connection()
    results["Redis Upstash"] = redis_mgr.test_connection()
    
    # Print Summary
    print("\n  SUMMARY:")
    all_pass = True
    for name, success in results.items():
        status = "OK - CONNECTED" if success else "FAILED"
        print(f"  {name}    {status}")
        if not success:
            all_pass = False
            
    print("  ==================================")
    
    # Cleanup
    neo4j.close()
    
    if all_pass:
        print("  All connections OK -- ready for Phase 2\n")
        sys.exit(0)
    else:
        print("  Some connections failed. Check logs above.\n")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()

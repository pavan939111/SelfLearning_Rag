import sys
import json
from datetime import datetime
from agents.agent6_learning import Agent6Learning, FailurePattern, CoverageGap, CalibrationPoint, Agent6Insight
from agents.cache_manager import CacheManager
from test_agent6 import MockSupabaseDB

def print_header(title):
    print(f"\n{'='*50}")
    print(f" {title}")
    print(f"{'='*50}")

def test_generate_insights_rules():
    print_header("Test W1: generate_insights() Logic & Deduplication")
    agent6 = Agent6Learning()
    
    # 1. Setup Mock DB
    mock_db = MockSupabaseDB()
    agent6.supabase = type('Manager', (object,), {'client': mock_db})()
    
    # Populate failure patterns for Rule 1 (count >= 10)
    mock_db.insert_data("agent6_patterns", {
        "pattern_id": "temporal_freshness_immunotherapy",
        "topic_cluster": "immunotherapy",
        "failure_type": "freshness",
        "occurrence_count": 12,
        "sample_queries": "[]",
        "severity": "medium",
        "recommended_action": "ref"
    })
    
    # Populate coverage gaps for Rule 2 (count >= 5)
    mock_db.insert_data("agent6_gaps", {
        "topic": "genomics",
        "query_count": 6,
        "coverage_level": "none",
        "sample_queries": "[]"
    })
    
    # Populate calibration drift for Rule 3 (abs(diff) > 0.15 and sample_size >= 10)
    mock_db.insert_data("agent6_calibration", {
        "topic_cluster": "drug_interactions",
        "expressed_confidence": 0.90,
        "actual_pass_rate": 0.50,
        "sample_size": 12
    })
    
    # Generate insights!
    insights = agent6.generate_insights()
    print(f"Generated {len(insights)} insights:")
    for ins in insights:
        print(f"  [{ins.insight_type.upper()}] Title: '{ins.title}', Action: '{ins.recommended_action}', Priority: '{ins.priority}'")
        
    assert len(insights) == 3, f"Expected 3 insights, got {len(insights)}"
    
    # Assert specific rule details
    pattern_ins = next(i for i in insights if i.insight_type == "pattern")
    assert pattern_ins.title == "freshness failures in immunotherapy"
    assert pattern_ins.recommended_action == "Schedule corpus refresh for this cluster"
    assert pattern_ins.priority == "medium"  # count is 12 (not >= 20)
    
    gap_ins = next(i for i in insights if i.insight_type == "gap")
    assert gap_ins.title == "Coverage gap: genomics"
    assert gap_ins.recommended_action == "Ingest papers on this topic"
    assert gap_ins.priority == "medium"  # count is 6 (not >= 15)
    
    cal_ins = next(i for i in insights if i.insight_type == "calibration")
    assert cal_ins.title == "Confidence miscalibrated for drug_interactions"
    assert cal_ins.recommended_action == "Recalibrate confidence thresholds"
    assert cal_ins.priority == "medium"
    
    # Test deduplication - calling again should NOT insert duplicates or return them
    print("Running generate_insights() again to test deduplication...")
    insights2 = agent6.generate_insights()
    assert len(insights2) == 0, f"Expected 0 new insights due to deduplication, got {len(insights2)}"
    print("Deduplication verification PASSED")

def test_cache_manager_dynamic_ttl():
    print_header("Test W2: CacheManager Dynamic TTL based on Agent 6 Velocity")
    cache = CacheManager()
    
    # Mock Agent6Learning inside cache manager to control topic velocity returns
    from agents import cache_manager
    original_agent6_class = None
    try:
        from agents.agent6_learning import Agent6Learning
        original_agent6_class = Agent6Learning
    except ImportError:
        pass
        
    class MockAgent6:
        def __init__(self):
            pass
        def get_topic_velocity(self, cluster):
            if cluster == "immunotherapy":
                return "high"
            elif cluster == "drug_interactions":
                return "medium"
            elif cluster == "genomics":
                return "low"
            return "low"
            
    # Inject Mock Agent6 into local modules for testing
    import sys
    sys.modules['agents.agent6_learning'].Agent6Learning = MockAgent6
    
    # Query TTLs
    ttl_imm = cache._get_ttl("immunotherapy")
    ttl_drug = cache._get_ttl("drug_interactions")
    ttl_gen = cache._get_ttl("genomics")
    
    print(f"Dynamic TTLs:")
    print(f"  immunotherapy (high):     {ttl_imm}s (Expected: {4*3600}s)")
    print(f"  drug_interactions (med):  {ttl_drug}s (Expected: {24*3600}s)")
    print(f"  genomics (low):           {ttl_gen}s (Expected: {7*24*3600}s)")
    
    assert ttl_imm == 4 * 3600, "High velocity TTL should be 4 hours"
    assert ttl_drug == 24 * 3600, "Medium velocity TTL should be 24 hours"
    assert ttl_gen == 7 * 24 * 3600, "Low velocity TTL should be 7 days"
    
    # Restore original class
    if original_agent6_class:
        sys.modules['agents.agent6_learning'].Agent6Learning = original_agent6_class
        
    print("Test W2 PASSED")

if __name__ == "__main__":
    test_generate_insights_rules()
    test_cache_manager_dynamic_ttl()
    print("\n==================================================")
    print("     ALL AGENT 6 WIRING & INSIGHT TESTS PASSED")
    print("==================================================")

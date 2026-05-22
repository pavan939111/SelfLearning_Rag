import json
from dataclasses import dataclass, field
from datetime import datetime
from database.supabase_client import SupabaseManager
from utils.logger import get_logger
from config import get_config

@dataclass
class FailurePattern:
    pattern_id: str
    topic_cluster: str
    failure_type: str       # retrieval/completeness/freshness
    occurrence_count: int
    first_seen: str         # ISO datetime
    last_seen: str
    sample_queries: list[str] = field(default_factory=list)  # up to 3 examples
    severity: str = "low"   # low/medium/high
    recommended_action: str = ""

@dataclass
class CoverageGap:
    topic: str
    query_count: int        # how many queries asked about this
    coverage_level: str = "none"  # none/partial/good
    first_detected: str = ""
    last_queried: str = ""
    sample_queries: list[str] = field(default_factory=list)

@dataclass
class CalibrationPoint:
    topic_cluster: str
    expressed_confidence: float
    actual_pass_rate: float    # how often Agent 2 actually passed
    sample_size: int = 0
    last_updated: str = ""

@dataclass
class Agent6Insight:
    insight_id: str
    insight_type: str       # pattern/gap/calibration/strategy
    title: str
    description: str
    evidence: str
    recommended_action: str
    priority: str = "medium"  # low/medium/high
    created_at: str = ""
    status: str = "new"       # new/reviewed/implemented/dismissed


class Agent6Learning:
    """
    Agent 6 (Learning Agent): Observes system behaviors and outputs,
    detecting multi-turn failure patterns, maintaining calibration curves,
    mapping content coverage gaps, and surfacing recommendations.
    Never blocks the hot-path, running in fire-and-forget mode.
    """
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger(__name__, level=self.config.log_level)
        try:
            self.supabase = SupabaseManager()
            if not self.supabase.client:
                self.logger.warning("Supabase client is not available in SupabaseManager.")
        except Exception as e:
            self.logger.error(f"Failed to initialize Supabase client in Agent 6: {e}")
            self.supabase = None

    def observe_query_result(self, 
                             session_id: str, 
                             query: str, 
                             classification, 
                             agent2_result, 
                             cycle_result) -> None:
        """
        Observes the outcome of a single complete query loop.
        Updates failure patterns, coverage gaps, and calibration statistics in Supabase.
        Never crashes.
        """
        if not self.supabase or not self.supabase.client:
            self.logger.warning("Supabase unavailable. Observe query skipped.")
            return

        try:
            # 0. Common extraction
            retrieved = getattr(agent2_result, "retrieval_results", []) or []
            clusters = [r.topic_cluster if hasattr(r, "topic_cluster") else r.get("topic_cluster", "unknown") for r in retrieved]
            topic_cluster = max(set(clusters), key=clusters.count) if clusters else "default"
            
            # 1. Update Failure Patterns if Agent 2 failed
            if agent2_result and not agent2_result.all_passed:
                failed_check = agent2_result.failed_check or "unknown"
                query_type = classification.query_type if classification else "unknown"
                pattern_id = f"{query_type}_{failed_check}_{topic_cluster}"
                
                try:
                    # Check if pattern already exists
                    pattern_res = self.supabase.client.table("agent6_patterns").select("*").eq("pattern_id", pattern_id).execute()
                    
                    if pattern_res.data:
                        existing = pattern_res.data[0]
                        new_count = existing.get("occurrence_count", 0) + 1
                        
                        # Parse sample queries
                        sample_str = existing.get("sample_queries", "[]")
                        try:
                            samples = json.loads(sample_str) if sample_str else []
                        except Exception:
                            samples = []
                        if query not in samples:
                            samples.append(query)
                        samples = samples[-3:]  # limit to 3
                        
                        # Determine severity
                        severity = "low"
                        if new_count >= 20:
                            severity = "high"
                        elif new_count >= 5:
                            severity = "medium"
                            
                        # Update
                        self.supabase.client.table("agent6_patterns").update({
                            "occurrence_count": new_count,
                            "last_seen": datetime.now().isoformat(),
                            "sample_queries": json.dumps(samples),
                            "severity": severity
                        }).eq("pattern_id", pattern_id).execute()
                        
                    else:
                        # Insert new
                        recommended = f"Ingest more papers for cluster '{topic_cluster}' or recalibrate the query formulation strategy."
                        self.supabase.client.table("agent6_patterns").insert({
                            "pattern_id": pattern_id,
                            "topic_cluster": topic_cluster,
                            "failure_type": failed_check,
                            "occurrence_count": 1,
                            "first_seen": datetime.now().isoformat(),
                            "last_seen": datetime.now().isoformat(),
                            "sample_queries": json.dumps([query]),
                            "severity": "low",
                            "recommended_action": recommended
                        }).execute()
                except Exception as pattern_err:
                    self.logger.error(f"Error updating failure pattern in Agent 6: {pattern_err}")

            # 2. Update Coverage Gaps if Class A/B failure triggered repair cycle exit
            if cycle_result and cycle_result.exit_reason == "class_ab_exit":
                try:
                    # Extract topic from classification
                    topic = ""
                    if classification:
                        topics = getattr(classification, "main_topics", [])
                        if isinstance(topics, list) and topics:
                            topic = topics[0]
                        elif isinstance(topics, str):
                            topic = topics
                            
                    if topic:
                        gap_res = self.supabase.client.table("agent6_gaps").select("*").eq("topic", topic).execute()
                        
                        if gap_res.data:
                            existing = gap_res.data[0]
                            new_count = existing.get("query_count", 0) + 1
                            
                            # Parse sample queries
                            sample_str = existing.get("sample_queries", "[]")
                            try:
                                samples = json.loads(sample_str) if sample_str else []
                            except Exception:
                                samples = []
                            if query not in samples:
                                samples.append(query)
                            samples = samples[-3:]
                            
                            self.supabase.client.table("agent6_gaps").update({
                                "query_count": new_count,
                                "last_queried": datetime.now().isoformat(),
                                "sample_queries": json.dumps(samples)
                            }).eq("topic", topic).execute()
                        else:
                            self.supabase.client.table("agent6_gaps").insert({
                                "topic": topic,
                                "query_count": 1,
                                "coverage_level": "none",
                                "first_detected": datetime.now().isoformat(),
                                "last_queried": datetime.now().isoformat(),
                                "sample_queries": json.dumps([query])
                            }).execute()
                except Exception as gap_err:
                    self.logger.error(f"Error updating coverage gap in Agent 6: {gap_err}")

            # 3. Update Calibration stats
            if agent2_result:
                try:
                    expressed = getattr(agent2_result, "calibrated_confidence", 0.85) or 0.85
                    passed = 1.0 if agent2_result.all_passed else 0.0
                    
                    cal_res = self.supabase.client.table("agent6_calibration").select("*").eq("topic_cluster", topic_cluster).execute()
                    
                    if cal_res.data:
                        existing = cal_res.data[0]
                        old_pass_rate = existing.get("actual_pass_rate", 0.0)
                        old_confidence = existing.get("expressed_confidence", 0.0)
                        old_size = existing.get("sample_size", 0)
                        
                        new_size = old_size + 1
                        new_pass_rate = (old_pass_rate * old_size + passed) / new_size
                        new_confidence = (old_confidence * old_size + expressed) / new_size
                        
                        self.supabase.client.table("agent6_calibration").update({
                            "actual_pass_rate": new_pass_rate,
                            "expressed_confidence": new_confidence,
                            "sample_size": new_size,
                            "last_updated": datetime.now().isoformat()
                        }).eq("topic_cluster", topic_cluster).execute()
                    else:
                        self.supabase.client.table("agent6_calibration").insert({
                            "topic_cluster": topic_cluster,
                            "expressed_confidence": expressed,
                            "actual_pass_rate": passed,
                            "sample_size": 1,
                            "last_updated": datetime.now().isoformat()
                        }).execute()
                except Exception as cal_err:
                    self.logger.error(f"Error updating calibration in Agent 6: {cal_err}")

        except Exception as general_err:
            self.logger.error(f"General error in observe_query_result: {general_err}")

    def get_coverage_gaps(self, min_query_count: int = 3) -> list[CoverageGap]:
        """
        Returns all coverage gaps with query count >= min_query_count, sorted by query_count descending.
        Never crashes.
        """
        gaps_list = []
        if not self.supabase or not self.supabase.client:
            return gaps_list

        try:
            res = self.supabase.client.table("agent6_gaps")\
                .select("*")\
                .gte("query_count", min_query_count)\
                .order("query_count", desc=True)\
                .execute()
            
            for row in res.data:
                try:
                    sample_str = row.get("sample_queries", "[]")
                    samples = json.loads(sample_str) if sample_str else []
                except Exception:
                    samples = []
                gaps_list.append(CoverageGap(
                    topic=row["topic"],
                    query_count=row["query_count"],
                    coverage_level=row.get("coverage_level", "none"),
                    first_detected=row.get("first_detected", ""),
                    last_queried=row.get("last_queried", ""),
                    sample_queries=samples
                ))
            return gaps_list
        except Exception as e:
            self.logger.error(f"Failed to fetch coverage gaps: {e}")
            return []

    def get_failure_patterns(self, severity: str = None) -> list[FailurePattern]:
        """
        Returns failure patterns optionally filtered by severity, sorted by occurrence count descending.
        Never crashes.
        """
        patterns_list = []
        if not self.supabase or not self.supabase.client:
            return patterns_list

        try:
            query = self.supabase.client.table("agent6_patterns").select("*")
            if severity:
                query = query.eq("severity", severity)
                
            res = query.order("occurrence_count", desc=True).execute()
            
            for row in res.data:
                try:
                    sample_str = row.get("sample_queries", "[]")
                    samples = json.loads(sample_str) if sample_str else []
                except Exception:
                    samples = []
                patterns_list.append(FailurePattern(
                    pattern_id=row["pattern_id"],
                    topic_cluster=row.get("topic_cluster", ""),
                    failure_type=row.get("failure_type", ""),
                    occurrence_count=row["occurrence_count"],
                    first_seen=row.get("first_seen", ""),
                    last_seen=row.get("last_seen", ""),
                    sample_queries=samples,
                    severity=row.get("severity", "low"),
                    recommended_action=row.get("recommended_action", "")
                ))
            return patterns_list
        except Exception as e:
            self.logger.error(f"Failed to fetch failure patterns: {e}")
            return []

    def get_calibration(self, topic_cluster: str) -> CalibrationPoint | None:
        """
        Returns CalibrationPoint statistics for a specific topic cluster.
        Never crashes.
        """
        if not self.supabase or not self.supabase.client:
            return None

        try:
            res = self.supabase.client.table("agent6_calibration")\
                .select("*")\
                .eq("topic_cluster", topic_cluster)\
                .execute()
            
            if res.data:
                row = res.data[0]
                return CalibrationPoint(
                    topic_cluster=row["topic_cluster"],
                    expressed_confidence=row["expressed_confidence"],
                    actual_pass_rate=row["actual_pass_rate"],
                    sample_size=row["sample_size"],
                    last_updated=row.get("last_updated", "")
                )
            return None
        except Exception as e:
            self.logger.error(f"Failed to fetch calibration point for cluster {topic_cluster}: {e}")
            return None

    def get_topic_velocity(self, topic_cluster: str) -> str:
        """
        Returns topic velocity class 'high' / 'medium' / 'low' based on historical data.
        high: failure patterns count > 10 OR gap query_count > 20
        medium: failure patterns count > 3 OR gap query_count > 5
        low: everything else
        """
        if not self.supabase or not self.supabase.client:
            return "low"

        try:
            # failure patterns count for this cluster (sum of occurrence_count)
            patterns_res = self.supabase.client.table("agent6_patterns")\
                .select("occurrence_count")\
                .eq("topic_cluster", topic_cluster)\
                .execute()
            patterns_count = sum(r.get("occurrence_count", 0) for r in patterns_res.data) if patterns_res.data else 0

            # gap query_count
            gaps_res = self.supabase.client.table("agent6_gaps")\
                .select("query_count")\
                .eq("topic", topic_cluster)\
                .execute()
            gap_query_count = gaps_res.data[0].get("query_count", 0) if gaps_res.data else 0

            if patterns_count > 10 or gap_query_count > 20:
                return "high"
            elif patterns_count > 3 or gap_query_count > 5:
                return "medium"
            else:
                return "low"
        except Exception as e:
            self.logger.warning(f"Failed to calculate topic velocity for '{topic_cluster}', defaulting to 'low': {e}")
            return "low"

    def generate_insights(self) -> list[Agent6Insight]:
        """
        Scans failure patterns, coverage gaps, and calibration statistics,
        detecting and deduplicating actionable insights, then persisting them to Supabase.
        Never crashes.
        """
        new_insights = []
        if not self.supabase or not self.supabase.client:
            return new_insights

        try:
            # Rule 1 - High frequency failure pattern
            # For each pattern where occurrence_count >= 10:
            patterns_res = self.supabase.client.table("agent6_patterns").select("*").gte("occurrence_count", 10).execute()
            for row in patterns_res.data:
                count = row["occurrence_count"]
                failure_type = row.get("failure_type", "unknown")
                topic_cluster = row.get("topic_cluster", "unknown")
                
                # Recommended action
                rec_action = "Analyze failure patterns"
                if failure_type == "retrieval":
                    rec_action = "Consider query expansion improvement"
                elif failure_type == "completeness":
                    rec_action = "Corpus may have coverage gap"
                elif failure_type == "freshness":
                    rec_action = "Schedule corpus refresh for this cluster"
                    
                priority = "high" if count >= 20 else "medium"
                
                insight_id = f"pattern_{failure_type}_{topic_cluster}"
                title = f"{failure_type} failures in {topic_cluster}"
                description = f"This query type has failed {count} times"
                evidence = f"Pattern ID: {row['pattern_id']}, Count: {count}"
                
                new_insights.append(Agent6Insight(
                    insight_id=insight_id,
                    insight_type="pattern",
                    title=title,
                    description=description,
                    evidence=evidence,
                    recommended_action=rec_action,
                    priority=priority,
                    created_at=datetime.now().isoformat(),
                    status="new"
                ))

            # Rule 2 - Coverage gap
            # For each gap where query_count >= 5:
            gaps_res = self.supabase.client.table("agent6_gaps").select("*").gte("query_count", 5).execute()
            for row in gaps_res.data:
                count = row["query_count"]
                topic = row["topic"]
                
                priority = "high" if count >= 15 else "medium"
                insight_id = f"gap_{topic}"
                title = f"Coverage gap: {topic}"
                description = f"Users asked about this {count} times but corpus lacks coverage"
                evidence = f"Gap Topic: {topic}, Queries Count: {count}"
                
                new_insights.append(Agent6Insight(
                    insight_id=insight_id,
                    insight_type="gap",
                    title=title,
                    description=description,
                    evidence=evidence,
                    recommended_action="Ingest papers on this topic",
                    priority=priority,
                    created_at=datetime.now().isoformat(),
                    status="new"
                ))

            # Rule 3 - Calibration drift
            # For each calibration where abs(expressed_confidence - actual_pass_rate) > 0.15 AND sample_size >= 10:
            cal_res = self.supabase.client.table("agent6_calibration").select("*").gte("sample_size", 10).execute()
            for row in cal_res.data:
                size = row["sample_size"]
                expressed = row["expressed_confidence"]
                actual = row["actual_pass_rate"]
                topic_cluster = row["topic_cluster"]
                
                if abs(expressed - actual) > 0.15:
                    insight_id = f"calibration_{topic_cluster}"
                    title = f"Confidence miscalibrated for {topic_cluster}"
                    description = f"Expressed {expressed:.2f} but actual {actual:.2f}"
                    evidence = f"Topic Cluster: {topic_cluster}, Sample Size: {size}"
                    
                    new_insights.append(Agent6Insight(
                        insight_id=insight_id,
                        insight_type="calibration",
                        title=title,
                        description=description,
                        evidence=evidence,
                        recommended_action="Recalibrate confidence thresholds",
                        priority="medium",
                        created_at=datetime.now().isoformat(),
                        status="new"
                    ))

            # Deduplicate against agent6_insights database table and insert
            inserted_insights = []
            for ins in new_insights:
                try:
                    # Check if similar exists (matching insight_id)
                    exists_res = self.supabase.client.table("agent6_insights").select("*").eq("insight_id", ins.insight_id).execute()
                    if not exists_res.data:
                        # Insert
                        self.supabase.client.table("agent6_insights").insert({
                            "insight_id": ins.insight_id,
                            "insight_type": ins.insight_type,
                            "title": ins.title,
                            "description": ins.description,
                            "evidence": ins.evidence,
                            "recommended_action": ins.recommended_action,
                            "priority": ins.priority,
                            "created_at": ins.created_at,
                            "status": ins.status
                        }).execute()
                        inserted_insights.append(ins)
                        self.logger.info(f"Generated new dashboard insight: {ins.title}")
                except Exception as ins_err:
                    self.logger.error(f"Failed to check or insert insight {ins.insight_id}: {ins_err}")
            
            return inserted_insights

        except Exception as e:
            self.logger.error(f"Failed to generate strategic insights: {e}")
            return []

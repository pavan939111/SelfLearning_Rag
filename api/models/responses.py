from pydantic import BaseModel
from typing import List, Dict, Any

class ChatResponse(BaseModel):
    session_id: str
    query: str
    answer: str
    citations: List[Dict[str, Any]]
    confidence: float
    confidence_lower: float = 0.0
    confidence_upper: float = 1.0
    has_gaps: bool
    gap_acknowledgment: str
    has_contradiction: bool
    contradiction_note: str
    query_type: str
    chunks_used: int
    cycle_ran: bool
    cycle_exit_reason: str
    processing_time_ms: int
    cache_hit: bool = False
    session_bias_applied: bool = False
    session_topic: str = ""
    follow_up_resolved: bool = False
    resolved_query: str = ""
    graph_expansion_used: bool = False
    graph_papers_added: int = 0
    output_format: str = "prose"
    claim_provenance: List[Dict[str, Any]] = []
    query_suggestions: List[str] = []
    domain_rejected: bool = False
    proactive_contradiction_detected: bool = False
    contradicting_papers_count: int = 0

class HealthResponse(BaseModel):
    status: str
    databases: Dict[str, Any]
    agents: Dict[str, Any]
    system: Dict[str, Any]

class ErrorResponse(BaseModel):
    error: str
    detail: str

from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, Optional
from datetime import datetime
import uuid

# ── THOUGHT TRACES ─────────────────────────────────

class ThoughtTrace(BaseModel):
    trace_id: str = Field(
        default_factory=lambda: str(uuid.uuid4())[:8]
    )
    session_id: str = ''
    agent: str                    # agent1, agent2, etc.
    step: str                     # classify, retrieve, evaluate etc.
    obs: str                      # what the agent observed
    thk: str                      # what it reasoned
    act: str                      # what action it decided
    out: str                      # what the outcome was
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    duration_ms: int = 0
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )
    metadata: dict = {}

# ── AGENT 1 — RETRIEVAL ──────────────────────────

class QueryClassification(BaseModel):
    query: str
    query_type: Literal[
        'simple_factual', 'multi_hop', 
        'comparative', 'temporal', 'exploratory'
    ] = 'simple_factual'
    main_topics: list[str] = []
    requires_recent: bool = False
    entities: list[str] = []
    topic_cluster: str = "default"
    domain_rejected: bool = False
    rejection_reason: str = ''

class FilterConfig(BaseModel):
    must_conditions: list[dict] = []
    should_conditions: list[dict] = []
    min_year: Optional[int] = None
    topic_cluster: Optional[str] = None
    requires_fresh: bool = False

class RetrievalResult(BaseModel):
    chunk_id: str
    paper_id: str
    text: str
    score: float = Field(ge=0.0, le=1.0)
    level: str
    section_type: str = ""
    topic_cluster: str = ""
    year: int = 2020
    freshness_score: float = Field(default=1.0, ge=0.0, le=1.0)
    contradiction_flag: bool = False
    keyword_matches: int = 0
    from_graph: bool = False
    live_fetch: bool = False
    journal: str = ""
    authors: list[str] = []

class SufficiencyResult(BaseModel):
    is_sufficient: bool
    reason: str = ""
    suggestion: str = ""

# ── AGENT 2 — QUALITY GATE ───────────────────────

class EvaluationResult(BaseModel):
    check_name: str
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    reason: str = ""
    suggestion: str = ""
    confidence_lower: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_upper: float = Field(default=1.0, ge=0.0, le=1.0)

class Agent2Result(BaseModel):
    all_passed: bool
    failed_check: str = ""
    checks: list[EvaluationResult] = []
    calibrated_confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    confidence_lower: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_upper: float = Field(default=1.0, ge=0.0, le=1.0)
    contradiction_found: bool = False
    contradicting_chunks: list[str] = []
    live_fetch_needed: bool = False
    coverage_gaps: list[str] = []
    retrieval_results: list[RetrievalResult] = []
    thought_traces: list[ThoughtTrace] = []

# ── AGENT 3 — ROOT CAUSE ─────────────────────────

class DiagnosisResult(BaseModel):
    failure_class: Literal['A', 'B', 'C']
    root_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = ""
    route_to: Literal['4A', '4B', 'escalate']
    thought_traces: list[ThoughtTrace] = []

# ── AGENT 4A — FORMULATOR ────────────────────────

class SubQuery(BaseModel):
    query_text: str
    strategy: str
    filter_config: FilterConfig
    target_gap: str = ""

class LiveFetchResult(BaseModel):
    source: str = "pubmed_live"
    papers_fetched: int = 0
    chunks_returned: list[dict] = []
    query_used: str = ""
    success: bool = False

class FormulationResult(BaseModel):
    original_query: str
    sub_queries: list[SubQuery] = []
    gaps_identified: list[str] = []
    strategy_explanation: str = ""
    live_fetch_result: Optional[LiveFetchResult] = None
    used_live_fetch: bool = False

# ── REPAIR CYCLE ─────────────────────────────────

class CycleResult(BaseModel):
    final_chunks: list[RetrievalResult] = []
    agent2_result: Optional[Agent2Result] = None
    iterations_run: int = 0
    exit_reason: Literal[
        'agent2_passed', 'max_cycles', 
        'class_ab_exit', 'not_run'
    ] = 'not_run'
    diagnosis_history: list[DiagnosisResult] = []
    all_chunks_seen: list[RetrievalResult] = []
    agent4b_action: str = ""
    thought_traces: list[ThoughtTrace] = []

# ── AGENT 5A — VERIFICATION ──────────────────────

class VerificationResult(BaseModel):
    paper_id: str
    passed: bool
    failed_check: str = ""
    reason: str = ""
    priority: Literal['high', 'medium', 'low'] = 'low'
    ingestion_instructions: dict = {}

# ── AGENT 6 — LEARNING ───────────────────────────

class FailurePattern(BaseModel):
    pattern_id: str
    topic_cluster: str
    failure_type: str
    occurrence_count: int = 1
    first_seen: str = ""
    last_seen: str = ""
    sample_queries: list[str] = []
    severity: Literal['low', 'medium', 'high'] = 'low'
    recommended_action: str = ""

class CoverageGap(BaseModel):
    topic: str
    query_count: int = 1
    coverage_level: Literal['none', 'partial', 'good'] = 'none'
    first_detected: str = ""
    last_queried: str = ""
    sample_queries: list[str] = []

class CalibrationPoint(BaseModel):
    topic_cluster: str
    expressed_confidence: float = Field(ge=0.0, le=1.0)
    actual_pass_rate: float = Field(ge=0.0, le=1.0)
    sample_size: int = 0
    last_updated: str = ""

class Agent6Insight(BaseModel):
    insight_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    insight_type: Literal[
        'pattern', 'gap', 'calibration', 
        'strategy', 'feedback'
    ]
    title: str
    description: str
    evidence: str = ""
    recommended_action: str = ""
    priority: Literal['low', 'medium', 'high'] = 'medium'
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )
    status: Literal['new', 'reviewed', 
                    'implemented', 'dismissed'] = 'new'

class StrategyRecommendation(BaseModel):
    recommendation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4())[:8]
    )
    parameter: str
    current_value: str
    recommended_value: str
    reason: str
    evidence: dict = {}
    priority: Literal['low', 'medium', 'high'] = 'medium'
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )
    status: Literal[
        'pending', 'approved', 'rejected'
    ] = 'pending'

# ── AGENT 7 — GENERATOR ──────────────────────────

class ClaimProvenance(BaseModel):
    claim: str
    chunk_id: str
    paper_id: str
    paper_year: int = 2020
    journal: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    quote: str = ""

class GeneratedResponse(BaseModel):
    answer: str
    citations: list[dict] = []
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_lower: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_upper: float = Field(default=1.0, ge=0.0, le=1.0)
    has_gaps: bool = False
    gap_acknowledgment: str = ""
    has_contradiction: bool = False
    contradiction_note: str = ""
    query_type: str = ""
    chunks_used: int = 0
    output_format: Literal[
        'prose', 'table', 'list', 'summary'
    ] = 'prose'
    claim_provenance: list[ClaimProvenance] = []
    query_suggestions: list[str] = []
    thought_traces: list[ThoughtTrace] = []

# ── CONVERSATION ─────────────────────────────────

class ConversationTurn(BaseModel):
    role: Literal['user', 'assistant', 'system']
    content: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )
    query_type: str = ""
    confidence: float = 0.0

class ConversationSession(BaseModel):
    session_id: str
    turns: list[ConversationTurn] = []
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )
    last_active: str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )
    summary: str = ""

# ── PIPELINE STATE ───────────────────────────────

class PipelineState(BaseModel):
    query: str
    session_id: str
    classification: Optional[QueryClassification] = None
    retrieval_results: list[RetrievalResult] = []
    agent2_result: Optional[Agent2Result] = None
    cycle_result: Optional[CycleResult] = None
    response: Optional[GeneratedResponse] = None
    cache_hit: bool = False
    live_fetch_used: bool = False
    topic_has_contradictions: bool = False
    proactive_contradiction_note: str = ""
    resolved_query: str = ""
    follow_up_resolved: bool = False
    session_bias_applied: bool = False
    session_topic: str = ""
    thought_traces: list[ThoughtTrace] = []

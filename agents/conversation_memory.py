import json
import datetime
from google import genai
from dataclasses import dataclass, field, asdict
from typing import Optional
from config import get_config
from utils.logger import get_logger
from utils.llm_utils import get_gemini_key

from agents.models import ConversationTurn, ConversationSession

class ConversationMemory:
    """
    Manages multi-turn conversation history in Redis.
    Compresses older turns via LLM summarization to prevent context bloat.
    """
    def __init__(self, session_ttl: int = 7200, max_verbatim_turns: int = 6):
        self.config = get_config()
        self.logger = get_logger(__name__)
        self.session_ttl = session_ttl
        self.max_verbatim_turns = max_verbatim_turns
        
        try:
            from database.redis_client import RedisManager
            self.redis_manager = RedisManager()
            self.redis = self.redis_manager.client
        except Exception as e:
            self.logger.error(f"Failed to initialize Redis client for Conversation Memory: {e}")
            self.redis = None

    def _get_key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def get_or_create_session(self, session_id: str) -> ConversationSession:
        try:
            if self.redis:
                data_str = self.redis.get(self._get_key(session_id))
                if data_str:
                    return ConversationSession.model_validate_json(data_str)
        except Exception as e:
            self.logger.warning(f"Error loading session {session_id} from Redis: {e}")
            
        return ConversationSession(session_id=session_id)

    def summarize_old_turns(self, session: ConversationSession) -> str:
        if len(session.turns) <= self.max_verbatim_turns:
            return session.summary
            
        turns_to_summarize = session.turns[:-self.max_verbatim_turns]
        
        dialogue = ""
        if session.summary:
            dialogue += f"Previous summary: {session.summary}\n\n"
            
        for t in turns_to_summarize:
            dialogue += f"{t.role.capitalize()}: {t.content}\n"
            
        try:
            client = genai.Client(api_key=get_gemini_key())
            prompt = (
                "Summarize this conversation in 2-3 sentences.\n"
                "Focus on topics discussed and key facts established.\n\n"
                f"{dialogue}"
            )
            response = client.models.generate_content(
                model="gemini-flash-latest",
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            self.logger.warning(f"Failed to generate summary via Gemini: {e}")
            return dialogue[:500] + "... [truncated due to LLM failure]"

    def add_turn(self, session_id: str, role: str, content: str, query_type: Optional[str] = None, confidence: Optional[float] = None) -> None:
        try:
            session = self.get_or_create_session(session_id)
            
            turn_data = {
                "role": role,
                "content": content,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
            if query_type is not None: turn_data["query_type"] = query_type
            if confidence is not None: turn_data["confidence"] = confidence
            
            turn = ConversationTurn(**turn_data)
            
            session.turns.append(turn)
            session.last_active = turn.timestamp
            
            # Check for compression
            if len(session.turns) > self.max_verbatim_turns + 4:
                new_summary = self.summarize_old_turns(session)
                session.summary = new_summary
                session.turns = session.turns[-self.max_verbatim_turns:]
                
            if self.redis:
                self.redis.set(
                    self._get_key(session_id),
                    session.model_dump_json(),
                    ex=self.session_ttl
                )
        except Exception as e:
            self.logger.error(f"Failed to add turn for session {session_id}: {e}")

    def get_history_for_agent7(self, session_id: str) -> list[dict]:
        history = []
        try:
            session = self.get_or_create_session(session_id)
            
            if session.summary:
                history.append({
                    "role": "system",
                    "content": f"Earlier conversation summary: {session.summary}"
                })
                
            recent_turns = session.turns[-self.max_verbatim_turns:]
            for t in recent_turns:
                history.append({
                    "role": t.role,
                    "content": t.content
                })
        except Exception as e:
            self.logger.error(f"Failed to format history for Agent 7 (session {session_id}): {e}")
            
        return history

    def clear_session(self, session_id: str) -> None:
        try:
            if self.redis:
                self.redis.delete(self._get_key(session_id))
        except Exception as e:
            self.logger.error(f"Failed to clear session {session_id}: {e}")

@dataclass
class SessionTopicData:
    session_id: str
    entities: list[str] = field(default_factory=list)
    topic_cluster: str = "default"
    query_count: int = 0
    last_updated: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

class SessionTopicModel:
    def __init__(self):
        self.logger = get_logger(__name__)
        try:
            from database.redis_client import RedisManager
            self.redis_manager = RedisManager()
            self.redis = self.redis_manager.client
        except Exception as e:
            self.logger.error(f"Failed to initialize Redis for SessionTopicModel: {e}")
            self.redis = None

    def extract_entities(self, text: str) -> list[str]:
        # Simple keyword extraction
        BIOMEDICAL_TERMS = [
            "pembrolizumab", "nivolumab", "atezolizumab",
            "pd-1", "pd-l1", "ctla-4", "car-t",
            "nsclc", "sclc", "melanoma", "lymphoma",
            "cyp3a4", "cyp2c9", "warfarin", "metformin",
            "crispr", "cas9", "snp", "indel", "brca1", "brca2",
            "immunotherapy", "chemotherapy", "radiotherapy"
        ]
        text_lower = text.lower()
        return [term for term in BIOMEDICAL_TERMS if term in text_lower]

    def update_session_model(self, session_id: str, query: str, response: str) -> None:
        try:
            key = f"topic_model:{session_id}"
            data = SessionTopicData(session_id=session_id)
            if self.redis:
                existing = self.redis.get(key)
                if existing:
                    data_dict = json.loads(existing)
                    data = SessionTopicData(**data_dict)
            
            new_entities = self.extract_entities(query + " " + response)
            data.entities.extend(new_entities)
            
            # Deduplicate and keep last 20
            seen = set()
            deduped = []
            for e in reversed(data.entities):
                if e not in seen:
                    seen.add(e)
                    deduped.append(e)
            data.entities = list(reversed(deduped))[:20]
            
            data.query_count += 1
            data.last_updated = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            # Detect dominant cluster
            cluster_counts = {"immunotherapy": 0, "drug_interactions": 0, "genomics": 0}
            for e in data.entities:
                if e in ["pembrolizumab", "nivolumab", "atezolizumab", "pd-1", "pd-l1", "ctla-4", "car-t", "immunotherapy"]:
                    cluster_counts["immunotherapy"] += 1
                elif e in ["cyp3a4", "cyp2c9", "warfarin", "metformin", "chemotherapy"]:
                    cluster_counts["drug_interactions"] += 1
                elif e in ["crispr", "cas9", "snp", "indel", "brca1", "brca2"]:
                    cluster_counts["genomics"] += 1
                    
            if sum(cluster_counts.values()) > 0:
                data.topic_cluster = max(cluster_counts, key=cluster_counts.get)
            
            if self.redis:
                self.redis.setex(key, 7200, json.dumps(asdict(data)))
        except Exception as e:
            self.logger.warning(f"Failed to update session topic model: {e}")

    def get_retrieval_bias(self, session_id: str, current_query: str) -> dict:
        try:
            if not self.redis:
                return {}
                
            key = f"topic_model:{session_id}"
            existing = self.redis.get(key)
            if not existing:
                return {}
                
            data = SessionTopicData(**json.loads(existing))
            if not data.entities:
                return {}
                
            current_entities = self.extract_entities(current_query)
            
            # If current query has entities but zero overlap, topic might have changed
            if current_entities and not any(e in data.entities for e in current_entities):
                self.logger.info(f"Topic change detected in session {session_id}. Resetting bias.")
                return {}
                
            return {
                "boost_entities": data.entities[:5],
                "preferred_cluster": data.topic_cluster,
                "context_terms": data.entities
            }
        except Exception as e:
            self.logger.warning(f"Failed to get retrieval bias: {e}")
            return {}

    def build_biased_query(self, original_query: str, bias: dict) -> str:
        try:
            if not bias:
                return original_query
                
            enhanced = original_query
            if bias.get("boost_entities"):
                top_entities = " ".join(bias["boost_entities"][:3])
                enhanced = f"{original_query} {top_entities}"
            return enhanced
        except Exception as e:
            self.logger.warning(f"Failed to build biased query: {e}")
            return original_query

class FollowUpResolver:
    FOLLOW_UP_SIGNALS = [
        "tell me more", "elaborate", "explain further",
        "what about", "and the", "the second", "first one",
        "that study", "this treatment", "same drug",
        "how about", "compared to what you said",
        "you mentioned", "the one you described"
    ]

    def __init__(self):
        self.logger = get_logger(__name__)

    def is_follow_up(self, query: str) -> bool:
        query_lower = query.lower()
        return any(signal in query_lower for signal in self.FOLLOW_UP_SIGNALS)

    def resolve_follow_up(self, query: str, session_id: str, conversation_history: list) -> str:
        try:
            if not self.is_follow_up(query):
                return query
                
            if not conversation_history:
                return query
                
            last_2_turns = conversation_history[-4:]
            
            history_text = ""
            for turn in last_2_turns:
                history_text += f"{turn.get('role', 'unknown').capitalize()}: {turn.get('content', '')}\n"
                
            prompt = f"""Given this conversation history and follow-up question,
rewrite the follow-up as a self-contained question
that does not require conversation context.

Conversation:
{history_text}

Follow-up question: {query}

Rewritten self-contained question:
(Return ONLY the rewritten question, nothing else)"""

            client = genai.Client(api_key=get_gemini_key())
            response = client.models.generate_content(
                model="gemini-flash-latest",
                contents=prompt
            )
            rewritten = response.text.strip()
            return rewritten if rewritten else query
        except Exception as e:
            self.logger.warning(f"Failed to resolve follow-up query via Gemini: {e}")
            return query

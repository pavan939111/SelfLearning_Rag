import json
import datetime
from google import genai
from dataclasses import dataclass, field, asdict
from typing import Optional
from config import get_config
from utils.logger import get_logger
from utils.llm_utils import get_gemini_key

@dataclass
class ConversationTurn:
    role: str
    content: str
    timestamp: str
    query_type: Optional[str] = None
    confidence: Optional[float] = None

@dataclass
class ConversationSession:
    session_id: str
    turns: list[ConversationTurn] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    last_active: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    summary: str = ""

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "turns": [asdict(t) for t in self.turns],
            "created_at": self.created_at,
            "last_active": self.last_active,
            "summary": self.summary
        }

    @classmethod
    def from_dict(cls, data: dict):
        turns = [ConversationTurn(**t) for t in data.get("turns", [])]
        return cls(
            session_id=data.get("session_id", ""),
            turns=turns,
            created_at=data.get("created_at", datetime.datetime.now(datetime.timezone.utc).isoformat()),
            last_active=data.get("last_active", datetime.datetime.now(datetime.timezone.utc).isoformat()),
            summary=data.get("summary", "")
        )

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
                    data = json.loads(data_str)
                    return ConversationSession.from_dict(data)
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
                model="gemini-2.0-flash",
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            self.logger.warning(f"Failed to generate summary via Gemini: {e}")
            return dialogue[:500] + "... [truncated due to LLM failure]"

    def add_turn(self, session_id: str, role: str, content: str, query_type: Optional[str] = None, confidence: Optional[float] = None) -> None:
        try:
            session = self.get_or_create_session(session_id)
            
            turn = ConversationTurn(
                role=role,
                content=content,
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                query_type=query_type,
                confidence=confidence
            )
            
            session.turns.append(turn)
            session.last_active = turn.timestamp
            
            # Check for compression
            if len(session.turns) > self.max_verbatim_turns + 4:
                new_summary = self.summarize_old_turns(session)
                session.summary = new_summary
                session.turns = session.turns[-self.max_verbatim_turns:]
                
            if self.redis:
                self.redis.setex(
                    self._get_key(session_id),
                    self.session_ttl,
                    json.dumps(session.to_dict())
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

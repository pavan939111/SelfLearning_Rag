from agents.models import ThoughtTrace
from utils.logger import get_logger
import time

logger = get_logger(__name__)

class ThoughtLogger:

    def __init__(self, session_id: str, agent: str):
        self.session_id = session_id
        self.agent = agent
        self.traces: list[ThoughtTrace] = []
        self._step_start = time.time()

    def trace(self,
              step: str,
              obs: str,
              thk: str,
              act: str,
              out: str,
              confidence: float = 0.0,
              metadata: dict = {}) -> ThoughtTrace:

        duration_ms = int(
            (time.time() - self._step_start) * 1000
        )
        self._step_start = time.time()

        t = ThoughtTrace(
            session_id=self.session_id,
            agent=self.agent,
            step=step,
            obs=obs,
            thk=thk,
            act=act,
            out=out,
            confidence=confidence,
            duration_ms=duration_ms,
            metadata=metadata
        )

        self.traces.append(t)

        # Log to console in ReAct format
        logger.info(
            f"\n"
            f"  [{self.agent.upper()}:{step}]\n"
            f"  OBS: {obs[:120]}\n"
            f"  THK: {thk[:120]}\n"
            f"  ACT: {act[:120]}\n"
            f"  OUT: {out[:120]}\n"
        )

        return t

    def get_traces(self) -> list[ThoughtTrace]:
        return self.traces

    def persist(self, supabase_manager):
        """
        Saves all traces to Supabase asynchronously.
        Call after pipeline completes.
        Never crash — traces are non-critical.
        """
        try:
            rows = [
                {
                    'trace_id': t.trace_id,
                    'session_id': t.session_id,
                    'agent': t.agent,
                    'step': t.step,
                    'obs': t.obs,
                    'thk': t.thk,
                    'act': t.act,
                    'out': t.out,
                    'confidence': t.confidence,
                    'duration_ms': t.duration_ms,
                    'metadata': t.metadata
                }
                for t in self.traces
            ]
            if rows:
                supabase_manager.client\
                    .table('thought_traces')\
                    .insert(rows)\
                    .execute()
        except Exception as e:
            logger.warning(f'Trace persist failed: {e}')

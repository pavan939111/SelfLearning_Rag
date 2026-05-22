import { useSession } from '../hooks/useSession'
import { useAgentStream } from '../hooks/useAgentStream'
import MiniChat from '../components/transparency/MiniChat'
import AgentFeed from '../components/transparency/AgentFeed'
import SystemStatePanel from '../components/transparency/SystemStatePanel'

export default function Transparency() {
  const { sessionId } = useSession()
  const { events, answer, streaming, error, stream, reset } = useAgentStream()

  const handleQuery = (query) => {
    reset()
    stream(sessionId, query)
  }

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '380px 1fr 280px',
      height: 'calc(100vh - 56px)',
      overflow: 'hidden',
    }}>
      <MiniChat
        onQuery={handleQuery}
        answer={answer}
        streaming={streaming}
      />
      <AgentFeed
        events={events}
        streaming={streaming}
      />
      <SystemStatePanel />
    </div>
  )
}

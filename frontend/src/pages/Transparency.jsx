import { useSession } from '../hooks/useSession'
import { useAgentStream } from '../hooks/useAgentStream'
import MiniChat from '../components/transparency/MiniChat'
import AgentFeed from '../components/transparency/AgentFeed'
import SystemStatePanel from '../components/transparency/SystemStatePanel'

export default function Transparency() {
  const { session } = useSession()
  const { events, streaming, answer, stream } = useAgentStream()

  const handleQuery = (text) => {
    stream(session?.id || 'demo_session', text)
  }

  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      width: '100%',
      overflow: 'hidden',
      background: 'var(--bg-primary)'
    }}>
      {/* LEFT (25%): Live Query / MiniChat */}
      <div style={{ flex: '0 0 25%', minWidth: '300px', borderRight: '1px solid var(--border)' }}>
        <MiniChat 
          onQuery={handleQuery} 
          answer={answer} 
          streaming={streaming} 
        />
      </div>

      {/* CENTER (50%): Agent activity feed */}
      <div style={{ flex: '1', borderRight: '1px solid var(--border)', background: 'var(--bg-primary)' }}>
        <AgentFeed
          events={events}
          streaming={streaming}
        />
      </div>
      
      {/* RIGHT (25%): Live metadata */}
      <div style={{ flex: '0 0 25%', minWidth: '300px', backgroundColor: 'var(--bg-secondary)' }}>
        <SystemStatePanel />
      </div>
    </div>
  )
}

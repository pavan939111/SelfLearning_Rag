import { useSession } from '../hooks/useSession'
import { useAgentStream } from '../hooks/useAgentStream'
import MiniChat from '../components/transparency/MiniChat'
import AgentFeed from '../components/transparency/AgentFeed'
import SystemStatePanel from '../components/transparency/SystemStatePanel'

export default function Transparency() {
  const { events, streaming } = useAgentStream()

  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      width: '100%',
      overflow: 'hidden',
    }}>
      {/* LEFT (60%): Agent activity feed */}
      <div style={{ flex: '6', borderRight: '1px solid var(--border)' }}>
        <AgentFeed
          events={events}
          streaming={streaming}
        />
      </div>
      
      {/* RIGHT (40%): Live metadata */}
      <div style={{ flex: '4', backgroundColor: 'var(--bg-secondary)' }}>
        <SystemStatePanel />
      </div>
    </div>
  )
}

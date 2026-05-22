import { useState, useEffect } from 'react'
import { generateSessionId } from '../api/chat'

export function useSession() {
  const [sessionId, setSessionId] = useState(() => {
    return sessionStorage.getItem('failurerag_session') 
      || generateSessionId()
  })

  useEffect(() => {
    sessionStorage.setItem('failurerag_session', sessionId)
  }, [sessionId])

  const newSession = () => {
    const id = generateSessionId()
    setSessionId(id)
    return id
  }

  return { sessionId, newSession }
}

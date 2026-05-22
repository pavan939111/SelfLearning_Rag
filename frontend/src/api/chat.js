import client from './client'
import { v4 as uuidv4 } from 'uuid'

export const generateSessionId = () => uuidv4()

export const sendMessage = async (sessionId, query, topK = 5) => {
  const response = await client.post('/chat', {
    session_id: sessionId,
    query,
    top_k: topK
  })
  return response.data
}

export const clearSession = async (sessionId) => {
  const response = await client.delete(
    `/admin/clear-session/${sessionId}`
  )
  return response.data
}

export const submitFeedback = async (feedbackData) => {
  try {
    const response = await client.post('/chat/feedback', feedbackData)
    return response.data
  } catch (err) {
    console.error('Feedback submission failed:', err)
    return null
  }
}

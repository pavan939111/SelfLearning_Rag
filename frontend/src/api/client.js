import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL
  || 'http://localhost:8000'

const API_KEY = import.meta.env.VITE_API_KEY || ''

const client = axios.create({
  baseURL: BASE_URL,
  timeout: 120000,
  headers: { 
    'Content-Type': 'application/json',
    ...(API_KEY ? { 'X-API-Key': API_KEY } : {})
  }
})

client.interceptors.response.use(
  response => response,
  async error => {
    if (
      error.code === 'ECONNABORTED' && 
      error.config && 
      !error.config.__retried
    ) {
      error.config.__retried = true
      return client(error.config)
    }
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

export default client

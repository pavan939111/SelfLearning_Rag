import axios from 'axios'

const client = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' }
})

client.interceptors.response.use(
  response => response,
  error => {
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

export default client

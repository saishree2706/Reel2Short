/** Axios API client pre-configured to talk to the FastAPI backend. */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120_000,
})

// Request interceptor to normalize accidental double '/api' prefix
api.interceptors.request.use((config) => {
  if (config.url?.startsWith('/api/')) {
    config.url = config.url.replace(/^\/api/, '')
  }
  return config
})

// Global error interceptor — adds a user-friendly message to all errors
api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response) {
      const detail = error.response.data?.detail
      const msg =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
          ? detail.map((d: { msg: string }) => d.msg).join(', ')
          : `Server error ${error.response.status}`
      error.userMessage = msg
    } else if (error.request) {
      error.userMessage = 'Cannot reach the server. Is the backend running?'
    } else {
      error.userMessage = error.message
    }
    return Promise.reject(error)
  }
)

export default api


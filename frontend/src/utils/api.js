import axios from 'axios'
const configuredApiUrl = import.meta.env?.VITE_API_URL?.trim().replace(/\/+$/, '')
const apiBaseUrl = configuredApiUrl
  ? (/\/api$/i.test(configuredApiUrl) ? configuredApiUrl : `${configuredApiUrl}/api`)
  : '/api'
const api = axios.create({
  baseURL: apiBaseUrl,
  timeout: 120000,
})
export const ACCESS_TOKEN_KEY = 'notebot.access-token'

api.interceptors.request.use((config) => {
  const token = typeof window !== 'undefined'
    ? window.localStorage.getItem(ACCESS_TOKEN_KEY)
    : null
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status
    const requestUrl = error?.config?.url || ''
    if (
      status === 401 &&
      !requestUrl.includes('/auth/login') &&
      !requestUrl.includes('/auth/register') &&
      typeof window !== 'undefined' &&
      window.localStorage.getItem(ACCESS_TOKEN_KEY)
    ) {
      window.localStorage.removeItem(ACCESS_TOKEN_KEY)
      window.dispatchEvent(new Event('notebot:auth-expired'))
    }

    if (error?.response) {
      if (status === 429 && !error.response.data?.error) {
        error.response.data = {
          ...error.response.data,
          error: 'Rate limit reached. Please wait a moment before trying again.',
        }
      } else if (status === 503 && !error.response.data?.error) {
        error.response.data = {
          ...error.response.data,
          error: 'Backend service is waking up or temporarily unavailable. Please retry in a few seconds.',
        }
      }
    }
    return Promise.reject(error)
  },
)
const HEALTH_CHECK_TIMEOUT_MS = 5000
export const isHealthyResponse = (response) =>
  response?.status >= 200 &&
  response?.status < 300 &&
  response?.data?.status === 'ok'

export const checkHealth = async () => {
  const response = await api.get('/health', { timeout: HEALTH_CHECK_TIMEOUT_MS })
  if (!isHealthyResponse(response)) {
    throw new Error('Backend health check returned an unexpected response')
  }
  return response
}
export const register = (credentials) => api.post('/auth/register', credentials)
export const login = (credentials) => api.post('/auth/login', credentials)
export const loginAsGuest = () => api.post('/auth/guest')
export const getCurrentUser = () => api.get('/auth/me')
export const logout = () => api.post('/auth/logout')
export const summarizeText = (text,opts={}) => api.post('/summarize/',{text,method:'auto',bullet_count:opts.bulletCount||6})
export const uploadPDF = (file, onProgress) => {
  const f = new FormData()
  f.append('file', file)
  return api.post('/upload/', f, {
    timeout: 180000,
    onUploadProgress: (event) => {
      if (event.total) onProgress?.(Math.round((event.loaded / event.total) * 100))
    },
  })
}
export const indexText = (text, docName='pasted-text') => api.post('/upload/text/',{text,doc_name:docName})
export const uploadFile = (file, onProgress) => {
  const f = new FormData()
  f.append('file', file)
  return api.post('/upload/', f, {
    timeout: 180000,
    onUploadProgress: (e) => onProgress?.(Math.round(100*e.loaded/e.total))
  })
}
export const getFlashcards = (docId,count=8) => api.post('/flashcards/',{doc_id:docId,count})
export const markFlashcardReviewed = (cardId) => api.post(`/flashcards/${encodeURIComponent(cardId)}/review`)
export const getQuiz = (docId, count=5, excludeQuestions=[], generationId=null) => 
  api.post('/quiz/', { doc_id: docId, count, exclude_questions: excludeQuestions, generation_id: generationId })
export const submitQuizAttempt = (questionId, selectedAnswer) =>
  api.post('/quiz/attempts', { question_id: questionId, selected_answer: selectedAnswer })
export const getQuizHistory = (docId) => api.get('/quiz/attempts', { params: docId ? { doc_id: docId } : {} })
export const getConversations = (docId) => api.get('/chat/conversations', { params: docId ? { doc_id: docId } : {} })
export const createConversation = (docId) => api.post('/chat/conversations', { doc_id: docId })
export const getConversationMessages = (conversationId) => api.get(`/chat/conversations/${conversationId}/messages`)
export const sendChatMessage = (conversationId, message) => api.post(`/chat/conversations/${conversationId}/messages`, { message })
export const summarize = (text,method='auto',bulletCount=6) => api.post('/summarize/',{text,method,bullet_count:bulletCount})
export const exportPDF = (data) => api.post('/export/pdf',data,{responseType:'blob'})
export const downloadBlob = (blob, filename) => {
  const url = window.URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }));
  const a = document.createElement('a');
  a.style.display = 'none';
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  a.remove();
}
export default api

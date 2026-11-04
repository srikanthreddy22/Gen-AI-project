import axios from 'axios'
const configuredApiUrl = import.meta.env.VITE_API_URL?.trim().replace(/\/+$/, '')
const apiBaseUrl = configuredApiUrl
  ? (/\/api$/i.test(configuredApiUrl) ? configuredApiUrl : `${configuredApiUrl}/api`)
  : '/api'
const api = axios.create({
  baseURL: apiBaseUrl,
  timeout: 60000,
})
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
export const summarizeText = (text,opts={}) => api.post('/summarize/',{text,method:'auto',bullet_count:opts.bulletCount||6})
export const uploadPDF = (file, onProgress) => {
  const f = new FormData()
  f.append('file', file)
  return api.post('/upload/', f, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (event.total) onProgress?.(Math.round((event.loaded / event.total) * 100))
    },
  })
}
export const indexText = (text, docName='pasted-text') => api.post('/upload/text/',{text,doc_name:docName})
export const uploadFile = (file, onProgress) => {
  const f=new FormData()
  f.append('file',file)
  return api.post('/upload/',f,{
    headers:{'Content-Type':'multipart/form-data'},
    onUploadProgress: (e) => onProgress?.(Math.round(100*e.loaded/e.total))
  })
}
export const getFlashcards = (docId,count=8) => api.post('/flashcards/',{doc_id:docId,count})
export const getQuiz = (docId, count=5, excludeQuestions=[], generationId=null) => 
  api.post('/quiz/', { doc_id: docId, count, exclude_questions: excludeQuestions, generation_id: generationId })
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

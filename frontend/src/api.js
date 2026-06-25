import axios from 'axios'

// In production (Render), VITE_API_URL = https://tool-o148.onrender.com
// In local dev, requests go through Vite proxy to localhost:8000
const baseURL = import.meta.env.VITE_API_URL ? import.meta.env.VITE_API_URL : ''

const api = axios.create({
  baseURL,
  withCredentials: true,
})

export default api

// 👇 New: Start auto‑scan with Server‑Sent Events
export const startAutoScan = (brandName, geminiKeyId = null, geminiApiKey = null, model = "gemini-2.5-flash") => {
  const params = new URLSearchParams()
  params.append("brand_name", brandName)
  if (geminiKeyId) params.append("gemini_key_id", geminiKeyId)
  if (geminiApiKey) params.append("gemini_api_key", geminiApiKey)
  if (model) params.append("model", model)

  const url = `${baseURL}/api/auto-scan?${params.toString()}`
  return new EventSource(url, { withCredentials: true })
}

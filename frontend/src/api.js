import axios from 'axios'

// In production (Render), VITE_API_URL = https://tool-o148.onrender.com
// In local dev, requests go through Vite proxy to localhost:8000
const baseURL = import.meta.env.VITE_API_URL ? import.meta.env.VITE_API_URL : ''

const api = axios.create({
  baseURL,
  withCredentials: true,
})

export default api

// 👇 Start auto‑scan with Server‑Sent Events
export const startAutoScan = (brandName, geminiKeyId = null, geminiApiKey = null, model = "gemini-2.5-flash") => {
  const params = new URLSearchParams()
  params.append("brand_name", brandName)
  if (geminiKeyId) params.append("gemini_key_id", geminiKeyId)
  if (geminiApiKey) params.append("gemini_api_key", geminiApiKey)
  if (model) params.append("model", model)

  const url = `${baseURL}/api/auto-scan?${params.toString()}`
  return new EventSource(url, { withCredentials: true })
}

// ================================================================
// GROUP MANAGEMENT
// ================================================================

// Get all scanned groups for the current user
export const getScannedGroups = () => 
  api.get('/api/groups').then(res => res.data)

// Scan new groups by keyword (uses AI to expand keywords)
export const scanGroups = (keyword, model = "gemini-2.5-flash") =>
  api.post('/api/groups/search', { keyword, model }).then(res => res.data)

// Fetch messages from a specific group
export const getGroupMessages = (groupUsername) =>
  api.post('/api/groups/messages', { group_username: groupUsername }).then(res => res.data)

// ================================================================
// RECRUITMENT POSTS
// ================================================================

// Generate a unique recruitment post using AI
export const generateRecruitmentPost = (brandName = 'ACE2KING') =>
  api.get('/api/group-posts/generate-message', { params: { brand_name: brandName } })
    .then(res => res.data.message)

// Check if the group allows sending messages (restricted?)
export const checkGroupPermissions = (groupUsername) =>
  api.get('/api/group-posts/check-permissions', { params: { group_username: groupUsername } })
    .then(res => res.data.can_send)

// Send the recruitment post to selected groups with brand_name
export const sendPostToGroups = (groupUsernames, message, delayBetween = 2.0, brandName = 'ACE2KING') =>
  api.post('/api/group-posts/send', {
    group_usernames: groupUsernames,
    message,
    delay_between: delayBetween,
    brand_name: brandName   // 👈 added
  }).then(res => res.data)

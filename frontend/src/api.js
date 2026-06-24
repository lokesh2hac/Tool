import axios from 'axios'

// In production (Render), VITE_API_URL = https://tool-o148.onrender.com
// In local dev, requests go through Vite proxy to localhost:8000
const baseURL = import.meta.env.VITE_API_URL ? import.meta.env.VITE_API_URL : ''

const api = axios.create({
  baseURL,
  withCredentials: true,
})

export default api

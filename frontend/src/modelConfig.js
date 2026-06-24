export const MODEL_STORAGE_KEY = 'ace2king_model'
export const DEFAULT_MODEL = 'gemini-2.5-flash'

export const MODEL_OPTIONS = [
  { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash', note: 'recommended' },
  { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' },
  { value: 'llama-3.3-70b-versatile', label: 'Groq llama-3.3-70b', note: 'free fallback' },
]

export function getStoredModel() {
  if (typeof window === 'undefined') return DEFAULT_MODEL
  return localStorage.getItem(MODEL_STORAGE_KEY) || DEFAULT_MODEL
}

export function setStoredModel(model) {
  if (typeof window === 'undefined') return
  localStorage.setItem(MODEL_STORAGE_KEY, model || DEFAULT_MODEL)
}

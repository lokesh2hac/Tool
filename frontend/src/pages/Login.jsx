import { useState } from 'react'
import api from '../api'

export default function Login({ setAuth, showToast }) {
  const [step, setStep] = useState(1)
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [phoneCodeHash, setPhoneCodeHash] = useState('')  // store hash from backend
  const [loading, setLoading] = useState(false)

  const handleSendCode = async (e) => {
    e.preventDefault()
    if (!phone.trim()) return
    setLoading(true)
    try {
      const res = await api.post('/api/auth/send-code', { phone })
      // Save phone_code_hash returned from backend
      setPhoneCodeHash(res.data.phone_code_hash)
      setStep(2)
      showToast('OTP sent to your Telegram!', 'success')
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to send OTP', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleVerifyCode = async (e) => {
    e.preventDefault()
    if (!code.trim()) return
    if (!phoneCodeHash) {
      showToast('Session lost. Please request OTP again.', 'error')
      setStep(1)
      return
    }
    setLoading(true)
    try {
      // Send phone_code_hash back to backend for real Telegram verification
      const res = await api.post('/api/auth/verify-code', {
        phone,
        code,
        phone_code_hash: phoneCodeHash,
      })
      showToast('Logged in successfully!', 'success')
      setAuth({ logged_in: true, phone, username: res.data.username })
    } catch (err) {
      showToast(err.response?.data?.detail || 'Invalid OTP. Please try again.', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleBack = () => {
    setStep(1)
    setCode('')
    setPhoneCodeHash('')
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo / Branding */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-amber-500 to-yellow-400 mb-4 shadow-lg shadow-amber-500/30">
            <span className="text-3xl font-black text-gray-900">A2K</span>
          </div>
          <h1 className="text-3xl font-bold text-white">ACE2KING</h1>
          <p className="text-gray-400 mt-1">Affiliate Candidate Finder</p>
        </div>

        <div className="bg-surface rounded-2xl border border-gray-800 p-8 shadow-2xl">
          <h2 className="text-xl font-semibold text-white mb-6">
            {step === 1 ? 'Sign in with Telegram' : 'Enter OTP'}
          </h2>

          {step === 1 ? (
            <form onSubmit={handleSendCode} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Phone Number
                </label>
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+91 9876543210"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-amber-500 transition-colors"
                  required
                />
                <p className="text-xs text-gray-500 mt-1">Include country code (e.g. +91 for India)</p>
              </div>
              <button type="submit" disabled={loading} className="btn-gold w-full py-3">
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="w-4 h-4 border-2 border-gray-900 border-t-transparent rounded-full animate-spin" />
                    Sending OTP...
                  </span>
                ) : 'Send OTP'}
              </button>
            </form>
          ) : (
            <form onSubmit={handleVerifyCode} className="space-y-4">
              <div>
                <p className="text-sm text-gray-400 mb-4">
                  OTP sent to <span className="text-amber-400 font-medium">{phone}</span>
                </p>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Verification Code
                </label>
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                  placeholder="Enter OTP from Telegram"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-amber-500 transition-colors text-center tracking-widest text-lg"
                  maxLength={6}
                  required
                />
              </div>
              <button type="submit" disabled={loading} className="btn-gold w-full py-3">
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="w-4 h-4 border-2 border-gray-900 border-t-transparent rounded-full animate-spin" />
                    Verifying...
                  </span>
                ) : 'Verify & Login'}
              </button>
              <button
                type="button"
                onClick={handleBack}
                className="w-full text-gray-400 hover:text-white text-sm transition-colors py-2"
              >
                ← Use a different number
              </button>
            </form>
          )}
        </div>

        <p className="text-center text-gray-600 text-xs mt-6">
          ACE2KING HR Platform · Powered by Gemini AI
        </p>
      </div>
    </div>
  )
}

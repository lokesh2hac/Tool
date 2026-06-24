import { useState } from 'react'
import api from '../api'

export default function Login({ setAuth, showToast }) {
  // step 1 = phone input, step 2 = OTP input, step 3 = 2FA password input
  const [step, setStep] = useState(1)
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [phoneCodeHash, setPhoneCodeHash] = useState('')
  const [loading, setLoading] = useState(false)

  // Step 1: Send OTP
  const handleSendCode = async (e) => {
    e.preventDefault()
    if (!phone.trim()) return
    setLoading(true)
    try {
      const res = await api.post('/api/auth/send-code', { phone })
      setPhoneCodeHash(res.data.phone_code_hash)
      setStep(2)
      showToast('OTP sent to your Telegram!', 'success')
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to send OTP', 'error')
    } finally {
      setLoading(false)
    }
  }

  // Step 2: Verify OTP
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
      const res = await api.post('/api/auth/verify-code', {
        phone,
        code,
        phone_code_hash: phoneCodeHash,
      })
      if (res.data.requires_password) {
        // 2FA is enabled — go to step 3
        setStep(3)
        showToast('OTP verified! Please enter your 2FA password.', 'success')
      } else {
        showToast('Logged in successfully!', 'success')
        setAuth({ logged_in: true, phone, username: res.data.username })
      }
    } catch (err) {
      showToast(err.response?.data?.detail || 'Invalid OTP. Please try again.', 'error')
    } finally {
      setLoading(false)
    }
  }

  // Step 3: Verify 2FA password
  const handleVerifyPassword = async (e) => {
    e.preventDefault()
    if (!password.trim()) return
    setLoading(true)
    try {
      const res = await api.post('/api/auth/verify-password', { phone, password })
      showToast('Logged in successfully!', 'success')
      setAuth({ logged_in: true, phone, username: res.data.username })
    } catch (err) {
      showToast(err.response?.data?.detail || 'Incorrect password. Please try again.', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleBack = () => {
    setStep(1)
    setCode('')
    setPassword('')
    setPhoneCodeHash('')
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Branding */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-amber-500 to-yellow-400 mb-4 shadow-lg shadow-amber-500/30">
            <span className="text-3xl font-black text-gray-900">A2K</span>
          </div>
          <h1 className="text-3xl font-bold text-white">ACE2KING</h1>
          <p className="text-gray-400 mt-1">Affiliate Candidate Finder</p>
        </div>

        <div className="bg-surface rounded-2xl border border-gray-800 p-8 shadow-2xl">

          {/* Step indicator */}
          <div className="flex items-center gap-2 mb-6">
            {[1,2,3].map(s => (
              <div key={s} className={`h-1 flex-1 rounded-full transition-colors ${
                s <= step ? 'bg-amber-500' : 'bg-gray-700'
              }`} />
            ))}
          </div>

          <h2 className="text-xl font-semibold text-white mb-6">
            {step === 1 && 'Sign in with Telegram'}
            {step === 2 && 'Enter OTP'}
            {step === 3 && 'Two-Step Verification'}
          </h2>

          {/* Step 1 — Phone */}
          {step === 1 && (
            <form onSubmit={handleSendCode} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Phone Number</label>
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
                {loading ? <Spinner text="Sending OTP..." /> : 'Send OTP'}
              </button>
            </form>
          )}

          {/* Step 2 — OTP */}
          {step === 2 && (
            <form onSubmit={handleVerifyCode} className="space-y-4">
              <div>
                <p className="text-sm text-gray-400 mb-4">
                  OTP sent to <span className="text-amber-400 font-medium">{phone}</span>
                </p>
                <label className="block text-sm font-medium text-gray-300 mb-2">Verification Code</label>
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                  placeholder="Enter 5-digit OTP"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-amber-500 transition-colors text-center tracking-widest text-lg"
                  maxLength={6}
                  required
                />
              </div>
              <button type="submit" disabled={loading} className="btn-gold w-full py-3">
                {loading ? <Spinner text="Verifying..." /> : 'Verify OTP'}
              </button>
              <button type="button" onClick={handleBack} className="w-full text-gray-400 hover:text-white text-sm transition-colors py-2">
                ← Use a different number
              </button>
            </form>
          )}

          {/* Step 3 — 2FA Password */}
          {step === 3 && (
            <form onSubmit={handleVerifyPassword} className="space-y-4">
              <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
                <p className="text-amber-400 text-sm">
                  🔒 Two-step verification is enabled on your account. Please enter your Telegram 2FA password.
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">2FA Password</label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your Telegram password"
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-amber-500 transition-colors pr-12"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white text-sm"
                  >
                    {showPassword ? 'Hide' : 'Show'}
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-1">This is the password set in Telegram → Settings → Privacy → Two-Step Verification</p>
              </div>
              <button type="submit" disabled={loading} className="btn-gold w-full py-3">
                {loading ? <Spinner text="Logging in..." /> : 'Login'}
              </button>
              <button type="button" onClick={handleBack} className="w-full text-gray-400 hover:text-white text-sm transition-colors py-2">
                ← Start over
              </button>
            </form>
          )}
        </div>

        <p className="text-center text-gray-600 text-xs mt-6">
          ACE2KING HR Platform · Powered by Groq & Gemini AI
        </p>
      </div>
    </div>
  )
}

function Spinner({ text }) {
  return (
    <span className="flex items-center justify-center gap-2">
      <span className="w-4 h-4 border-2 border-gray-900 border-t-transparent rounded-full animate-spin" />
      {text}
    </span>
  )
}

import React, { useState } from 'react'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'
import { ACCESS_TOKEN_KEY, login, register } from '../utils/api'

export default function AuthPage({ onAuthenticated }) {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const isRegistering = mode === 'register'

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const response = isRegistering
        ? await register({ email, username, password })
        : await login({ email, password })
      window.localStorage.setItem(ACCESS_TOKEN_KEY, response.data.token)
      onAuthenticated(response.data.user)
    } catch (requestError) {
      const message = requestError?.response?.data?.error || 'Could not sign in. Please try again.'
      setError(message)
      toast.error(message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main
      className="auth-screen"
      style={{ display: 'grid', placeItems: 'center', padding: 24 }}
    >
      <motion.section
        className="glass-panel"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        style={{ width: 'min(100%, 430px)', padding: 32, position: 'relative' }}
      >
        <p className="font-mono" style={{ color: 'var(--accent)', fontSize: 11, margin: '0 0 12px' }}>
          NOTEBOT · STUDY WORKSPACE
        </p>
        <h1 style={{ margin: '0 0 8px', fontSize: 32 }}>
          {isRegistering ? 'Create your account' : 'Welcome back'}
        </h1>
        <p style={{ color: 'var(--text-soft)', margin: '0 0 24px', lineHeight: 1.6 }}>
          Sign in to keep your study documents and learning history private.
        </p>

        <form onSubmit={submit} style={{ display: 'grid', gap: 14 }}>
          <label style={{ display: 'grid', gap: 6, color: 'var(--text-soft)', fontSize: 12 }}>
            Email
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              style={{ width: '100%', minHeight: 42, borderRadius: 'var(--radius-sm)', border: '1px solid var(--line)', padding: '0 12px' }}
            />
          </label>

          {isRegistering && (
            <label style={{ display: 'grid', gap: 6, color: 'var(--text-soft)', fontSize: 12 }}>
              Username
              <input
                type="text"
                autoComplete="username"
                minLength={2}
                maxLength={120}
                required
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                style={{ width: '100%', minHeight: 42, borderRadius: 'var(--radius-sm)', border: '1px solid var(--line)', padding: '0 12px' }}
              />
            </label>
          )}

          <label style={{ display: 'grid', gap: 6, color: 'var(--text-soft)', fontSize: 12 }}>
            Password
            <input
              type="password"
              autoComplete={isRegistering ? 'new-password' : 'current-password'}
              minLength={isRegistering ? 8 : undefined}
              maxLength={1024}
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              style={{ width: '100%', minHeight: 42, borderRadius: 'var(--radius-sm)', border: '1px solid var(--line)', padding: '0 12px' }}
            />
          </label>

          {error && (
            <p role="alert" style={{ color: 'var(--danger)', margin: 0, fontSize: 12 }}>
              {error}
            </p>
          )}

          <button type="submit" className="btn-primary" disabled={submitting} style={{ marginTop: 6 }}>
            {submitting ? 'Please wait…' : isRegistering ? 'Create account' : 'Sign in'}
          </button>
        </form>

        <p style={{ margin: '20px 0 0', color: 'var(--text-soft)', textAlign: 'center', fontSize: 12 }}>
          {isRegistering ? 'Already have an account?' : 'New to NoteBot?'}{' '}
          <button
            type="button"
            className="btn-ghost"
            onClick={() => {
              setError('')
              setMode(isRegistering ? 'login' : 'register')
            }}
            style={{ minHeight: 30, border: 0, padding: '0 4px', color: 'var(--accent)' }}
          >
            {isRegistering ? 'Sign in' : 'Create an account'}
          </button>
        </p>
      </motion.section>
    </main>
  )
}

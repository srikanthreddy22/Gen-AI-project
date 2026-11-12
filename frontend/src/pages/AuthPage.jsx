import React, { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion'
import { Mail, Lock, Eye, EyeOff } from 'lucide-react'
import toast from 'react-hot-toast'
import { ACCESS_TOKEN_KEY, login, loginAsGuest, register } from '../utils/api'
import SceneBackdrop from '../components/background/SceneBackdrop'
import Logo from '../components/brand/Logo'
import AuthParticles from '../components/auth/AuthParticles'

function TypewriterText({ text, delay = 0.08, reducedMotion }) {
  if (reducedMotion) {
    return <span>{text}</span>
  }
  return (
    <span aria-label={text}>
      {text.split('').map((char, index) => (
        <motion.span
          key={index}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: delay + index * 0.03, duration: 0.01 }}
          aria-hidden="true"
        >
          {char}
        </motion.span>
      ))}
    </span>
  )
}

export default function AuthPage({ onAuthenticated }) {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [toastError, setToastError] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [emailFocused, setEmailFocused] = useState(false)
  const [usernameFocused, setUsernameFocused] = useState(false)
  const [passwordFocused, setPasswordFocused] = useState(false)
  const [invalidFields, setInvalidFields] = useState({ email: false, username: false, password: false })
  const [tilt, setTilt] = useState({ rotateX: 0, rotateY: 0 })
  const [isCardHovered, setIsCardHovered] = useState(false)

  const cardRef = useRef(null)
  const reducedMotion = useReducedMotion()
  const isRegistering = mode === 'register'

  useEffect(() => {
    if (error) {
      setToastError(error)
      const timer = setTimeout(() => setToastError(''), 4000)
      return () => clearTimeout(timer)
    }
  }, [error])

  const triggerShake = (fieldName) => {
    setInvalidFields((prev) => ({ ...prev, [fieldName]: true }))
    setTimeout(() => {
      setInvalidFields((prev) => ({ ...prev, [fieldName]: false }))
    }, 600)
  }

  const handleMouseMove = (e) => {
    if (reducedMotion) return
    if (typeof window !== 'undefined' && window.matchMedia('(pointer: coarse)').matches) return
    const rect = cardRef.current?.getBoundingClientRect()
    if (!rect) return
    const x = e.clientX - rect.left - rect.width / 2
    const y = e.clientY - rect.top - rect.height / 2
    const maxTilt = 4
    const rotateY = (x / (rect.width / 2)) * maxTilt
    const rotateX = -(y / (rect.height / 2)) * maxTilt
    setTilt({ rotateX, rotateY })
  }

  const handleMouseLeave = () => {
    setTilt({ rotateX: 0, rotateY: 0 })
    setIsCardHovered(false)
  }

  const handleMouseEnter = () => {
    setIsCardHovered(true)
  }

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setToastError('')
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

  const handleGuestSignIn = async () => {
    setError('')
    setToastError('')
    setSubmitting(true)
    try {
      const response = await loginAsGuest()
      if (response?.data?.token) {
        window.localStorage.setItem(ACCESS_TOKEN_KEY, response.data.token)
        onAuthenticated(response.data.user)
      } else {
        const guestUser = { id: 'guest', username: 'Guest User', email: 'guest@notebot.local', is_guest: true }
        onAuthenticated(guestUser)
      }
      toast.success('Signed in as guest')
    } catch {
      const guestUser = { id: 'guest', username: 'Guest User', email: 'guest@notebot.local', is_guest: true }
      onAuthenticated(guestUser)
      toast.success('Signed in as guest')
    } finally {
      setSubmitting(false)
    }
  }

  const stagger = (step) => ({
    initial: reducedMotion ? { opacity: 0 } : { opacity: 0, y: 14 },
    animate: reducedMotion ? { opacity: 1 } : { opacity: 1, y: 0 },
    transition: {
      duration: 0.38,
      delay: reducedMotion ? 0 : step * 0.08,
      ease: 'easeOut',
    },
  })

  return (
    <main
      className="auth-screen relative min-h-screen w-full flex items-center justify-center p-4 sm:p-6 overflow-x-hidden"
      style={{
        background: 'transparent',
      }}
    >
      {/* 1. Animated background with SceneBackdrop and floating particles */}
      <SceneBackdrop variant="auth" />
      <AuthParticles />

      {/* Floating error toast notification (slides from top, fades after 4s) */}
      <AnimatePresence>
        {toastError && (
          <motion.div
            role="alert"
            aria-live="assertive"
            initial={reducedMotion ? { opacity: 0 } : { opacity: 0, y: -24, scale: 0.96 }}
            animate={reducedMotion ? { opacity: 1 } : { opacity: 1, y: 0, scale: 1 }}
            exit={reducedMotion ? { opacity: 0 } : { opacity: 0, y: -18, scale: 0.96 }}
            transition={{ duration: 0.28, ease: 'easeOut' }}
            style={{
              position: 'fixed',
              top: 24,
              left: '50%',
              transform: 'translateX(-50%)',
              zIndex: 100,
              maxWidth: 420,
              width: 'calc(100% - 32px)',
              background: 'rgba(255, 255, 255, 0.95)',
              backdropFilter: 'blur(16px)',
              WebkitBackdropFilter: 'blur(16px)',
              border: '1px solid rgba(248, 113, 113, 0.45)',
              borderRadius: 16,
              padding: '12px 18px',
              boxShadow: '0 12px 30px -5px rgba(239, 68, 68, 0.2), 0 4px 12px -2px rgba(15, 23, 42, 0.08)',
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              color: '#b91c1c',
              fontSize: 13,
              fontWeight: 500,
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: '#ef4444',
                flexShrink: 0,
              }}
              aria-hidden="true"
            />
            <span style={{ flex: 1 }}>{toastError}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 2. Card with Entrance, Glassmorphism, Rounded Corners, and 3D Tilt */}
      <div
        style={{
          perspective: 1000,
          width: '100%',
          display: 'flex',
          justifyContent: 'center',
          zIndex: 10,
        }}
      >
        <motion.section
          ref={cardRef}
          onMouseMove={handleMouseMove}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          initial={reducedMotion ? { opacity: 0 } : { opacity: 0, y: 24 }}
          animate={reducedMotion ? { opacity: 1 } : { opacity: 1, y: 0 }}
          transition={reducedMotion ? { duration: 0.3 } : { type: 'spring', stiffness: 120, damping: 16 }}
          className="rounded-3xl"
          style={{
            width: 'min(100%, 430px)',
            padding: '36px 32px',
            position: 'relative',
            background: 'rgba(255, 255, 255, 0.78)',
            backdropFilter: 'blur(24px)',
            WebkitBackdropFilter: 'blur(24px)',
            border: '1px solid rgba(34, 211, 238, 0.25)',
            boxShadow: isCardHovered
              ? '0 20px 45px -10px rgba(34, 211, 238, 0.28), 0 12px 24px -6px rgba(15, 23, 42, 0.08)'
              : '0 12px 35px -5px rgba(34, 211, 238, 0.16), 0 8px 16px -4px rgba(15, 23, 42, 0.05)',
            transform: reducedMotion ? 'none' : `rotateX(${tilt.rotateX}deg) rotateY(${tilt.rotateY}deg)`,
            transition: 'box-shadow 0.3s ease, transform 0.15s ease-out',
            transformStyle: 'preserve-3d',
            willChange: 'transform, box-shadow',
          }}
        >
          {/* Step 0: Logo with stroke animation and gentle pulse */}
          <motion.div {...stagger(0)} style={{ marginBottom: 18 }}>
            <Logo animated size={40} />
          </motion.div>

          {/* Step 1: "NOTEBOT · STUDY WORKSPACE" label typing letter by letter */}
          <motion.p
            {...stagger(1)}
            className="font-mono"
            style={{
              color: 'var(--accent)',
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: '0.06em',
              margin: '0 0 10px',
            }}
          >
            <TypewriterText text="NOTEBOT · STUDY WORKSPACE" delay={0.08} reducedMotion={reducedMotion} />
          </motion.p>

          {/* Step 2: "Welcome back" heading sliding up and fading in */}
          <motion.h1
            {...stagger(2)}
            style={{
              margin: '0 0 8px',
              fontSize: 32,
              fontWeight: 700,
              color: 'var(--ink)',
              letterSpacing: '-0.02em',
            }}
          >
            {isRegistering ? 'Create your account' : 'Welcome back'}
          </motion.h1>

          {/* Step 3: Subtitle */}
          <motion.p
            {...stagger(3)}
            style={{
              color: 'var(--text-soft)',
              margin: '0 0 24px',
              fontSize: 14,
              lineHeight: 1.6,
            }}
          >
            Sign in to keep your study documents and learning history private.
          </motion.p>

          {/* Form with staggered inputs */}
          <form onSubmit={submit} style={{ display: 'grid', gap: 16 }}>
            {/* Step 4: Email Input */}
            <motion.div {...stagger(4)}>
              <label
                htmlFor="auth-email"
                style={{
                  display: 'grid',
                  gap: 6,
                  color: emailFocused ? '#06b6d4' : 'var(--text-soft)',
                  fontSize: 12,
                  fontWeight: 600,
                  transform: emailFocused && !reducedMotion ? 'translateY(-2px)' : 'none',
                  transition: 'color 0.2s ease, transform 0.2s ease',
                }}
              >
                Email
                <div style={{ position: 'relative' }}>
                  <span
                    aria-hidden="true"
                    style={{
                      position: 'absolute',
                      left: 12,
                      top: '50%',
                      transform: 'translateY(-50%)',
                      pointerEvents: 'none',
                      display: 'flex',
                      alignItems: 'center',
                      color: emailFocused ? '#0891b2' : '#94a3b8',
                      transition: 'color 0.2s ease',
                      zIndex: 2,
                    }}
                  >
                    <Mail size={17} />
                  </span>
                  <motion.input
                    id="auth-email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={(event) => {
                      setEmail(event.target.value)
                      if (invalidFields.email) setInvalidFields((prev) => ({ ...prev, email: false }))
                    }}
                    onFocus={() => setEmailFocused(true)}
                    onBlur={() => setEmailFocused(false)}
                    onInvalid={() => triggerShake('email')}
                    animate={
                      invalidFields.email && !reducedMotion
                        ? { x: [0, -8, 8, -6, 6, -3, 3, 0] }
                        : { x: 0 }
                    }
                    transition={{ duration: 0.45 }}
                    style={{
                      width: '100%',
                      minHeight: 44,
                      borderRadius: 'var(--radius-sm)',
                      border: invalidFields.email
                        ? '1px solid var(--danger)'
                        : emailFocused
                        ? '1px solid #22d3ee'
                        : '1px solid rgba(203, 213, 225, 0.8)',
                      padding: '0 14px 0 38px',
                      background: emailFocused
                        ? 'rgba(255, 255, 255, 0.98)'
                        : 'rgba(255, 255, 255, 0.88)',
                      boxShadow: emailFocused
                        ? '0 0 0 2px rgba(34, 211, 238, 0.4), 0 0 12px rgba(34, 211, 238, 0.2)'
                        : '0 1px 2px rgba(0, 0, 0, 0.04)',
                      color: 'var(--ink)',
                      fontSize: 14,
                      transition: 'background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease',
                      outline: 'none',
                    }}
                  />
                </div>
              </label>
            </motion.div>

            {/* Username Input if Registering */}
            {isRegistering && (
              <motion.div {...stagger(4.5)}>
                <label
                  htmlFor="auth-username"
                  style={{
                    display: 'grid',
                    gap: 6,
                    color: usernameFocused ? '#06b6d4' : 'var(--text-soft)',
                    fontSize: 12,
                    fontWeight: 600,
                    transform: usernameFocused && !reducedMotion ? 'translateY(-2px)' : 'none',
                    transition: 'color 0.2s ease, transform 0.2s ease',
                  }}
                >
                  Username
                  <div style={{ position: 'relative' }}>
                    <motion.input
                      id="auth-username"
                      name="username"
                      type="text"
                      autoComplete="username"
                      minLength={2}
                      maxLength={120}
                      required
                      value={username}
                      onChange={(event) => {
                        setUsername(event.target.value)
                        if (invalidFields.username) setInvalidFields((prev) => ({ ...prev, username: false }))
                      }}
                      onFocus={() => setUsernameFocused(true)}
                      onBlur={() => setUsernameFocused(false)}
                      onInvalid={() => triggerShake('username')}
                      animate={
                        invalidFields.username && !reducedMotion
                          ? { x: [0, -8, 8, -6, 6, -3, 3, 0] }
                          : { x: 0 }
                      }
                      transition={{ duration: 0.45 }}
                      style={{
                        width: '100%',
                        minHeight: 44,
                        borderRadius: 'var(--radius-sm)',
                        border: invalidFields.username
                          ? '1px solid var(--danger)'
                          : usernameFocused
                          ? '1px solid #22d3ee'
                          : '1px solid rgba(203, 213, 225, 0.8)',
                        padding: '0 14px',
                        background: usernameFocused
                          ? 'rgba(255, 255, 255, 0.98)'
                          : 'rgba(255, 255, 255, 0.88)',
                        boxShadow: usernameFocused
                          ? '0 0 0 2px rgba(34, 211, 238, 0.4), 0 0 12px rgba(34, 211, 238, 0.2)'
                          : '0 1px 2px rgba(0, 0, 0, 0.04)',
                        color: 'var(--ink)',
                        fontSize: 14,
                        transition: 'background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease',
                        outline: 'none',
                      }}
                    />
                  </div>
                </label>
              </motion.div>
            )}

            {/* Step 5: Password Input with Eye Toggle */}
            <motion.div {...stagger(5)}>
              <label
                htmlFor="auth-password"
                style={{
                  display: 'grid',
                  gap: 6,
                  color: passwordFocused ? '#06b6d4' : 'var(--text-soft)',
                  fontSize: 12,
                  fontWeight: 600,
                  transform: passwordFocused && !reducedMotion ? 'translateY(-2px)' : 'none',
                  transition: 'color 0.2s ease, transform 0.2s ease',
                }}
              >
                Password
                <div style={{ position: 'relative' }}>
                  <span
                    aria-hidden="true"
                    style={{
                      position: 'absolute',
                      left: 12,
                      top: '50%',
                      transform: 'translateY(-50%)',
                      pointerEvents: 'none',
                      display: 'flex',
                      alignItems: 'center',
                      color: passwordFocused ? '#0891b2' : '#94a3b8',
                      transition: 'color 0.2s ease',
                      zIndex: 2,
                    }}
                  >
                    <Lock size={17} />
                  </span>
                  <motion.input
                    id="auth-password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete={isRegistering ? 'new-password' : 'current-password'}
                    minLength={isRegistering ? 8 : undefined}
                    maxLength={1024}
                    required
                    value={password}
                    onChange={(event) => {
                      setPassword(event.target.value)
                      if (invalidFields.password) setInvalidFields((prev) => ({ ...prev, password: false }))
                    }}
                    onFocus={() => setPasswordFocused(true)}
                    onBlur={() => setPasswordFocused(false)}
                    onInvalid={() => triggerShake('password')}
                    animate={
                      invalidFields.password && !reducedMotion
                        ? { x: [0, -8, 8, -6, 6, -3, 3, 0] }
                        : { x: 0 }
                    }
                    transition={{ duration: 0.45 }}
                    style={{
                      width: '100%',
                      minHeight: 44,
                      borderRadius: 'var(--radius-sm)',
                      border: invalidFields.password
                        ? '1px solid var(--danger)'
                        : passwordFocused
                        ? '1px solid #22d3ee'
                        : '1px solid rgba(203, 213, 225, 0.8)',
                      padding: '0 42px 0 38px',
                      background: passwordFocused
                        ? 'rgba(255, 255, 255, 0.98)'
                        : 'rgba(255, 255, 255, 0.88)',
                      boxShadow: passwordFocused
                        ? '0 0 0 2px rgba(34, 211, 238, 0.4), 0 0 12px rgba(34, 211, 238, 0.2)'
                        : '0 1px 2px rgba(0, 0, 0, 0.04)',
                      color: 'var(--ink)',
                      fontSize: 14,
                      transition: 'background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease',
                      outline: 'none',
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    style={{
                      position: 'absolute',
                      right: 8,
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'none',
                      border: 'none',
                      padding: 6,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      borderRadius: 6,
                      color: showPassword ? '#0891b2' : '#94a3b8',
                      zIndex: 2,
                    }}
                    className="focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:outline-none"
                  >
                    <AnimatePresence mode="wait" initial={false}>
                      <motion.span
                        key={showPassword ? 'shown' : 'hidden'}
                        initial={reducedMotion ? false : { opacity: 0, rotate: -35 }}
                        animate={reducedMotion ? { opacity: 1 } : { opacity: 1, rotate: 0 }}
                        exit={reducedMotion ? { opacity: 0 } : { opacity: 0, rotate: 35 }}
                        transition={{ duration: 0.2 }}
                        style={{ display: 'flex', alignItems: 'center' }}
                      >
                        {showPassword ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
                      </motion.span>
                    </AnimatePresence>
                  </button>
                </div>
              </label>
            </motion.div>

            {/* Error Message inside form if present */}
            {error && (
              <p role="alert" style={{ color: 'var(--danger)', margin: 0, fontSize: 12, fontWeight: 500 }}>
                {error}
              </p>
            )}

            {/* Step 6: Sign in button with continuous shimmer and loading spinner */}
            <motion.div {...stagger(6)}>
              <motion.button
                type="submit"
                className="btn-primary"
                disabled={submitting}
                whileTap={reducedMotion ? {} : { scale: 0.97 }}
                style={{
                  position: 'relative',
                  overflow: 'hidden',
                  width: '100%',
                  minHeight: 44,
                  fontSize: 14,
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginTop: 6,
                  boxShadow: '0 4px 14px -2px rgba(34, 211, 238, 0.45)',
                }}
              >
                {!reducedMotion && !submitting && (
                  <motion.span
                    aria-hidden="true"
                    style={{
                      position: 'absolute',
                      inset: 0,
                      pointerEvents: 'none',
                      background: 'linear-gradient(105deg, transparent 20%, rgba(255, 255, 255, 0.45) 50%, transparent 80%)',
                    }}
                    animate={{ x: ['-100%', '200%'] }}
                    transition={{
                      repeat: Infinity,
                      duration: 1.2,
                      repeatDelay: 1.8,
                      ease: 'easeInOut',
                    }}
                  />
                )}
                {submitting ? (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                    <svg
                      className="animate-spin"
                      style={{ width: 18, height: 18, color: '#ffffff' }}
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <circle style={{ opacity: 0.25 }} cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path style={{ opacity: 0.85 }} fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                    </svg>
                    <span className="sr-only">{isRegistering ? 'Create account' : 'Sign in'}</span>
                  </span>
                ) : (
                  isRegistering ? 'Create account' : 'Sign in'
                )}
              </motion.button>
            </motion.div>
          </form>

          {/* Step 7: OR divider with lines drawing outward from center */}
          <motion.div
            {...stagger(7)}
            style={{
              display: 'flex',
              alignItems: 'center',
              margin: '22px 0 18px',
              gap: 14,
            }}
          >
            <motion.div
              initial={reducedMotion ? false : { scaleX: 0 }}
              animate={reducedMotion ? false : { scaleX: 1 }}
              transition={{ delay: reducedMotion ? 0 : 0.56, duration: 0.5, ease: 'easeOut' }}
              style={{
                flex: 1,
                height: 1,
                background: 'rgba(34, 211, 238, 0.3)',
                transformOrigin: 'right center',
              }}
            />
            <span
              style={{
                color: 'var(--text-soft)',
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
              }}
            >
              OR
            </span>
            <motion.div
              initial={reducedMotion ? false : { scaleX: 0 }}
              animate={reducedMotion ? false : { scaleX: 1 }}
              transition={{ delay: reducedMotion ? 0 : 0.56, duration: 0.5, ease: 'easeOut' }}
              style={{
                flex: 1,
                height: 1,
                background: 'rgba(34, 211, 238, 0.3)',
                transformOrigin: 'left center',
              }}
            />
          </motion.div>

          {/* Step 8: Sign in as guest button with cyan glow & fill from left */}
          <motion.div {...stagger(8)}>
            <button
              type="button"
              className="btn-secondary group"
              disabled={submitting}
              onClick={handleGuestSignIn}
              style={{
                position: 'relative',
                overflow: 'hidden',
                width: '100%',
                minHeight: 44,
                fontSize: 13,
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                borderRadius: 'var(--radius-sm)',
                background: 'rgba(255, 255, 255, 0.85)',
                borderColor: 'rgba(203, 213, 225, 0.8)',
                transition: 'border-color 0.25s ease, box-shadow 0.25s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = '#22d3ee'
                e.currentTarget.style.boxShadow = '0 0 16px rgba(34, 211, 238, 0.35)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'rgba(203, 213, 225, 0.8)'
                e.currentTarget.style.boxShadow = 'none'
              }}
            >
              <span
                aria-hidden="true"
                className="absolute inset-0 bg-gradient-to-r from-cyan-100/70 via-cyan-50/50 to-white/40 -translate-x-full group-hover:translate-x-0 transition-transform duration-300 ease-out origin-left pointer-events-none"
              />
              <span className="relative z-10">Sign in as guest</span>
            </button>
          </motion.div>

          {/* Step 9: Link with left-to-right animated underline on hover */}
          <motion.p
            {...stagger(9)}
            style={{
              margin: '22px 0 0',
              color: 'var(--text-soft)',
              textAlign: 'center',
              fontSize: 13,
            }}
          >
            {isRegistering ? 'Already have an account?' : 'New to NoteBot?'}{' '}
            <button
              type="button"
              className="group relative inline-block focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:outline-none rounded px-1"
              onClick={() => {
                setError('')
                setToastError('')
                setMode(isRegistering ? 'login' : 'register')
              }}
              style={{
                background: 'none',
                border: 0,
                padding: '0 4px',
                fontWeight: 600,
                color: 'var(--accent)',
                cursor: 'pointer',
              }}
            >
              <span>{isRegistering ? 'Sign in' : 'Create an account'}</span>
              <span
                aria-hidden="true"
                style={{
                  position: 'absolute',
                  bottom: 0,
                  left: 0,
                  width: '100%',
                  height: 2,
                  background: '#06b6d4',
                  transformOrigin: 'left',
                  transform: 'scaleX(0)',
                  transition: 'transform 0.25s ease-out',
                }}
                className="group-hover:scale-x-100"
              />
            </button>
          </motion.p>
        </motion.section>
      </div>
    </main>
  )
}

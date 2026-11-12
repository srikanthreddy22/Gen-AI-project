import React from 'react'
import { motion, useReducedMotion } from 'framer-motion'

export default function LogoIcon({ size = 28, className = '', style = {}, decorative = false, animated = false }) {
  const reducedMotion = useReducedMotion()
  const shouldAnimate = animated && !reducedMotion

  if (!shouldAnimate) {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 52 52"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={className}
        style={{ display: 'block', flexShrink: 0, ...style }}
        aria-hidden={decorative ? 'true' : undefined}
        aria-label={decorative ? undefined : 'NoteBot Logo'}
      >
        <rect x="2" y="2" width="48" height="48" rx="13" stroke="var(--coral)" strokeWidth="2" />
        <path d="M26 38c-6-3.5-11.8-4.1-17-2V20c6.2-2.2 11.6-1.3 17 2.8 5.4-4.1 10.8-5 17-2.8v16c-5.2-2.1-11-1.5-17 2Z"
          stroke="var(--ink)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M26 23v15M11 22c4.8-.9 9.5.2 13.2 3.2m16.8-3.2c-4.8-.9-9.5.2-13.2 3.2"
          stroke="var(--ink)" strokeWidth="1.8" strokeLinecap="round" />
        <circle cx="26" cy="12" r="2.8" fill="var(--saffron)" />
      </svg>
    )
  }

  return (
    <motion.div
      className={className}
      style={{ display: 'inline-block', flexShrink: 0, ...style }}
      aria-hidden={decorative ? 'true' : undefined}
      aria-label={decorative ? undefined : 'NoteBot Logo'}
      animate={{ scale: [1, 1.08, 1] }}
      transition={{ delay: 0.9, duration: 0.5, ease: 'easeInOut' }}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 52 52"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ display: 'block' }}
      >
        <motion.rect
          x="2"
          y="2"
          width="48"
          height="48"
          rx="13"
          stroke="var(--coral)"
          strokeWidth="2"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={{ duration: 0.65, ease: 'easeInOut' }}
        />
        <motion.path
          d="M26 38c-6-3.5-11.8-4.1-17-2V20c6.2-2.2 11.6-1.3 17 2.8 5.4-4.1 10.8-5 17-2.8v16c-5.2-2.1-11-1.5-17 2Z"
          stroke="var(--ink)"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={{ duration: 0.7, delay: 0.15, ease: 'easeInOut' }}
        />
        <motion.path
          d="M26 23v15M11 22c4.8-.9 9.5.2 13.2 3.2m16.8-3.2c-4.8-.9-9.5.2-13.2 3.2"
          stroke="var(--ink)"
          strokeWidth="1.8"
          strokeLinecap="round"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.35, ease: 'easeInOut' }}
        />
        <motion.circle
          cx="26"
          cy="12"
          r="2.8"
          fill="var(--saffron)"
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.3, delay: 0.65, ease: 'backOut' }}
        />
      </svg>
    </motion.div>
  )
}

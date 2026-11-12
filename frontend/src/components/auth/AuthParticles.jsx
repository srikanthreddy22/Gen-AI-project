import React, { useEffect, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'

const DESKTOP_PARTICLES = [
  { id: 1, x: 8, yStart: 85, size: 48, duration: 16, delay: 0, dx: 14, color: 'rgba(34, 211, 238, 0.22)', blur: 8 },
  { id: 2, x: 22, yStart: 95, size: 28, duration: 22, delay: 3, dx: -18, color: 'rgba(255, 255, 255, 0.32)', blur: 6 },
  { id: 3, x: 35, yStart: 80, size: 64, duration: 19, delay: 1, dx: 22, color: 'rgba(34, 211, 238, 0.18)', blur: 12 },
  { id: 4, x: 48, yStart: 90, size: 22, duration: 25, delay: 5, dx: -12, color: 'rgba(255, 255, 255, 0.28)', blur: 5 },
  { id: 5, x: 62, yStart: 88, size: 54, duration: 17, delay: 2, dx: 18, color: 'rgba(34, 211, 238, 0.24)', blur: 10 },
  { id: 6, x: 74, yStart: 94, size: 32, duration: 20, delay: 4, dx: -20, color: 'rgba(255, 255, 255, 0.35)', blur: 6 },
  { id: 7, x: 86, yStart: 82, size: 70, duration: 24, delay: 0.5, dx: 16, color: 'rgba(34, 211, 238, 0.20)', blur: 14 },
  { id: 8, x: 15, yStart: 75, size: 24, duration: 18, delay: 6, dx: -15, color: 'rgba(255, 255, 255, 0.25)', blur: 5 },
  { id: 9, x: 42, yStart: 70, size: 40, duration: 21, delay: 2.5, dx: 12, color: 'rgba(34, 211, 238, 0.22)', blur: 8 },
  { id: 10, x: 55, yStart: 78, size: 36, duration: 15, delay: 7, dx: -16, color: 'rgba(255, 255, 255, 0.30)', blur: 7 },
  { id: 11, x: 68, yStart: 72, size: 60, duration: 23, delay: 3.5, dx: 14, color: 'rgba(34, 211, 238, 0.16)', blur: 12 },
  { id: 12, x: 80, yStart: 86, size: 26, duration: 19, delay: 1.5, dx: -10, color: 'rgba(255, 255, 255, 0.26)', blur: 6 },
  { id: 13, x: 92, yStart: 76, size: 44, duration: 26, delay: 4.5, dx: 15, color: 'rgba(34, 211, 238, 0.25)', blur: 9 },
  { id: 14, x: 28, yStart: 84, size: 50, duration: 18, delay: 5.5, dx: -14, color: 'rgba(255, 255, 255, 0.22)', blur: 10 },
]

export default function AuthParticles() {
  const reducedMotion = useReducedMotion()
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 640)
    }
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])

  if (reducedMotion) {
    return null
  }

  const activeParticles = isMobile ? DESKTOP_PARTICLES.slice(0, 8) : DESKTOP_PARTICLES

  return (
    <div
      className="auth-particles"
      aria-hidden="true"
      style={{
        position: 'fixed',
        inset: 0,
        overflow: 'hidden',
        pointerEvents: 'none',
        zIndex: 2,
      }}
    >
      {activeParticles.map((particle) => (
        <motion.div
          key={particle.id}
          style={{
            position: 'absolute',
            left: `${particle.x}%`,
            top: `${particle.yStart}%`,
            width: particle.size,
            height: particle.size,
            borderRadius: '50%',
            background: particle.color,
            filter: `blur(${particle.blur}px)`,
            willChange: 'transform, opacity',
          }}
          animate={{
            y: [0, -window.innerHeight * 0.45, -window.innerHeight * 0.95],
            x: [0, particle.dx, 0],
            opacity: [0.15, 0.35, 0.15],
          }}
          transition={{
            duration: particle.duration,
            repeat: Infinity,
            ease: 'linear',
            delay: particle.delay,
          }}
        />
      ))}
    </div>
  )
}

import React, { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import Logo from '../brand/Logo'

const LINES = [
  { text: 'Photosynthesis turns light into chemical energy.', highlight: 'light into chemical energy.' },
  { text: 'Chlorophyll absorbs mostly blue and red light.', highlight: 'blue and red light.' },
  { text: 'Oxygen is released as a by-product.' },
  { text: 'Glucose stores the energy for the plant.', highlight: 'Glucose stores the energy' },
]
const INTRO_DURATION = 3400
const EXIT_DURATION = 500
const TYPE_INTERVAL = 35

function renderTypedLine(line, count, lineIndex) {
  const phrase = line.highlight
  if (!phrase) return line.text.slice(0, count)
  const start = line.text.indexOf(phrase)
  if (start < 0 || count <= start) return line.text.slice(0, count)
  const before = line.text.slice(0, start)
  const throughPhrase = Math.min(phrase.length, count - start)
  const afterStart = start + phrase.length
  return (
    <>
      {before}
      <span className={`preloader-highlight preloader-highlight-${lineIndex}`}>
        {phrase.slice(0, throughPhrase)}
      </span>
      {count > afterStart && line.text.slice(afterStart, count)}
    </>
  )
}

export default function Preloader({ onDone }) {
  const reduceMotion = useReducedMotion()
  const [visible, setVisible] = useState(true)
  const [showSummary, setShowSummary] = useState(Boolean(reduceMotion))
  const [exiting, setExiting] = useState(false)
  const [typedCounts, setTypedCounts] = useState(() => LINES.map(() => 0))
  const completed = useRef(false)
  const timers = useRef([])

  useEffect(() => {
    let interval
    const clearTimers = () => {
      timers.current.forEach(clearTimeout)
      timers.current = []
      if (interval) clearInterval(interval)
    }
    const finish = (skip = false) => {
      if (completed.current) return
      completed.current = true
      clearTimers()
      if (skip) setShowSummary(true)
      setExiting(true)
      timers.current.push(setTimeout(() => {
        setVisible(false)
        onDone?.()
      }, reduceMotion ? 0 : EXIT_DURATION))
    }
    const onKeyDown = () => finish(true)
    const onPointerDown = () => finish(true)

    if (reduceMotion) {
      setShowSummary(true)
      timers.current.push(setTimeout(() => finish(), 700))
    } else {
      interval = setInterval(() => {
        setTypedCounts((current) => current.map((count, index) => (
          Math.min(LINES[index].text.length, count + 1)
        )))
      }, TYPE_INTERVAL)
      timers.current.push(setTimeout(() => setShowSummary(true), 2200))
      timers.current.push(setTimeout(() => finish(), INTRO_DURATION))
      timers.current.push(setTimeout(() => finish(true), 6000))
    }
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('pointerdown', onPointerDown)

    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('pointerdown', onPointerDown)
      clearTimers()
    }
  }, [onDone, reduceMotion])

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className="preloader-overlay"
          initial={{ opacity: 1 }}
          animate={{ opacity: exiting ? 0 : 1 }}
          transition={{ duration: reduceMotion ? 0 : EXIT_DURATION / 1000, ease: 'easeOut' }}
          aria-label="NoteBot introduction"
          role="status"
        >
          <div className="preloader-stage">
            <AnimatePresence mode="wait">
              {!showSummary ? (
                <motion.section
                  key="notes"
                  className="preloader-notes"
                  initial={reduceMotion ? false : { opacity: 0, y: 18, rotate: -2 }}
                  animate={{ opacity: 1, y: 0, rotate: -1 }}
                  exit={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.76, rotate: 0, y: -8 }}
                  transition={{ duration: reduceMotion ? 0 : 0.6, ease: 'easeOut' }}
                  aria-label="Study notes preview"
                >
                  <div className="preloader-note-lines">
                    {LINES.map((line, index) => (
                      <p className="preloader-note-line" key={line.text}>
                        {renderTypedLine(line, typedCounts[index], index)}
                      </p>
                    ))}
                  </div>
                  {!reduceMotion && (
                    <>
                      <motion.span
                        className="preloader-sparkle"
                        aria-hidden="true"
                        animate={{ x: [0, 170, 260, 100], y: [0, 8, 24, 42] }}
                        transition={{ duration: 1.6, delay: 0.7, ease: 'easeInOut' }}
                      >✦</motion.span>
                      <div className="preloader-chips" aria-hidden="true">
                        {['Key idea', 'Definition', 'Example'].map((label, index) => (
                          <motion.span
                            className={`preloader-chip preloader-chip-${index}`}
                            key={label}
                            initial={{ opacity: 0, y: 12 }}
                            animate={{ opacity: [0, 1, 1, 0], y: [12, 0, 0, -60], scale: [0.85, 1, 1, 0.6] }}
                            transition={{ delay: 1.6 + index * 0.1, duration: 0.9, times: [0, 0.3, 0.65, 1] }}
                          >{label}</motion.span>
                        ))}
                      </div>
                    </>
                  )}
                </motion.section>
              ) : (
                <motion.section
                  key="summary"
                  className="preloader-summary-card"
                  initial={reduceMotion ? { opacity: 1 } : { opacity: 0, y: 8, scale: 0.92 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ duration: reduceMotion ? 0 : 0.45, ease: 'easeOut' }}
                >
                  <p>Light becomes glucose. Oxygen is the by-product.</p>
                </motion.section>
              )}
            </AnimatePresence>
            <motion.div
              className="preloader-brand"
              initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
              animate={{ opacity: showSummary ? 1 : 0, y: showSummary ? 0 : 8 }}
              transition={{ duration: reduceMotion ? 0 : 0.45, delay: reduceMotion ? 0 : 0.35 }}
            >
              <span className="preloader-logo-mark"><Logo markOnly size={48} /></span>
              <span className="preloader-brand-copy">
                <span>NoteBot</span>
                <small>Study notes</small>
              </span>
            </motion.div>
          </div>
          <div className="preloader-progress" aria-hidden="true">
            <motion.div
              className="preloader-progress-fill"
              initial={{ scaleX: 0 }}
              animate={{ scaleX: exiting || reduceMotion ? 1 : showSummary ? 0.82 : 0.32 }}
              transition={{ duration: reduceMotion ? 0 : 0.5, ease: 'easeOut' }}
            />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

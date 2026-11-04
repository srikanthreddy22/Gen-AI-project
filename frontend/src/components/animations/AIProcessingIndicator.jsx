import React from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { Sparkles } from 'lucide-react'

export default function AIProcessingIndicator({ message, progress }) {
  const reduceMotion = useReducedMotion()
  const hasProgress = Number.isFinite(progress)

  return (
    <div className="ai-processing" role="status" aria-live="polite">
      <motion.span
        className="ai-processing-icon"
        animate={reduceMotion ? undefined : { rotate: [0, 12, -12, 0], scale: [1, 1.06, 1] }}
        transition={reduceMotion ? undefined : { duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
        aria-hidden="true"
      >
        <Sparkles size={23} />
      </motion.span>
      <span className="ai-processing-copy">
        <span className="ai-processing-message">{message}</span>
        {hasProgress && <span className="ai-processing-upload">Upload progress: {progress}%</span>}
      </span>
      <span className="ai-processing-dots" aria-hidden="true"><i /><i /><i /></span>
    </div>
  )
}

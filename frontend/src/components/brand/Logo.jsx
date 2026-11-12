import React from 'react'
import LogoIcon from '../layout/LogoIcon'

export default function Logo({ markOnly = false, size = 42, className = '', animated = false }) {
  if (markOnly) {
    return <LogoIcon size={size} className={className} animated={animated} decorative />
  }

  return (
    <div className={`brand-lockup ${className}`.trim()}>
      <LogoIcon size={size} animated={animated} decorative />
      <span className="brand-lockup-copy">
        <span className="brand-lockup-name" style={{ color: '#F8FAFC' }}>NoteBot</span>
        <span className="brand-lockup-caption" style={{ color: '#CBD5E1' }}>Study notes</span>
      </span>
    </div>
  )
}

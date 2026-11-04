import React from 'react'
import LogoIcon from '../layout/LogoIcon'

export default function Logo({ markOnly = false, size = 42, className = '' }) {
  if (markOnly) {
    return <LogoIcon size={size} className={className} decorative />
  }

  return (
    <div className={`brand-lockup ${className}`.trim()}>
      <LogoIcon size={size} decorative />
      <span className="brand-lockup-copy">
        <span className="brand-lockup-name">NoteBot</span>
        <span className="brand-lockup-caption">Study notes</span>
      </span>
    </div>
  )
}

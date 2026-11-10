import React from 'react'

export default function LogoIcon({ size = 28, className = '', style = {}, decorative = false }) {
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

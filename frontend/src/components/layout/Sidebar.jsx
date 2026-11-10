import React, { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useNoteStore } from '../../store/noteStore'
import { checkHealth } from '../../utils/api'
import Logo from '../brand/Logo'

const NAV = [
  {
    id: 'summarize', label: 'Workspace', sub: 'Summarize & analyze',
    color: 'var(--accent)', tint: 'var(--accent-15)',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>
      </svg>
    ),
  },
  {
    id: 'flashcards', label: 'Flashcards', sub: 'Smart review', badge: '12',
    color: 'var(--accent)', tint: 'var(--accent-15)',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="6" width="20" height="13" rx="2"/><path d="M6 6V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v2"/>
      </svg>
    ),
  },
  {
    id: 'quiz', label: 'Knowledge', sub: 'Test yourself',
    color: 'var(--accent)', tint: 'var(--accent-15)',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
      </svg>
    ),
  },
  {
    id: 'chat', label: 'Chat', sub: 'Ask your document',
    color: 'var(--accent)', tint: 'var(--accent-15)',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5z"/>
      </svg>
    ),
  },
]

export default function Sidebar() {
  const { activeView, setActiveView, flashcards } = useNoteStore()
  const [backendOnline, setBackendOnline] = useState(null)

  useEffect(() => {
    let active = true
    let timeoutId
    const pollHealth = async () => {
      try {
        await checkHealth()
        if (active) setBackendOnline(true)
      } catch {
        if (active) setBackendOnline(false)
      } finally {
        if (active) timeoutId = setTimeout(pollHealth, 10000)
      }
    }

    pollHealth()
    return () => {
      active = false
      clearTimeout(timeoutId)
    }
  }, [])

  return (
    <motion.aside
      initial={{ x: -50, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
      className="surface app-sidebar"
      style={{ width: 230, flexShrink: 0, height: '100vh', display: 'flex', flexDirection: 'column', position: 'relative', zIndex: 20 }}
    >
      {/* ── Logo ── */}
      <div className="sidebar-brand" style={{ padding: '22px 20px 18px', borderBottom: '1px solid var(--line)' }}>
        <div className="sidebar-brand-content">
          <Logo className="sidebar-logo" />

          {/* Backend status */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
            <div style={{
              width: 7, height: 7, clipPath: 'circle(50%)',
              background: backendOnline === true ? 'var(--success)' : backendOnline === false ? 'var(--danger)' : 'var(--warn)',
            }} title={backendOnline === true ? 'Live NLP' : 'Connecting...'}/>
            <span className="sidebar-status" aria-live="polite" style={{ fontSize: 8, color: 'var(--paper-dim)', letterSpacing: '0.02em' }}>
              {backendOnline === true ? 'Backend online' : backendOnline === false ? 'Backend offline' : 'Checking backend'}
            </span>
          </div>
        </div>
      </div>

      {/* ── Nav ── */}
      <nav className="sidebar-nav" style={{ flex: 1, padding: '12px 10px', display: 'flex', flexDirection: 'column', gap: 3 }}>
        {NAV.map((item, i) => {
          const active = activeView === item.id
          const cardCount = item.id === 'flashcards' ? flashcards.length : null
          return (
            <motion.button
              key={item.id}
              aria-label={item.label}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.08 + 0.18, ease: [0.16, 1, 0.3, 1] }}
              onClick={() => setActiveView(item.id)}
              whileHover={!active ? { x: 4 } : {}}
              whileTap={{ scale: 0.98 }}
              style={{
                display: 'flex', alignItems: 'center', gap: 12,
                width: '100%', padding: '10px 12px',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer', textAlign: 'left',
                position: 'relative',
                background: 'transparent',
                border: 'none',
              }}
            >
              {/* Active background */}
              {active && (
                <motion.div
                  layoutId="nav-bg"
                  style={{
                    position: 'absolute', inset: 0, borderRadius: 'var(--radius-sm)',
                    pointerEvents: 'none',
                    background: item.tint,
                    border: '1px solid var(--accent-30)',
                    boxShadow: '0 0 18px var(--glow)',
                  }}
                />
              )}
              {/* Icon */}
              <div style={{
                position: 'relative', zIndex: 1,
                width: 34, height: 34, borderRadius: 'var(--radius-sm)',
                display: 'flex', alignItems: 'center', justifycontent: 'center',
                flexShrink: 0,
                background: item.tint,
                color: item.color,
                boxShadow: 'none',
                transition: 'all 0.2s',
                justifyContent: 'center',
              }}>
                {item.icon}
              </div>

              {/* Label */}
              <div className="sidebar-label" style={{ flex: 1, minWidth: 0, position: 'relative', zIndex: 1 }}>
                <div style={{
                  fontSize: 13, fontWeight: 500, lineHeight: '1.1',
                  marginBottom: 2,
                  color: active ? 'var(--ink)' : 'var(--ink-soft)',
                  transition: 'color 0.15s',
                }}>{item.label}</div>
                <div className="sidebar-sub" style={{ fontSize: 10, color: active ? 'var(--ink)' : 'var(--ink-soft)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.sub}</div>
              </div>

              {/* Badge */}
              {cardCount > 0 && (
                <span style={{
                  position: 'relative', zIndex: 1,
                  fontSize: 10, fontWeight: 700, fontFamily: "'IBM Plex Mono',monospace",
                  padding: '2px 7px', borderRadius: 'var(--radius-sm)',
                  background: 'var(--accent-14)',
                  color: 'var(--accent)',
                  border: '1px solid var(--accent-30)',
                }}>{cardCount}</span>
              )}
            </motion.button>
          )
        })}
      </nav>

    </motion.aside>
  )
}

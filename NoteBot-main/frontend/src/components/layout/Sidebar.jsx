import React, { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useNoteStore } from '../../store/noteStore'
import api from '../../utils/api'

const NAV = [
  {
    id: 'summarize', label: 'Workspace', sub: 'Summarize & analyze',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>
      </svg>
    ),
  },
  {
    id: 'flashcards', label: 'Flashcards', sub: 'Smart review', badge: '12',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="6" width="20" height="13" rx="2"/><path d="M6 6V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v2"/>
      </svg>
    ),
  },
  {
    id: 'quiz', label: 'Knowledge', sub: 'Test yourself',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
      </svg>
    ),
  },
]

export default function Sidebar() {
  const { activeView, setActiveView, flashcards } = useNoteStore()
  const [backendOnline, setBackendOnline] = useState(null)

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await api.get('/health')
        if (res.data && res.data.status === 'ok') {
          setBackendOnline(true)
        } else {
          setBackendOnline(false)
        }
      } catch (err) {
        setBackendOnline(false)
      }
    }

    checkHealth()
    const interval = setInterval(checkHealth, 10000)
    return () => clearInterval(interval)
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
      <div className="sidebar-brand" style={{ padding: '22px 20px 18px', borderBottom: '1px solid rgba(239,229,207,0.08)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <motion.div
            whileHover={{ scale: 1.08, rotate: 6 }}
            transition={{ type: 'spring', stiffness: 380, damping: 20 }}
            style={{ flexShrink: 0, cursor: 'pointer', position: 'relative' }}
          >
            <div style={{
              width: 42, height: 42, borderRadius: 14,
              background: 'var(--ink-2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              position: 'relative',
              border: '1px solid rgba(201,160,99,0.35)',
            }}>
              <div style={{ position: 'absolute', inset: 3, borderRadius: 10, border: '1px solid rgba(255,255,255,0.12)' }}/>
              <span className="sidebar-badge" style={{
                fontFamily: "'Newsreader',serif",
                fontSize: 22, fontWeight: 500, color: 'var(--brass)',
                lineHeight: 1, position: 'relative',
              }}>N</span>
            </div>
          </motion.div>

          <div className="sidebar-copy" style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontFamily: "'Newsreader',serif",
              fontSize: 20, fontWeight: 500, color: 'var(--paper)',
              letterSpacing: '-0.03em', lineHeight: 1, marginBottom: 3,
            }}>NoteBot</div>
            <div style={{
              fontSize: 10, fontWeight: 500, color: 'var(--paper-dim)',
              letterSpacing: '0.02em',
            }}>Study notes</div>
          </div>

          {/* Backend status */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
            <div style={{
              width: 7, height: 7, borderRadius: '50%',
              background: backendOnline === true ? 'var(--sage)' : backendOnline === false ? 'var(--oxblood)' : 'var(--brass)',
            }} title={backendOnline === true ? 'Live NLP' : 'Connecting...'}/>
            <span className="sidebar-status" style={{ fontSize: 8, color: 'var(--paper-dim)', letterSpacing: '0.02em' }}>
              {backendOnline === true ? 'live' : backendOnline === false ? 'down' : 'wait'}
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
                borderRadius: 14,
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
                    position: 'absolute', inset: 0, borderRadius: 14,
                    background: 'rgba(201,160,99,0.12)',
                    border: '1px solid rgba(201,160,99,0.24)',
                    boxShadow: 'inset 0 1px 0 rgba(239,229,207,0.04)',
                  }}
                />
              )}
              {/* Active left bar */}
              {active && (
                <motion.div
                  layoutId="nav-bar"
                  style={{
                    position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)',
                    width: 3, height: 24, borderRadius: '0 4px 4px 0',
                    background: 'var(--brass)',
                  }}
                />
              )}

              {/* Icon */}
              <div style={{
                position: 'relative', zIndex: 1,
                width: 34, height: 34, borderRadius: 10,
                display: 'flex', alignItems: 'center', justifycontent: 'center',
                flexShrink: 0,
                background: active ? 'rgba(201,160,99,0.12)' : 'rgba(239,229,207,0.04)',
                color: active ? 'var(--brass)' : 'var(--paper-dim)',
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
                  color: active ? 'var(--paper)' : 'var(--paper-dim)',
                  transition: 'color 0.15s',
                }}>{item.label}</div>
                <div className="sidebar-sub" style={{ fontSize: 10, color: 'var(--paper-dim)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.sub}</div>
              </div>

              {/* Badge */}
              {cardCount > 0 && (
                <span style={{
                  position: 'relative', zIndex: 1,
                  fontSize: 10, fontWeight: 700, fontFamily: "'IBM Plex Mono',monospace",
                  padding: '2px 7px', borderRadius: 99,
                  background: 'rgba(201,160,99,0.12)',
                  color: 'var(--brass)',
                  border: '1px solid rgba(201,160,99,0.28)',
                }}>{cardCount}</span>
              )}
            </motion.button>
          )
        })}
      </nav>

      {/* ── Settings ── */}
      <div className="sidebar-settings" style={{ padding: '12px 10px 20px', borderTop: '1px solid rgba(239,229,207,0.08)' }}>
        <button style={{
          display: 'flex', alignItems: 'center', gap: 10,
          width: '100%', padding: '9px 12px', borderRadius: 12,
          background: 'transparent', border: 'none', cursor: 'pointer',
          color: 'var(--paper-dim)', fontSize: 12, fontWeight: 400,
          transition: 'all 0.15s',
        }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(239,229,207,0.04)'; e.currentTarget.style.color = 'var(--paper)' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--paper-dim)' }}
          aria-label="Settings"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
          <span className="sidebar-settings-label">Settings</span>
        </button>
      </div>
    </motion.aside>
  )
}

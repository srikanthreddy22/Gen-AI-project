import React, { useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { useNoteStore } from '../../store/noteStore'
import { exportPDF, downloadBlob } from '../../utils/api'
import toast from 'react-hot-toast'

const TITLES = {
  summarize: 'Workspace',
  flashcards: 'Flashcards',
  quiz: 'Knowledge',
  chat: 'Chat',
}

export default function Topbar({ user, onLogout }) {
  const store = useNoteStore()
  const [exporting, setExporting] = useState(false)
  const exportInProgress = useRef(false)

  const handleExport = async () => {
    if (!store.result) {
      toast.error('Generate a summary first!')
      return
    }
    if (exportInProgress.current) return
    exportInProgress.current = true
    setExporting(true)
    const tid = toast.loading('Generating styled PDF…')
    try {
      const title = store.uploadedFile ? store.uploadedFile.name.replace(/\.[^/.]+$/, "") : 'NoteBot Summary'
      const res = await exportPDF({
        title: title,
        bullets: store.result.bullets,
        keywords: store.result.keywords,
        stats: store.result.stats,
        flashcards: store.flashcards,
        quiz: store.quizQuestions,
      })
      downloadBlob(res.data, `notebot-${title.toLowerCase().replace(/\s+/g, '-')}.pdf`)
      toast.success('PDF saved!', { id: tid })
    } catch (err) {
      const msg = err?.response?.data?.error || 'Export failed — is backend running?'
      toast.error(msg, { id: tid })
    } finally {
      exportInProgress.current = false
      setExporting(false)
    }
  }

  const handleCopy = async () => {
    if (!store.result) return
    const text = store.result.bullets.map((bullet) => `• ${bullet.text || bullet}`).join('\n')
    try {
      await navigator.clipboard.writeText(text)
      toast.success('Insights copied')
    } catch (error) {
      console.error('Could not copy the study insights:', error)
      toast.error('Could not copy insights to the clipboard')
    }
  }

  const title = store.result && store.uploadedFile
    ? store.uploadedFile.name
    : TITLES[store.activeView] || 'NoteBot'

  return (
    <motion.div
      className="app-topbar"
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.38, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
      style={{
        height: 60, display: 'flex', alignItems: 'center',
        padding: '0 24px', gap: 16, flexShrink: 0,
        position: 'relative', zIndex: 10,
      }}
    >
      {/* Breadcrumb */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <p className="topbar-breadcrumb">
          <span>NoteBot</span><span aria-hidden="true">/</span><span>{title}</span>
        </p>
        {store.uploadedFile && store.activeView === 'summarize' && !store.result && (
          <motion.p
            initial={{ opacity: 0, y: 3 }} animate={{ opacity: 1, y: 0 }}
            style={{ fontSize: 11, color: 'var(--ink)', marginTop: 2, letterSpacing: '0.02em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
          >
            {store.uploadedFile.name}
          </motion.p>
        )}
      </div>

      {/* Model pill */}
      {store.result && store.activeView === 'summarize' && (
        <motion.div
          initial={{ opacity: 0, scale: 0.88 }} animate={{ opacity: 1, scale: 1 }}
          className="topbar-model"
          style={{
            display: 'flex', alignItems: 'center', gap: 7,
            padding: '5px 12px', borderRadius: 'var(--radius-sm)',
            background: 'var(--paper)',
            border: '1px solid var(--line)',
            fontSize: 11, fontFamily: "'IBM Plex Mono',monospace",
            color: 'var(--ink)',
          }}
        >
          <div style={{
            width: 6, height: 6, clipPath: 'circle(50%)',
            background: 'var(--success)',
          }}/>
          {store.result.stats?.model || 'AI Model'}
        </motion.div>
      )}

      {/* Export / Reset buttons */}
      <div className="topbar-actions" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {user && (
          <>
            <span title={user.email} style={{ maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-soft)', fontSize: 11 }}>
              {user.username}
            </span>
            <button type="button" className="btn-secondary topbar-action" onClick={onLogout} style={{ padding: '8px 12px', fontSize: 12 }}>
              Sign out
            </button>
          </>
        )}
        {store.result && store.activeView === 'summarize' && (
          <>
            <motion.button
              type="button"
              whileHover={{ y: -2 }} whileTap={{ scale: 0.97 }}
              onClick={handleCopy}
              className="btn-secondary topbar-action"
              style={{ padding: '8px 14px', fontSize: 12 }}
            >
              Copy all
            </motion.button>
            <motion.button
              type="button"
              data-export-pdf
              whileHover={{ y: -2 }} whileTap={{ scale: 0.97 }}
              onClick={handleExport}
              disabled={exporting}
              className="btn-primary topbar-action"
              style={{ padding: '8px 14px', borderRadius: 'var(--radius-sm)', fontSize: 12, fontWeight: 700 }}
            >
              {exporting ? 'Exporting...' : 'Export PDF'}
            </motion.button>
          </>
        )}
      </div>
    </motion.div>
  )
}

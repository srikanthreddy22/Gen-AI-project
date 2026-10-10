import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useDropzone } from 'react-dropzone'
import toast from 'react-hot-toast'
import { summarizeText, uploadPDF, indexText, getFlashcards, getQuiz } from '../utils/api'
import { useNoteStore } from '../store/noteStore'

const LOADING_MESSAGES = [
  "Initializing NLP pipelines…",
  "Executing BART summarizer transformer…",
  "Resolving linguistic syntax with spaCy…",
  "Calibrating keyword weights via TF-IDF…",
  "Extracting Spaced Repetition flashcards…",
  "Composing conceptual knowledge assessments…",
  "Polishing your study intelligence report…",
]

export default function SummarizePage() {
  const store = useNoteStore()
  const [loadingMsgIdx, setLoadingMsgIdx] = useState(0)
  const [inputType, setInputType] = useState('upload') // 'upload' | 'paste'
  const [pastedText, setPastedText] = useState('')

  useEffect(() => {
    let interval
    if (store.isProcessing) {
      interval = setInterval(() => {
        setLoadingMsgIdx(i => (i + 1) % LOADING_MESSAGES.length)
      }, 2000)
    } else {
      setLoadingMsgIdx(0)
    }
    return () => clearInterval(interval)
  }, [store.isProcessing])

  const processContent = async (text, file = null, docId = null) => {
    store.setProcessing(true)
    if (file) store.setUploadedFile(file)
    store.setDocumentId(docId)
    store.setResult(null)
    store.setFlashcards([])
    store.setQuizQuestions([])
    try {
      let activeDocId = docId
      if (!activeDocId) {
        const indexRes = await indexText(text)
        activeDocId = indexRes.data?.doc_id
        if (!activeDocId || !indexRes.data?.indexed) {
          throw new Error('The pasted text could not be indexed for study content generation.')
        }
        store.setDocumentId(activeDocId)
      }

      const [summaryResult, flashcardsResult, quizResult] = await Promise.allSettled([
        summarizeText(text, { bulletCount: 8, method: 'bart' }),
        getFlashcards(activeDocId, 10),
        getQuiz(activeDocId, 5),
      ])

      if (summaryResult.status === 'fulfilled') {
        store.setResult(summaryResult.value.data)
      } else {
        const error = summaryResult.reason
        toast.error(`Summarization failed: ${error?.response?.data?.error || error?.message || 'Please try again.'}`)
      }

      if (flashcardsResult.status === 'fulfilled' && flashcardsResult.value.data.flashcards) {
        store.setFlashcards(flashcardsResult.value.data.flashcards)
      } else {
        toast.error(`Flashcard generation failed: ${flashcardsResult.reason?.response?.data?.error || flashcardsResult.reason?.message || 'Please try again.'}`)
      }

      if (quizResult.status === 'fulfilled' && quizResult.value.data.questions) {
        store.setQuizQuestions(quizResult.value.data.questions)
      } else {
        toast.error(`Quiz generation failed: ${quizResult.reason?.response?.data?.error || quizResult.reason?.message || 'Please try again.'}`)
      }

      if (
        summaryResult.status === 'fulfilled' &&
        flashcardsResult.status === 'fulfilled' &&
        quizResult.status === 'fulfilled'
      ) {
        toast.success('Document analysis complete')
      }
    } catch (err) {
      console.error("Processing error:", err)
      const msg = err.response?.data?.error || err.message || 'Summarization error occurred'
      toast.error(msg.includes('Network Error') ? 'Server connection failed' : msg)
    } finally {
      store.setProcessing(false)
    }
  }

  const onDrop = async (acceptedFiles) => {
    const file = acceptedFiles[0]
    if (!file) return
    if (file.size === 0) return toast.error('File is empty')

    store.setProcessing(true)
    try {
      const res = await uploadPDF(file)
      const activeDocId = res.data?.doc_id
      if (!activeDocId || !res.data?.indexed) {
        throw new Error('The uploaded document could not be indexed for study content generation.')
      }
      toast.success('Document uploaded successfully')
      await processContent(res.data.text, file, activeDocId)
    } catch (err) {
      store.setProcessing(false)
      const msg = err.response?.data?.error || err.message || 'Text extraction failed'
      toast.error(msg.includes('Network Error') ? 'Server connection failed' : msg)
    }
  }

  const onDropRejected = (fileRejections) => {
    const rejection = fileRejections[0]
    if (!rejection) return
    const error = rejection.errors[0]
    if (error.code === 'file-invalid-type') toast.error('Unsupported file type. Please upload PDF or TXT.')
    else if (error.code === 'file-too-large') toast.error('File is too large. Max size is 32MB.')
    else toast.error('Invalid file upload: ' + error.message)
  }

  const handlePasteSubmit = () => {
    const trimmed = pastedText.trim()
    if (trimmed.length === 0) return toast.error('Text field is empty')
    if (trimmed.length < 30) return toast.error('Please paste at least 30 characters of text.')
    processContent(trimmed)
  }

  const handleTextPaste = (event) => {
    const pasted = event.clipboardData.getData('text')
    if (!pasted) return

    const textarea = event.currentTarget
    const nextText = pastedText.slice(0, textarea.selectionStart) + pasted + pastedText.slice(textarea.selectionEnd)
    event.preventDefault()
    setPastedText(nextText)

    const trimmed = nextText.trim()
    if (trimmed.length >= 30) processContent(trimmed)
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, onDropRejected,
    accept: { 'application/pdf': ['.pdf'], 'text/plain': ['.txt'] },
    maxFiles: 1, maxSize: 32 * 1024 * 1024
  })

  return (
    <div className="w-full h-full p-8 overflow-y-auto custom-scrollbar relative scroll-smooth flex flex-col">
      <AnimatePresence mode="wait">
        
        {/* ── 1. INITIAL WORKSPACE VIEW ── */}
        {!store.result && !store.isProcessing && (
          <motion.div
            key="input"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
            className="max-w-7xl mx-auto w-full pb-20 flex-1 flex flex-col justify-center"
          >
            {/* Editorial Hero Header */}
            <div className="workspace-hero flex justify-between items-end mb-10">
              <div>
                <motion.div
                  initial={{ opacity: 0, x: -25 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.1 }}
                  className="flex items-center gap-2 text-violet font-medium mb-3 tracking-wide text-xs uppercase"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                  </svg>
                  Premium Study Intelligence
                </motion.div>
                <h1 className="text-6xl font-semibold tracking-tight text-zinc-100 leading-[1.05] font-display">
                  Process raw research. <br />
                  <span className="text-transparent bg-clip-text bg-gradient-to-r from-white via-violet-soft to-rose">Generate understanding.</span>
                </h1>
              </div>

              <motion.button
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.2 }}
                onClick={store.loadDemo}
                className="btn-secondary"
                style={{ padding: '10px 22px', borderRadius: 99, fontSize: 13 }}
              >
                Load NLP Demo
              </motion.button>
            </div>

            <div className="workspace-grid grid grid-cols-12 gap-8">
              {/* Core Input Panel */}
              <div className="col-span-12 lg:col-span-8 flex flex-col">
                <div className="surface rounded-[32px] p-8 relative overflow-hidden group flex flex-col h-full min-h-[420px]">
                  {/* Header Row */}
                  <div className="workspace-panel-header flex justify-between items-center mb-8 relative z-10">
                    <h3 className="text-xl font-semibold text-zinc-100 flex items-center gap-3">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--brass)" strokeWidth="2.5">
                        <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>
                      </svg>
                      Initialize Workspace
                    </h3>

                    {/* Input Mode Selector */}
                    <div className="source-tabs flex bg-white/5 border border-white/10 p-1 rounded-full relative">
                      <div className="flex z-10 relative w-full">
                        <button
                          type="button"
                          aria-pressed={inputType === 'upload'}
                          onClick={() => setInputType('upload')}
                          className={`flex-1 items-center gap-2 px-5 py-2 rounded-full text-xs font-semibold tracking-wide uppercase transition-colors ${inputType === 'upload' ? 'text-zinc-100' : 'text-zinc-400 hover:text-zinc-200'}`}
                        >
                          Upload File
                        </button>
                        <button
                          type="button"
                          aria-pressed={inputType === 'paste'}
                          onClick={() => setInputType('paste')}
                          className={`flex-1 items-center gap-2 px-5 py-2 rounded-full text-xs font-semibold tracking-wide uppercase transition-colors ${inputType === 'paste' ? 'text-zinc-100' : 'text-zinc-400 hover:text-zinc-200'}`}
                        >
                          Paste Text
                        </button>
                      </div>
                      <motion.div
                        className="source-tab-marker absolute top-1 bottom-1 rounded-full"
                        initial={false}
                        animate={{ left: inputType === 'upload' ? '4px' : '50%', width: 'calc(50% - 4px)' }}
                        transition={{ type: 'spring', stiffness: 380, damping: 28 }}
                        style={{ background: 'var(--brass)' }}
                      />
                    </div>
                  </div>

                  {/* Body Content */}
                  <div className="flex-1 flex flex-col relative z-10">
                    <AnimatePresence mode="wait">
                      {inputType === 'upload' ? (
                        <motion.div
                          key="upload-zone"
                          initial={{ opacity: 0, scale: 0.98 }}
                          animate={{ opacity: 1, scale: 1 }}
                          exit={{ opacity: 0, scale: 0.98 }}
                          transition={{ duration: 0.2 }}
                          {...getRootProps()}
                          className={`surface w-full flex-1 min-h-[300px] rounded-3xl border border-dashed transition-all duration-300 cursor-pointer flex flex-col items-center justify-center gap-5 ${isDragActive ? 'border-violet shadow-[inset_0_0_40px_rgba(124,58,237,0.12)] bg-violet/5' : 'border-white/10 hover:border-violet/40 hover:bg-white/[0.01]'}`}
                        >
                          <input {...getInputProps()} />
                          <motion.div
                            whileHover={{ scale: 1.08, y: -2 }}
                            style={{
                              width: 68, height: 68, borderRadius: 20,
                              background: 'rgba(201,160,99,0.12)',
                              border: '1px solid rgba(201,160,99,0.24)',
                              display: 'flex', alignItems: 'center', justifyContent: 'center',
                              boxShadow: 'none',
                            }}
                          >
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--brass)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
                            </svg>
                          </motion.div>
                          <div className="text-center">
                            <p className="text-zinc-200 font-medium text-lg mb-1">Drag and drop file here</p>
                            <p className="text-zinc-500 text-xs tracking-wide uppercase">Supports PDF or TXT up to 32MB</p>
                          </div>
                        </motion.div>
                      ) : (
                        <motion.div
                          key="paste-zone"
                          initial={{ opacity: 0, scale: 0.98 }}
                          animate={{ opacity: 1, scale: 1 }}
                          exit={{ opacity: 0, scale: 0.98 }}
                          transition={{ duration: 0.2 }}
                          className="w-full flex-1 flex flex-col"
                        >
                          <textarea
                            value={pastedText}
                            onChange={e => setPastedText(e.target.value)}
                            onPaste={handleTextPaste}
                            placeholder="Paste text contents for deep intelligence processing…"
                            className="w-full flex-1 min-h-[250px] input-zone rounded-3xl p-6 text-zinc-200 placeholder-zinc-600 resize-none focus:outline-none"
                            style={{ fontSize: 14, lineHeight: '1.6' }}
                          />
                          <div className="mt-5 flex justify-between items-center">
                            <span className="font-mono text-xs text-zinc-500">{pastedText.length} characters · paste 30+ characters to start automatically</span>
                            <motion.button
                              whileHover={{ scale: 1.02 }}
                              whileTap={{ scale: 0.98 }}
                              onClick={handlePasteSubmit}
                              className="btn-primary"
                              style={{ padding: '12px 28px', borderRadius: 99, fontSize: 13 }}
                            >
                              Process Text
                            </motion.button>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>
              </div>

              {/* Side Panels */}
              <div className="col-span-12 lg:col-span-4 flex flex-col gap-6">
                {/* Processing Info */}
                <div className="surface rounded-[32px] p-6 hover:translate-y-[-2px] transition-transform duration-300">
                  <div className="flex items-center gap-3 mb-5">
                    <div style={{
                      width: 36, height: 36, borderRadius: 10,
                      background: 'rgba(201,160,99,0.1)',
                      border: '1px solid rgba(201,160,99,0.2)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--brass)" strokeWidth="2.2">
                        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                      </svg>
                    </div>
                    <h4 className="text-zinc-200 font-semibold text-[15px]">Advanced Pipeline</h4>
                  </div>
                  <p className="text-zinc-400 text-xs leading-relaxed mb-4">
                    Our platform automatically processes raw material with a structured pipeline:
                  </p>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-zinc-500">Synthesizer Model</span>
                      <span className="text-zinc-300 font-mono">BART-Large-CNN</span>
                    </div>
                    <div className="h-[1px] bg-white/5 w-full"/>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-zinc-500">Linguistic Parser</span>
                      <span className="text-zinc-300 font-mono">spaCy pipeline</span>
                    </div>
                  </div>
                </div>

                {/* Features list */}
                <div className="surface rounded-[32px] p-6 hover:translate-y-[-2px] transition-transform duration-300 flex-1">
                  <div className="flex items-center gap-3 mb-5">
                    <div style={{
                      width: 36, height: 36, borderRadius: 10,
                      background: 'rgba(16,185,129,0.1)',
                      border: '1px solid rgba(16,185,129,0.2)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6ee7b7" strokeWidth="2.2">
                        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                      </svg>
                    </div>
                    <h4 className="text-zinc-200 font-semibold text-[15px]">Active Study Graph</h4>
                  </div>
                  <p className="text-zinc-400 text-xs leading-relaxed">
                    Upload textbooks, lecture files, or research manuscripts to build active, dynamic flashcards and quizzes synced directly to extracted key concepts.
                  </p>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── 2. PROCESSING / LOADING VIEW ── */}
        {store.isProcessing && (
          <motion.div
            key="processing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5 }}
            className="flex flex-col items-center justify-center min-h-[60vh] w-full text-center max-w-xl mx-auto"
          >
            {/* Spinning orbital loader */}
            <div className="relative w-36 h-36 mb-10">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
                style={{
                  position: 'absolute', inset: 0,
                  borderRadius: '50%',
                  border: '1px solid rgba(124,58,237,0.25)',
                  boxShadow: '0 0 45px rgba(124,58,237,0.2)',
                }}
              />
              <motion.div
                animate={{ rotate: -360 }}
                transition={{ duration: 6, repeat: Infinity, ease: 'linear' }}
                style={{
                  position: 'absolute', inset: 12,
                  borderRadius: '50%',
                  border: '1px dashed rgba(244,63,94,0.25)',
                }}
              />
              <motion.div
                animate={{ scale: [1, 1.15, 1], opacity: [0.3, 0.7, 0.3] }}
                transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
                style={{
                  position: 'absolute', inset: 24,
                  borderRadius: '50%',
                  background: 'rgba(124,58,237,0.06)',
                  filter: 'blur(10px)',
                }}
              />
              {/* Center icon */}
              <div style={{
                position: 'absolute', inset: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" strokeWidth="1.5">
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                </svg>
              </div>
            </div>

            <h3 style={{ fontFamily: "'Cormorant Garamond',serif" }} className="text-3xl font-semibold text-zinc-100 mb-2">Synthesizing Material</h3>
            <p className="text-violet-soft text-sm font-semibold tracking-wide uppercase animate-pulse">{LOADING_MESSAGES[loadingMsgIdx]}</p>
            
            {/* Fine shimmer progress bar */}
            <div className="w-64 h-1.5 bg-white/5 rounded-full overflow-hidden relative mt-8">
              <motion.div
                className="absolute top-0 left-0 bottom-0"
                style={{
                  background: 'linear-gradient(90deg,#5b21b6,#a78bfa,#fb923c)',
                  boxShadow: '0 0 10px rgba(124,58,237,0.7)',
                }}
                initial={{ width: "0%" }}
                animate={{ width: "95%" }}
                transition={{ duration: 15, ease: "easeOut" }}
              />
            </div>
          </motion.div>
        )}

        {/* ── 3. INTEL REPORT RESULT VIEW ── */}
        {store.result && !store.isProcessing && (
          <motion.div
            key="result"
            initial={{ opacity: 0, y: 25 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.65, ease: [0.16, 1, 0.3, 1] }}
            className="max-w-7xl mx-auto w-full pb-20"
          >
            {/* Header row */}
            <div className="flex items-center justify-between mb-10 pb-6 border-b border-white/5">
              <div>
                <div className="flex items-center gap-2 text-emerald font-semibold text-xs tracking-wider uppercase mb-2">
                  <span className="glow-dot" style={{ background: '#10b981' }}/>
                  synthesis complete
                </div>
                <h2 style={{ fontFamily: "'Cormorant Garamond',serif" }} className="text-5xl font-semibold text-zinc-100 tracking-tight leading-none">Intelligence Report</h2>
              </div>

              <button
                onClick={() => {
                  store.setResult(null)
                  store.setUploadedFile(null)
                  store.setFlashcards([])
                  store.setQuizQuestions([])
                }}
                className="btn-secondary"
                style={{ padding: '8px 20px', borderRadius: 99, fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>
                </svg>
                Reset Workspace
              </button>
            </div>

            <div className="grid grid-cols-12 gap-8">
              {/* Left Column: Analytics / Navigation */}
              <div className="col-span-12 lg:col-span-4 flex flex-col gap-6">
                {/* Metrics */}
                <div className="surface metric-card p-6">
                  <div className="relative z-10 space-y-6">
                    <h4 className="text-zinc-400 font-semibold text-[13px] tracking-widest uppercase mb-2 flex items-center gap-2">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
                      </svg>
                      Compression Metrics
                    </h4>

                    {[
                      { label: 'Source Material Length', value: store.result.stats?.input_words || 0, suffix: 'words' },
                      { label: 'Conceptual Insights', value: store.result.stats?.bullet_count || 0, suffix: 'points' },
                      { label: 'Information Compression', value: store.result.stats?.compression_pct || 0, suffix: '%' }
                    ].map((m, i) => (
                      <div key={i}>
                        <p className="text-zinc-500 text-[11px] font-medium tracking-wide uppercase mb-1">{m.label}</p>
                        <p className="metric-val text-zinc-100 font-semibold tracking-tight">
                          {m.value}
                          <span className="text-xs font-sans text-zinc-500 font-normal tracking-normal ml-1">{m.suffix}</span>
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Sub-tools Links */}
                <div className="surface rounded-[32px] p-4 flex flex-col gap-2">
                  <motion.button
                    whileHover={{ x: 4 }}
                    onClick={() => store.setActiveView('flashcards')}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 12,
                      width: '100%', padding: '12px', borderRadius: 18,
                      background: 'rgba(255,255,255,0.02)',
                      border: '1px solid rgba(255,255,255,0.04)',
                      cursor: 'pointer', textAlign: 'left',
                    }}
                  >
                    <div style={{
                      width: 40, height: 40, borderRadius: 12,
                      background: 'rgba(124,58,237,0.15)',
                      border: '1px solid rgba(124,58,237,0.2)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" strokeWidth="2.2">
                        <rect x="2" y="6" width="20" height="13" rx="2"/><path d="M6 6V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v2"/>
                      </svg>
                    </div>
                    <div style={{ flex: 1 }}>
                      <h5 className="text-zinc-200 font-semibold text-xs uppercase tracking-wide">Review Flashcards</h5>
                      <p className="text-zinc-500 text-[11px] mt-0.5">{store.flashcards.length || 0} decks structured</p>
                    </div>
                    <span className="text-zinc-600">→</span>
                  </motion.button>

                  <motion.button
                    whileHover={{ x: 4 }}
                    onClick={() => store.setActiveView('quiz')}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 12,
                      width: '100%', padding: '12px', borderRadius: 18,
                      background: 'rgba(255,255,255,0.02)',
                      border: '1px solid rgba(255,255,255,0.04)',
                      cursor: 'pointer', textAlign: 'left',
                    }}
                  >
                    <div style={{
                      width: 40, height: 40, borderRadius: 12,
                      background: 'rgba(244,63,94,0.12)',
                      border: '1px solid rgba(244,63,94,0.2)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fca5a5" strokeWidth="2.2">
                        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                      </svg>
                    </div>
                    <div style={{ flex: 1 }}>
                      <h5 className="text-zinc-200 font-semibold text-xs uppercase tracking-wide">Assessment Quiz</h5>
                      <p className="text-zinc-500 text-[11px] mt-0.5">{store.quizQuestions.length || 0} testing items ready</p>
                    </div>
                    <span className="text-zinc-600">→</span>
                  </motion.button>
                </div>
              </div>

              {/* Right Column: Key Concept Insights */}
              <div className="col-span-12 lg:col-span-8 flex flex-col">
                <div className="surface rounded-[32px] p-8 h-full relative overflow-hidden flex-1">
                  <div style={{
                    position: 'absolute', top: 0, right: 0,
                    width: 350, height: 350, borderRadius: '50%',
                    background: 'radial-gradient(circle,rgba(124,58,237,0.04) 0%,transparent 65%)',
                    filter: 'blur(50px)', pointerEvents: 'none',
                  }}/>

                  <h3 className="text-xl font-semibold text-zinc-100 mb-8 flex items-center gap-3 relative z-10">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
                    </svg>
                    Executive Insights Matrix
                  </h3>

                  <div className="space-y-4 relative z-10">
                    {store.result.bullets.map((b, i) => {
                      const text = b.text || b
                      const tag = b.tag || 'concept'
                      return (
                        <motion.div
                          key={i}
                          initial={{ opacity: 0, x: 15 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: 0.15 + i * 0.05, ease: 'easeOut' }}
                          className="summary-point"
                        >
                          {/* Circle Index */}
                          <div style={{
                            width: 28, height: 28, borderRadius: 10,
                            background: 'rgba(255,255,255,0.03)',
                            border: '1px solid rgba(255,255,255,0.07)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            flexShrink: 0,
                          }}>
                            <span className="text-[11px] font-mono text-zinc-500 font-bold">{i + 1}</span>
                          </div>

                          {/* Insight and Chip */}
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div className="flex items-center gap-3 mb-2 flex-wrap">
                              <span className={`tag tag-${tag}`}>{tag}</span>
                            </div>
                            <p className="text-[14px] text-zinc-300 leading-relaxed font-sans">{text}</p>
                          </div>
                        </motion.div>
                      )
                    })}
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        )}

      </AnimatePresence>
    </div>
  )
}

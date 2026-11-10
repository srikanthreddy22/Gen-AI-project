import React, { useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useDropzone } from 'react-dropzone'
import { FileText, Lightbulb, Sparkles, UploadCloud } from 'lucide-react'
import toast from 'react-hot-toast'
import { getFlashcards, getQuiz, indexText, summarizeText, uploadPDF } from '../utils/api'
import { useNoteStore } from '../store/noteStore'
import AIProcessingIndicator from '../components/animations/AIProcessingIndicator'
import { StudySetSkeleton } from '../components/animations/LoadingSkeletons'
const TAG_COLORS = {
  core: 'tag-core',
  concept: 'tag-concept',
  applied: 'tag-applied',
  advanced: 'tag-advanced',
}

export default function SummarizePage() {
  const store = useNoteStore()
  const [inputType, setInputType] = useState('upload')
  const [pastedText, setPastedText] = useState('')
  const [isDragActive, setIsDragActive] = useState(false)
  const [processingStage, setProcessingStage] = useState('')
  const [uploadProgress, setUploadProgress] = useState(null)
  const processingLock = useRef(false)

  const beginProcessing = () => {
    if (processingLock.current || store.isProcessing) return false
    processingLock.current = true
    store.setProcessing(true)
    return true
  }

  const finishProcessing = () => {
    processingLock.current = false
    store.setProcessing(false)
    setProcessingStage('')
    setUploadProgress(null)
  }

  const processContent = async (text, file = null, docId = null) => {
    if (file) store.setUploadedFile(file)
    store.setDocumentId(docId)
    store.setResult(null)
    store.setFlashcards([])
    store.setQuizQuestions([])
    store.setQuizMessage('')
    try {
      let activeDocId = docId
      if (!activeDocId) {
        setProcessingStage('indexing')
        const indexRes = await indexText(text)
        activeDocId = indexRes.data?.doc_id
        if (!activeDocId || !indexRes.data?.indexed) {
          throw new Error('The pasted text could not be indexed for study content generation.')
        }
        store.setDocumentId(activeDocId)
      }

      setProcessingStage('generating')
      const [summaryResult, flashcardsResult] = await Promise.allSettled([
        summarizeText(text, { bulletCount: 8, method: 'bart' }),
        getFlashcards(activeDocId, 10),
      ])

      let quizResult
      try {
        const qRes = await getQuiz(activeDocId, store.quizQuestionCount)
        quizResult = { status: 'fulfilled', value: qRes }
      } catch (err) {
        quizResult = { status: 'rejected', reason: err }
      }

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

      if (quizResult.status === 'fulfilled' && quizResult.value.data?.questions) {
        store.setQuizQuestions(quizResult.value.data.questions, 'pdf')
        store.setQuizMessage(quizResult.value.data.message || '')
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
      console.error('Processing error:', err)
      const msg = err.response?.data?.error || err.message || 'Summarization error occurred'
      toast.error(msg.includes('Network Error') ? 'Server connection failed' : msg)
    }
  }

  const onDrop = async (acceptedFiles) => {
    const file = acceptedFiles[0]
    if (!file) return
    if (file.size === 0) return toast.error('File is empty')
    if (!beginProcessing()) return

    setProcessingStage('uploading')
    setUploadProgress(null)
    try {
      const res = await uploadPDF(file, setUploadProgress)
      const activeDocId = res.data?.doc_id
      if (!activeDocId || !res.data?.indexed) {
        throw new Error('The uploaded document could not be indexed for study content generation.')
      }
      toast.success('Document uploaded successfully')
      await processContent(res.data.text, file, activeDocId)
    } catch (err) {
      const msg = err.response?.data?.error || err.message || 'Text extraction failed'
      toast.error(msg.includes('Network Error') ? 'Server connection failed' : msg)
    } finally {
      finishProcessing()
    }
  }

  const onDropRejected = (fileRejections) => {
    setIsDragActive(false)
    const rejection = fileRejections[0]
    if (!rejection) return
    const error = rejection.errors[0]
    if (error.code === 'file-invalid-type') toast.error('Unsupported file type. Please upload PDF or TXT.')
    else if (error.code === 'file-too-large') toast.error('File is too large. Max size is 32MB.')
    else toast.error(`Invalid file upload: ${error.message}`)
  }

  const handlePasteSubmit = () => {
    const trimmed = pastedText.trim()
    if (trimmed.length === 0) return toast.error('Text field is empty')
    if (trimmed.length < 30) return toast.error('Please paste at least 30 characters of text.')
    if (!beginProcessing()) return
    setProcessingStage('indexing')
    void processContent(trimmed).finally(finishProcessing)
  }

  const handleTextPaste = (event) => {
    const pasted = event.clipboardData.getData('text')
    if (!pasted) return
    const textarea = event.currentTarget
    const nextText = pastedText.slice(0, textarea.selectionStart) + pasted + pastedText.slice(textarea.selectionEnd)
    event.preventDefault()
    setPastedText(nextText)
    if (nextText.trim().length >= 30 && beginProcessing()) {
      setProcessingStage('indexing')
      void processContent(nextText.trim()).finally(finishProcessing)
    }
  }

  const { getRootProps, getInputProps } = useDropzone({
    onDrop,
    onDropRejected,
    accept: { 'application/pdf': ['.pdf'], 'text/plain': ['.txt'] },
    maxFiles: 1,
    maxSize: 32 * 1024 * 1024,
    disabled: store.isProcessing,
    onDragEnter: () => setIsDragActive(true),
    onDragLeave: () => setIsDragActive(false),
    onDropAccepted: () => setIsDragActive(false),
  })

  const resetReport = () => {
    store.setResult(null)
    store.setUploadedFile(null)
    store.setFlashcards([])
    store.setQuizQuestions([])
  }

  return (
    <div className="h-full w-full overflow-y-auto custom-scrollbar">
      <AnimatePresence mode="wait">
        {!store.result && !store.isProcessing && (
          <motion.main
            key="workspace"
            className="workspace-page"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.32 }}
          >
            <section className="workspace-hero">
              <div>
                <h1>Drop in your notes. Walk out with a plan.</h1>
                <p>Turn class notes, readings, and research into a clear summary, a set of flashcards, and a quiz you can use right away.</p>
              </div>
              <div className="workspace-note">
                <Lightbulb size={22} aria-hidden="true" />
                <p className="mt-3 font-semibold">A little less rereading. A lot more remembering.</p>
                <button type="button" className="btn-ghost mt-3" onClick={store.loadDemo}>Try a sample</button>
              </div>
            </section>

            <section className="workspace-grid">
              <div className="surface workspace-input-panel">
                <div className="workspace-panel-header">
                  <div>
                    <h2 className="m-0 text-xl">Start with your notes</h2>
                    <p className="mt-1 text-sm" style={{ color: 'var(--ink-soft)' }}>Upload a document or paste in your own text.</p>
                  </div>
                  <div className="source-tabs" role="group" aria-label="Choose how to add notes">
                    <button type="button" aria-pressed={inputType === 'upload'} onClick={() => setInputType('upload')} disabled={store.isProcessing}>Upload</button>
                    <button type="button" aria-pressed={inputType === 'paste'} onClick={() => setInputType('paste')} disabled={store.isProcessing}>Paste</button>
                  </div>
                </div>
                <label className="mt-4 flex items-center justify-between gap-4 text-sm font-semibold">
                  Questions per quiz
                  <select
                    className="rounded-[var(--radius-sm)] border px-3 py-2"
                    style={{ background: 'var(--panel)', borderColor: 'var(--line)', color: 'var(--ink)' }}
                    value={store.quizQuestionCount}
                    onChange={(event) => store.setQuizQuestionCount(event.target.value)}
                    disabled={store.isProcessing}
                  >
                    {[5, 10, 15].map((count) => <option key={count} value={count}>{count}</option>)}
                  </select>
                </label>

                <AnimatePresence mode="wait">
                  {inputType === 'upload' ? (
                    <motion.div
                      key="upload-zone"
                      {...getRootProps()}
                      className={`upload-zone flex flex-col items-center justify-center gap-4 text-center${isDragActive ? ' is-drag-active' : ''}`}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.2 }}
                    >
                      <input {...getInputProps()} />
                      <div className="upload-icon grid h-16 w-16 place-items-center rounded-[var(--radius-md)]" style={{ background: 'var(--saffron)' }}>
                        <UploadCloud size={28} aria-hidden="true" />
                      </div>
                      <div>
                        <p className="m-0 text-lg font-bold">{isDragActive ? 'Drop your notes here' : 'Drop a file or browse your notes'}</p>
                        <p className="mt-2 text-sm" style={{ color: 'var(--ink-soft)' }}>PDF or TXT, up to 32 MB</p>
                      </div>
                    </motion.div>
                  ) : (
                    <motion.div
                      key="paste-zone"
                      className="flex min-w-0 flex-col gap-3"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.2 }}
                    >
                      <textarea
                        value={pastedText}
                        onChange={(event) => setPastedText(event.target.value)}
                        onPaste={handleTextPaste}
                        placeholder="Paste your notes here. A few sentences work best."
                        className="input-zone"
                        aria-label="Paste your notes"
                      />
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <span className="font-mono text-xs" style={{ color: 'var(--ink-soft)' }}>{pastedText.length} characters</span>
                        <button type="button" className="btn-primary px-6 py-3 text-base" onClick={handlePasteSubmit} disabled={store.isProcessing}>
                          <Sparkles size={17} aria-hidden="true" /> Synthesize
                        </button>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                <div className="mt-5 flex flex-wrap gap-2">
                  <span className="chip chip-saffron">Model: BART</span>
                  <span className="chip chip-sky">8 insights</span>
                  {store.uploadedFile && <span className="chip chip-teal"><FileText size={14} />{store.uploadedFile.name}</span>}
                </div>
              </div>

              <aside className="flex flex-col gap-4">
                <div className="surface feature-panel">
                  <div className="mb-4 grid h-10 w-10 place-items-center rounded-[var(--radius-sm)]" style={{ background: 'var(--teal)' }}>
                    <Sparkles size={20} aria-hidden="true" />
                  </div>
                  <h2 className="m-0 text-lg">A study set, all at once</h2>
                  <p className="mt-2 leading-relaxed" style={{ color: 'var(--ink-soft)' }}>Your source becomes a concise report, memory-ready flashcards, and a knowledge check.</p>
                </div>
                <div className="surface feature-panel feature-panel-sky rounded-[var(--radius-lg)]">
                  <p className="m-0 text-sm font-bold">Made for the next study session</p>
                  <p className="mb-0 mt-2 text-sm leading-relaxed">Keep your notes together and focus on what matters most.</p>
                </div>
              </aside>
            </section>
          </motion.main>
        )}

        {store.isProcessing && (
          <motion.main
            key="processing"
            className="workspace-page flex min-h-[70vh] flex-col items-center justify-center text-center"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.32 }}
          >
            <h1 className="m-0 text-3xl">
              {processingStage === 'uploading' ? 'Preparing your document' : 'Making a plan from your notes'}
            </h1>
            <AIProcessingIndicator
              message={{
                uploading: 'Uploading and extracting your PDF',
                indexing: 'Preparing your pasted notes',
                generating: 'Generating your summary, flashcards, and quiz',
              }[processingStage] || 'Preparing your study set'}
              progress={processingStage === 'uploading' ? uploadProgress : null}
            />
            <StudySetSkeleton />
          </motion.main>
        )}

        {store.result && !store.isProcessing && (
          <motion.main
            key="report"
            className="report-page"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.32 }}
          >
            <header className="report-header">
              <div>
                <p className="mb-2 font-semibold" style={{ color: 'var(--ink)' }}>Your study report</p>
                <h1>Here's what matters.</h1>
              </div>
              <button type="button" className="btn-secondary px-4 py-2" onClick={resetReport}>New notes</button>
            </header>

            <div className="report-layout">
              <aside className="report-metrics">
                {[
                  { label: 'Source words', value: store.result.stats?.input_words || 0, unit: 'words', className: 'metric-card-sky' },
                  { label: 'Insights', value: store.result.stats?.bullet_count || store.result.bullets?.length || 0, unit: 'ideas', className: 'metric-card-teal' },
                  { label: 'Compression', value: store.result.stats?.compression_pct || 0, unit: '%', className: 'metric-card-saffron' },
                ].map((metric) => (
                  <div className={`metric-card ${metric.className}`} key={metric.label}>
                    <p className="mb-3 text-sm font-bold">{metric.label}</p>
                    <p className="metric-val m-0">{metric.value}</p>
                    <span className="metric-unit text-sm">{metric.unit}</span>
                  </div>
                ))}
                {store.result.keywords?.length > 0 && (
                  <div className="surface keyword-list">
                    {store.result.keywords.slice(0, 12).map((keyword, index) => (
                      <span className={`keyword-chip kw-${index % 5}`} key={`${keyword}-${index}`}>{keyword}</span>
                    ))}
                  </div>
                )}
              </aside>

              <section className="surface insights-panel">
                <div className="mb-5 flex items-center gap-3">
                  <div className="grid h-10 w-10 place-items-center rounded-[var(--radius-sm)]" style={{ background: 'var(--saffron)' }}>
                    <FileText size={19} aria-hidden="true" />
                  </div>
                  <div>
                    <h2 className="m-0 text-xl">Key insights</h2>
                    <p className="m-0 mt-1 text-sm" style={{ color: 'var(--ink-soft)' }}>{store.result.bullets?.length || 0} ideas to take with you</p>
                  </div>
                </div>
                <div className="flex flex-col gap-3">
                  {store.result.bullets?.map((bullet, index) => {
                    const text = bullet.text || bullet
                    const tag = bullet.tag || 'concept'
                    const tagClass = TAG_COLORS[tag] || 'tag-concept'
                    return (
                      <motion.article
                        className={`summary-point ${tagClass}`}
                        key={`${index}-${text}`}
                        initial={{ opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.25, delay: index * 0.03 }}
                      >
                        <span className="insight-number">{String(index + 1).padStart(2, '0')}</span>
                        <div className="min-w-0">
                          <span className={`tag ${tagClass}`}>{tag}</span>
                          <p className="mb-0 mt-2 leading-relaxed">{text}</p>
                        </div>
                      </motion.article>
                    )
                  })}
                </div>
              </section>
            </div>

            <nav className="next-steps" aria-label="Next steps">
              <span className="next-steps-title">Next steps</span>
              <button type="button" className="next-step next-step-teal" onClick={() => store.setActiveView('flashcards')}>Review flashcards</button>
              <button type="button" className="next-step next-step-sky" onClick={() => store.setActiveView('quiz')}>Take the quiz</button>
              <button type="button" className="next-step next-step-coral" onClick={() => document.querySelector('[data-export-pdf]')?.click()}>Export PDF</button>
            </nav>
          </motion.main>
        )}
      </AnimatePresence>
    </div>
  )
}

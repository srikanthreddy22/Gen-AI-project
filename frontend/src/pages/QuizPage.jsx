import React, { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, Loader2, RotateCcw, Sparkles, Trophy, X } from 'lucide-react'
import toast from 'react-hot-toast'
import { useNoteStore } from '../store/noteStore'
import { getQuiz, getQuizHistory, submitQuizAttempt } from '../utils/api'
import AIProcessingIndicator from '../components/animations/AIProcessingIndicator'

export default function QuizPage() {
  const store = useNoteStore()
  const [current, setCurrent] = useState(0)
  const [selected, setSelected] = useState(null)
  const [score, setScore] = useState(0)
  const [done, setDone] = useState(false)
  const [isGeneratingNew, setIsGeneratingNew] = useState(false)
  const [attemptHistory, setAttemptHistory] = useState([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const generationInProgress = useRef(false)
  const questions = store.quizQuestions
  const question = questions[current]
  const correctAnswer = question ? (question.correct || question.correct_answer) : null

  useEffect(() => {
    setCurrent(0)
    setSelected(null)
    setScore(0)
    setDone(false)
  }, [questions])

  useEffect(() => {
    let active = true
    if (!store.documentId) {
      setAttemptHistory([])
      return () => { active = false }
    }

    setHistoryLoading(true)
    getQuizHistory(store.documentId)
      .then(({ data }) => {
        if (active) setAttemptHistory(data.attempts || [])
      })
      .catch((error) => {
        if (active) toast.error(error?.response?.data?.error || 'Quiz history could not be loaded.')
      })
      .finally(() => {
        if (active) setHistoryLoading(false)
      })

    // Automatically load quiz questions if document is active but store has no questions
    if (!questions.length && !generationInProgress.current) {
      setIsGeneratingNew(true)
      generationInProgress.current = true
      getQuiz(store.documentId, store.quizQuestionCount || 5)
        .then(({ data }) => {
          if (active && data?.questions?.length) {
            store.setQuizQuestions(data.questions, 'pdf')
            store.setQuizMessage(data.message || '')
          }
        })
        .catch((err) => {
          console.error('Quiz auto-fetch failed:', err)
        })
        .finally(() => {
          if (active) {
            setIsGeneratingNew(false)
            generationInProgress.current = false
          }
        })
    }

    return () => { active = false }
  }, [store.documentId])

  if (isGeneratingNew && !questions.length) {
    return (
      <main className="quiz-page flex min-h-[70vh] flex-col items-center justify-center text-center">
        <div className="surface w-full max-w-xl p-8 flex flex-col items-center">
          <Loader2 className="animate-spin text-accent mb-4" size={40} />
          <h1 className="m-0 text-2xl font-serif">Preparing your quiz questions…</h1>
          <p className="page-description mx-auto mt-2">
            Formulating concept-based multiple-choice questions with verified options and explanations.
          </p>
        </div>
      </main>
    )
  }

  if (!questions.length) {
    const hasDocument = Boolean(store.documentId)
    return (
      <main className="quiz-page flex min-h-[70vh] flex-col items-center justify-center text-center">
        <div className="surface w-full max-w-xl p-8">
          <h1 className="m-0 text-3xl font-serif">
            {hasDocument ? 'Ready for your quiz?' : 'A quiz starts with your notes.'}
          </h1>
          <p className="page-description mx-auto mt-2">
            {hasDocument
              ? store.quizMessage || 'Generate a quiz from your document notes to test your understanding.'
              : 'Summarise a document first, and we’ll build a quiz from its key ideas.'}
          </p>
          <div className="mt-6 flex items-center justify-center gap-3">
            {hasDocument && (
              <button
                type="button"
                className="btn-primary px-5 py-2.5 flex items-center gap-2"
                onClick={handleGenerateNewQuestions}
                disabled={isGeneratingNew}
              >
                <Sparkles size={16} />
                Generate Quiz
              </button>
            )}
            <button
              type="button"
              className={hasDocument ? 'btn-secondary px-5 py-2.5' : 'btn-primary px-5 py-2.5'}
              onClick={() => store.setActiveView('summarize')}
            >
              {hasDocument ? 'Back to Workspace' : 'Go to Workspace'}
            </button>
          </div>
        </div>
      </main>
    )
  }

  const pick = (option) => {
    if (selected) return
    setSelected(option)
    if (option === correctAnswer) setScore((value) => value + 1)
    if (store.quizMode === 'pdf' && question.record_id) {
      submitQuizAttempt(question.record_id, option)
        .then(({ data }) => setAttemptHistory((history) => [data, ...history].slice(0, 100)))
        .catch((error) => {
          toast.error(error?.response?.data?.error || 'Your answer could not be saved to quiz history.')
        })
    }
  }
  const next = () => {
    if (current + 1 >= questions.length) {
      setDone(true)
      return
    }
    setCurrent((value) => value + 1)
    setSelected(null)
  }
  const restart = () => {
    setCurrent(0)
    setSelected(null)
    setScore(0)
    setDone(false)
  }

  const handleGenerateNewQuestions = async () => {
    if (store.quizMode === 'sample') {
      store.startSampleQuiz()
      setCurrent(0)
      setSelected(null)
      setScore(0)
      setDone(false)
      toast.success('A fresh set of 5 sample questions is ready.')
      return
    }
    if (generationInProgress.current) return
    if (!store.documentId) {
      toast.error('No active document found. Please upload a document first.')
      return
    }

    generationInProgress.current = true
    setIsGeneratingNew(true)
    const toastId = toast.loading(`Generating ${store.quizQuestionCount} assessment questions…`)
    const documentId = store.documentId
    try {
      const exclusions = (store.quizHistory && store.quizHistory.length > 0)
        ? store.quizHistory
        : questions.map((item) => item?.question).filter(Boolean)
      const generationId = `gen_${Date.now()}`
      const response = await getQuiz(documentId, store.quizQuestionCount, exclusions, generationId)

      const currentStore = useNoteStore.getState()
      if (currentStore.documentId !== documentId) {
        toast.dismiss(toastId)
        return
      }

      if (response.data?.questions?.length > 0) {
        const newQuestions = response.data.questions
        store.setQuizQuestions(newQuestions, 'pdf')
        store.setQuizMessage(response.data.message || '')
        setCurrent(0)
        setSelected(null)
        setScore(0)
        setDone(false)
        if (response.data.insufficient_material) {
          toast.success(
            `Generated ${newQuestions.length} new question(s). ${response.data.message || 'All distinct concepts covered.'}`,
            { id: toastId, duration: 4000 }
          )
        } else {
          toast.success(`Generated ${newQuestions.length} brand-new questions!`, { id: toastId })
        }
      } else {
        const message = response.data?.message || 'No new questions could be generated. All document concepts covered.'
        store.setQuizMessage(message)
        toast.error(message, { id: toastId })
      }
    } catch (error) {
      console.error('Failed to generate new quiz questions:', error)
      const errorMessage = error?.response?.data?.error || error?.message || 'Failed to generate new questions.'
      toast.error(`Quiz generation failed: ${errorMessage}`, { id: toastId })
    } finally {
      generationInProgress.current = false
      setIsGeneratingNew(false)
    }
  }

  const percentage = Math.round((score / questions.length) * 100)

  if (done) {
    return (
      <motion.main
        className="quiz-page flex min-h-[70vh] flex-col items-center justify-center text-center"
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.32 }}
      >
        <div className="mb-5 grid h-20 w-20 place-items-center rounded-[var(--radius-lg)]" style={{ background: 'var(--saffron)' }}>
          <Trophy size={38} aria-hidden="true" />
        </div>
        <p className="mb-2 font-semibold" style={{ color: 'var(--ink)' }}>You made it through the questions</p>
        <h1 className="m-0 text-4xl">Your score</h1>
        <p className="font-display m-0 mt-2 text-6xl">{score}<span className="text-3xl"> / {questions.length}</span></p>
        <p className="mx-auto mt-3 max-w-xl leading-relaxed" style={{ color: 'var(--ink)' }}>
          {percentage === 100
            ? 'You have a strong handle on these ideas.'
            : percentage >= 60
              ? 'A quick review of a few missed points will help the ideas stick.'
              : 'Keep exploring the material. You are building a foundation.'}
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          {store.quizMode === 'pdf' && (
            <label className="flex items-center gap-2 text-sm font-semibold">
              Questions per quiz
              <select
                className="rounded-[var(--radius-sm)] border px-3 py-2"
                style={{ background: 'var(--panel)', borderColor: 'var(--line)', color: 'var(--ink)' }}
                value={store.quizQuestionCount}
                onChange={(event) => store.setQuizQuestionCount(event.target.value)}
              >
                {[5, 10, 15].map((count) => <option key={count} value={count}>{count}</option>)}
              </select>
            </label>
          )}
          <button type="button" className="btn-primary px-5 py-2.5" onClick={restart}>
            <RotateCcw size={16} aria-hidden="true" /> Try again
          </button>
          <button type="button" className="btn-secondary px-5 py-2.5" onClick={() => store.setActiveView('summarize')}>
            Back to report
          </button>
          <button type="button" className="btn-secondary px-5 py-2.5" onClick={handleGenerateNewQuestions} disabled={isGeneratingNew && store.quizMode === 'pdf'}>
            {isGeneratingNew && store.quizMode === 'pdf' ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            {isGeneratingNew && store.quizMode === 'pdf' ? 'Making new questions...' : `New questions (${store.quizQuestionCount})`}
          </button>
        </div>
        {store.quizMode === 'pdf' && (
          <section className="surface mx-auto mt-8 w-full max-w-3xl p-5 text-left" aria-labelledby="quiz-history-title">
            <h2 id="quiz-history-title" className="m-0 text-xl">Recent quiz history</h2>
            {historyLoading && <p className="mb-0 mt-3 text-sm">Loading saved attempts…</p>}
            {!historyLoading && attemptHistory.length === 0 && (
              <p className="mb-0 mt-3 text-sm">Your submitted answers will appear here.</p>
            )}
            {attemptHistory.length > 0 && (
              <ol className="mb-0 mt-4 space-y-3 pl-5">
                {attemptHistory.slice(0, 5).map((attempt) => (
                  <li key={attempt.id}>
                    <p className="m-0 font-semibold">{attempt.question}</p>
                    <p className="mb-0 mt-1 text-sm">
                      {attempt.is_correct ? 'Correct' : 'Incorrect'} · Your answer: {attempt.selected_answer}
                      {!attempt.is_correct && ` · Correct answer: ${attempt.correct_answer}`}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </section>
        )}
        {isGeneratingNew && store.quizMode === 'pdf' && <AIProcessingIndicator message="Generating new quiz questions" />}
      </motion.main>
    )
  }

  return (
    <motion.main
      className="quiz-page"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.32 }}
    >
      <header className="mb-7">
        <p className="mb-2 text-sm font-medium" style={{ color: 'var(--ink-soft)' }}>Question {current + 1} of {questions.length}</p>
        <h1>Test what you actually know.</h1>
        <div className="quiz-progress mt-5" aria-label={`${Math.round((current / questions.length) * 100)}% complete`}>
          <motion.div
            className="quiz-progress-fill"
            initial={false}
            animate={{ scaleX: (current + 1) / questions.length }}
            transition={{ duration: 0.32 }}
          />
        </div>
      </header>

      <div className="mx-auto w-full max-w-3xl">
        <AnimatePresence mode="wait">
          <motion.section
            key={current}
            className="quiz-question mb-5"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.24 }}
          >
            <p className="mb-2 text-sm font-semibold">
              {[question.difficulty, question.source_page ? `Page ${question.source_page}` : null].filter(Boolean).join(' · ')}
            </p>
            <h2 className="m-0 text-2xl leading-relaxed">{question.question}</h2>
          </motion.section>
        </AnimatePresence>

        <div className="flex flex-col gap-3">
          {question.options.map((option, index) => {
            const isCorrect = option === correctAnswer
            const isSelected = option === selected
            const stateClass = selected && isCorrect
              ? 'is-correct'
              : selected && isSelected
                ? 'is-wrong'
                : ''
            return (
              <motion.button
                key={`${current}-${index}`}
                type="button"
                className={`quiz-option ${stateClass}`}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2, delay: index * 0.025 }}
                onClick={() => pick(option)}
                disabled={Boolean(selected)}
              >
                <span className="quiz-option-letter mr-3 inline-grid h-8 w-8 place-items-center rounded-[var(--radius-sm)] font-bold">
                  {String.fromCharCode(65 + index)}
                </span>
                {option}
                {selected && isCorrect && (
                  <span className="quiz-option-feedback is-correct-feedback">
                    <Check size={16} aria-hidden="true" /> Correct
                  </span>
                )}
                {selected && isSelected && !isCorrect && (
                  <span className="quiz-option-feedback is-wrong-feedback">
                    <X size={16} aria-hidden="true" /> Not quite
                  </span>
                )}
              </motion.button>
            )
          })}
        </div>

        {selected && (
          <motion.div
            className={`surface quiz-feedback mt-5 flex flex-wrap items-start justify-between gap-4 p-5 ${selected === correctAnswer ? 'is-correct' : 'is-wrong'}`}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div>
              <p className="m-0 font-bold">{selected === correctAnswer ? 'That’s right.' : 'Not quite.'}</p>
              <p className="quiz-explanation">{question.explanation || `The correct answer is ${correctAnswer}.`}</p>
            </div>
            <button type="button" className="btn-primary shrink-0 px-5 py-2.5" onClick={next}>
              {current + 1 >= questions.length ? 'See your score' : 'Next question'}
            </button>
          </motion.div>
        )}
      </div>
    </motion.main>
  )
}

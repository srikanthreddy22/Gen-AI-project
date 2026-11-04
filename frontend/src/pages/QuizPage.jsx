import React, { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, Loader2, RotateCcw, Sparkles, Trophy, X } from 'lucide-react'
import toast from 'react-hot-toast'
import { useNoteStore } from '../store/noteStore'
import { getQuiz } from '../utils/api'
import AIProcessingIndicator from '../components/animations/AIProcessingIndicator'

export default function QuizPage() {
  const store = useNoteStore()
  const [current, setCurrent] = useState(0)
  const [selected, setSelected] = useState(null)
  const [score, setScore] = useState(0)
  const [done, setDone] = useState(false)
  const [isGeneratingNew, setIsGeneratingNew] = useState(false)
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

  if (!questions.length) {
    const hasDocument = Boolean(store.documentId)
    return (
      <main className="quiz-page flex min-h-[70vh] flex-col items-center justify-center text-center">
        <div className="surface w-full max-w-xl p-8">
          <h1 className="m-0 text-3xl">
            {hasDocument ? 'This document needs a little more detail.' : 'A quiz starts with your notes.'}
          </h1>
          <p className="page-description mx-auto">
            {hasDocument
              ? store.quizMessage || 'There is not enough clear information to create reliable quiz questions. Try a longer document with definitions or explanations.'
              : 'Summarise a document first, and we’ll build a quiz from its key ideas.'}
          </p>
          <button type="button" className="btn-primary mt-5 px-5 py-2.5" onClick={() => store.setActiveView('summarize')}>
            {hasDocument ? 'Back to Workspace' : 'Go to Workspace'}
          </button>
        </div>
      </main>
    )
  }

  const pick = (option) => {
    if (selected) return
    setSelected(option)
    if (option === correctAnswer) setScore((value) => value + 1)
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
    if (store.quizMode !== 'pdf' || !store.documentId) {
      toast.error('No active document found. Please upload a document first.')
      return
    }

    generationInProgress.current = true
    setIsGeneratingNew(true)
    const toastId = toast.loading('Generating 5 new assessment questions…')
    const documentId = store.documentId
    try {
      const exclusions = (store.quizHistory && store.quizHistory.length > 0)
        ? store.quizHistory
        : questions.map((item) => item?.question).filter(Boolean)
      const generationId = `gen_${Date.now()}`
      const response = await getQuiz(documentId, 5, exclusions, generationId)

      const currentStore = useNoteStore.getState()
      if (currentStore.quizMode !== 'pdf' || currentStore.documentId !== documentId) {
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
          <button type="button" className="btn-primary px-5 py-2.5" onClick={restart}>
            <RotateCcw size={16} aria-hidden="true" /> Try again
          </button>
          <button type="button" className="btn-secondary px-5 py-2.5" onClick={() => store.setActiveView('summarize')}>
            Back to report
          </button>
          <button type="button" className="btn-secondary px-5 py-2.5" onClick={handleGenerateNewQuestions} disabled={isGeneratingNew && store.quizMode === 'pdf'}>
            {isGeneratingNew && store.quizMode === 'pdf' ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            {isGeneratingNew && store.quizMode === 'pdf' ? 'Making new questions...' : 'New questions'}
          </button>
        </div>
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

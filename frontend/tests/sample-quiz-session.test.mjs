import assert from 'node:assert/strict'
import { test } from 'node:test'
import DEMO_QUESTIONS from '../src/data/demoQuestions.js'
import { useNoteStore } from '../src/store/noteStore.js'

test('sample sessions contain five unique questions and exhaust the 15-question pool before reuse', () => {
  const store = useNoteStore.getState()
  store.reset()
  useNoteStore.setState({ sampleQuizUsedIds: [] })

  const sessions = []
  for (let sessionIndex = 0; sessionIndex < 4; sessionIndex += 1) {
    useNoteStore.getState().startSampleQuiz()
    const state = useNoteStore.getState()
    const questions = state.quizQuestions
    assert.equal(state.quizMode, 'sample')
    assert.equal(questions.length, 5)
    assert.equal(new Set(questions.map((question) => question.id)).size, 5)
    assert.ok(questions.every((question) => (
      question.options.length === 4
      && question.options.includes(question.correct)
      && question.explanation
    )))
    sessions.push(questions.map((question) => question.id))
  }

  assert.equal(DEMO_QUESTIONS.length, 15)
  assert.equal(new Set(sessions.slice(0, 3).flat()).size, 15)
  assert.notDeepEqual(sessions[3].sort(), sessions[2].sort())
})

test('sample and PDF quiz modes switch explicitly even when a document remains in state', () => {
  const store = useNoteStore.getState()
  store.reset()
  store.setDocumentId('existing-document')
  useNoteStore.getState().startSampleQuiz()

  assert.equal(useNoteStore.getState().quizMode, 'sample')
  assert.equal(useNoteStore.getState().documentId, 'existing-document')

  useNoteStore.getState().setQuizQuestions([{ id: 'pdf-question', question: 'PDF question?' }], 'pdf')
  assert.equal(useNoteStore.getState().quizMode, 'pdf')

  useNoteStore.getState().startSampleQuiz()
  assert.equal(useNoteStore.getState().quizMode, 'sample')
  assert.equal(useNoteStore.getState().quizQuestions.length, 5)
})

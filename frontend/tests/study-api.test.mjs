import assert from 'node:assert/strict'
import test from 'node:test'
import api, {
  getQuizHistory,
  loginAsGuest,
  markFlashcardReviewed,
  submitQuizAttempt,
} from '../src/utils/api.js'

test('study API helpers use the authenticated flashcard and quiz routes', async () => {
  const calls = []
  const originalGet = api.get
  const originalPost = api.post
  api.get = (...args) => {
    calls.push(['get', ...args])
    return Promise.resolve({ data: { attempts: [] } })
  }
  api.post = (...args) => {
    calls.push(['post', ...args])
    return Promise.resolve({ data: {} })
  }

  try {
    await markFlashcardReviewed('card/with space')
    await submitQuizAttempt('question-1', 'Option A')
    await getQuizHistory('document-1')
    await loginAsGuest()
  } finally {
    api.get = originalGet
    api.post = originalPost
  }

  assert.deepEqual(calls, [
    ['post', '/flashcards/card%2Fwith%20space/review'],
    ['post', '/quiz/attempts', { question_id: 'question-1', selected_answer: 'Option A' }],
    ['get', '/quiz/attempts', { params: { doc_id: 'document-1' } }],
    ['post', '/auth/guest'],
  ])
})

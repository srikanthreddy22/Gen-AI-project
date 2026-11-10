import assert from 'node:assert/strict'
import { test } from 'node:test'
import DEMO_QUESTIONS from '../src/data/demoQuestions.js'
import {
  optionSimilarity,
  shuffleQuizQuestions,
  validateQuizQuestions,
} from '../src/utils/quizValidation.js'

test('the preserved 15-question sample has four distinct, correctly mapped options per question', () => {
  const report = validateQuizQuestions(DEMO_QUESTIONS)

  assert.equal(DEMO_QUESTIONS.length, 15)
  assert.deepEqual(DEMO_QUESTIONS.map((question) => question.id), Array.from({ length: 15 }, (_, index) => index + 1))
  assert.deepEqual(report.errors, [])
  assert.deepEqual(report.warnings, [])
})

test('normalization detects punctuation and whitespace duplicates and reports duplicate questions', () => {
  const report = validateQuizQuestions([
    {
      id: 1,
      question: 'Which option describes a neural network?',
      options: ['A neural-network model!', 'a neural network model', 'A clustering method', 'A regression method'],
      correct: 'A neural-network model!',
    },
    {
      id: 2,
      question: 'WHICH option describes a neural network',
      options: ['Neural networks use layers', 'Decision trees split features', 'Clustering groups records', 'Regression estimates values'],
      correct: 'Neural networks use layers',
    },
  ])

  assert.ok(report.errors.some((issue) => issue.code === 'duplicate-option'))
  assert.ok(report.errors.some((issue) => issue.code === 'duplicate-question'))
})

test('similarity is a warning signal for near-paraphrase options', () => {
  const first = 'A neural network learns patterns through several hidden layers'
  const second = 'A neural network learns patterns through multiple hidden layers'
  const report = validateQuizQuestions([{
    id: 'similar-options',
    question: 'Which statement describes a neural network?',
    options: [first, second, 'Clustering groups unlabelled observations', 'Regression predicts continuous values'],
    correct: first,
  }])

  assert.ok(optionSimilarity(first, second) >= 0.72)
  assert.deepEqual(report.errors, [])
  assert.equal(report.warnings[0]?.code, 'similar-options')
})

test('sample regeneration shuffles without losing questions or correct-answer mappings', () => {
  const firstShuffle = shuffleQuizQuestions(DEMO_QUESTIONS, () => 0)
  const secondShuffle = shuffleQuizQuestions(
    DEMO_QUESTIONS,
    () => 0,
    firstShuffle.map((question) => question.id),
  )

  assert.notDeepEqual(firstShuffle.map((question) => question.id), DEMO_QUESTIONS.map((question) => question.id))
  assert.notDeepEqual(secondShuffle.map((question) => question.id), firstShuffle.map((question) => question.id))
  for (const question of secondShuffle) {
    assert.equal(question.options.length, 4)
    assert.ok(question.options.includes(question.correct))
  }
  assert.deepEqual(new Set(secondShuffle.map((question) => question.id)), new Set(DEMO_QUESTIONS.map((question) => question.id)))
})

test('validation reports missing choices, invalid answer mappings, and multiple correct answers', () => {
  const report = validateQuizQuestions([
    { id: 1, question: 'Which technique predicts a category?', options: ['Classification'], correct: 'Classification' },
    {
      id: 2,
      question: 'Which technique predicts a category?',
      options: ['Classification', 'Regression', 'Clustering', 'Ranking'],
      correct: 'Dimensionality reduction',
    },
    {
      id: 3,
      question: 'Which technique predicts a category?',
      options: ['Classification', 'Regression', 'Clustering', 'Ranking'],
      correctAnswers: ['Classification', 'Regression'],
    },
  ])

  assert.ok(report.errors.some((issue) => issue.code === 'invalid-option-count'))
  assert.ok(report.errors.some((issue) => issue.code === 'missing-correct-answer'))
  assert.ok(report.errors.some((issue) => issue.code === 'invalid-correct-answer-count'))
})

const STOP_WORDS = new Set([
  'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'does', 'for', 'from',
  'in', 'into', 'is', 'it', 'of', 'on', 'or', 'the', 'to', 'with',
])

export function normalizeQuizText(text) {
  return String(text ?? '')
    .normalize('NFKC')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()
    .replace(/\s+/g, ' ')
}

function contentTokens(text) {
  return new Set(
    normalizeQuizText(text)
      .split(' ')
      .filter((token) => token && !STOP_WORDS.has(token)),
  )
}

export function optionSimilarity(left, right) {
  const leftTokens = contentTokens(left)
  const rightTokens = contentTokens(right)
  const union = new Set([...leftTokens, ...rightTokens])
  if (!union.size) return 1
  let intersectionSize = 0
  for (const token of leftTokens) {
    if (rightTokens.has(token)) intersectionSize += 1
  }
  return intersectionSize / union.size
}

export function shuffleQuizQuestions(questions, random = Math.random, previousOrder = []) {
  const shuffled = questions.map((question) => {
    const options = [...question.options]
    for (let index = options.length - 1; index > 0; index -= 1) {
      const swapIndex = Math.floor(random() * (index + 1))
      const current = options[index]
      options[index] = options[swapIndex]
      options[swapIndex] = current
    }
    return { ...question, options }
  })

  for (let index = shuffled.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(random() * (index + 1))
    const current = shuffled[index]
    shuffled[index] = shuffled[swapIndex]
    shuffled[swapIndex] = current
  }

  const keyFor = (question) => (
    typeof question === 'object' && question !== null
      ? question.id ?? question.question
      : question
  )
  const previousKeys = previousOrder.map(keyFor)
  const sameOrder = shuffled.length > 1
    && previousKeys.length === shuffled.length
    && shuffled.every((question, index) => keyFor(question) === previousKeys[index])

  if (sameOrder) {
    const firstQuestion = shuffled.shift()
    shuffled.push(firstQuestion)
  }
  return shuffled
}

export function selectSampleQuizQuestions(
  questions,
  { count = 5, usedIds = [], previousIds = [], random = Math.random } = {},
) {
  if (!Array.isArray(questions) || count <= 0) return []

  const shuffled = (items) => {
    const result = [...items]
    for (let index = result.length - 1; index > 0; index -= 1) {
      const swapIndex = Math.floor(random() * (index + 1))
      const current = result[index]
      result[index] = result[swapIndex]
      result[swapIndex] = current
    }
    return result
  }
  const previous = new Set(previousIds)
  const unused = questions.filter((question) => !usedIds.includes(question.id))
  const fresh = unused.filter((question) => !previous.has(question.id))
  const selected = shuffled(fresh).slice(0, count)
  const selectedIds = new Set(selected.map((question) => question.id))
  const fillFrom = (candidates) => {
    if (selected.length >= count) return
    for (const question of shuffled(candidates)) {
      if (selected.length >= count) break
      if (selectedIds.has(question.id)) continue
      selected.push(question)
      selectedIds.add(question.id)
    }
  }
  fillFrom(unused.filter((question) => previous.has(question.id)))
  fillFrom(questions.filter((question) => !unused.includes(question) && !previous.has(question.id)))
  fillFrom(questions)

  if (selected.length < count) {
    return selected
  }
  return selected
}

function correctAnswerFor(question, options) {
  const directAnswer = question.correct ?? question.correct_answer ?? question.answer
  const optionKey = question.correct_option ?? question.correctOption
  if (directAnswer != null) return directAnswer
  if (typeof optionKey === 'string' && /^[A-D]$/i.test(optionKey)) {
    return options[optionKey.toUpperCase().charCodeAt(0) - 65]
  }
  return null
}

export function validateQuizQuestions(questions, { optionSimilarityThreshold = 0.72 } = {}) {
  const errors = []
  const warnings = []
  const seenQuestions = new Map()

  if (!Array.isArray(questions)) {
    return { errors: [{ code: 'invalid-dataset', message: 'Quiz questions must be an array.' }], warnings }
  }

  questions.forEach((question, index) => {
    const questionId = question?.id ?? index + 1
    const stem = normalizeQuizText(question?.question)
    if (!stem) {
      errors.push({ code: 'missing-question', questionId, message: 'Question text is required.' })
    } else if (seenQuestions.has(stem)) {
      errors.push({
        code: 'duplicate-question',
        questionId,
        message: `Question duplicates item ${seenQuestions.get(stem)}.`,
      })
    } else {
      seenQuestions.set(stem, questionId)
    }

    const options = question?.options
    if (!Array.isArray(options) || options.length !== 4) {
      errors.push({ code: 'invalid-option-count', questionId, message: 'Each question must have exactly four options.' })
      return
    }

    const normalizedOptions = options.map(normalizeQuizText)
    if (normalizedOptions.some((option) => !option)) {
      errors.push({ code: 'missing-option', questionId, message: 'Every option must contain text.' })
      return
    }

    const seenOptions = new Set()
    normalizedOptions.forEach((option, optionIndex) => {
      if (seenOptions.has(option)) {
        errors.push({
          code: 'duplicate-option',
          questionId,
          optionIndex,
          message: `Option ${String.fromCharCode(65 + optionIndex)} duplicates another option after normalization.`,
        })
      }
      seenOptions.add(option)
    })

    for (let left = 0; left < options.length; left += 1) {
      for (let right = left + 1; right < options.length; right += 1) {
        if (normalizedOptions[left] !== normalizedOptions[right]
          && optionSimilarity(options[left], options[right]) >= optionSimilarityThreshold) {
          warnings.push({
            code: 'similar-options',
            questionId,
            optionIndexes: [left, right],
            message: `Options ${String.fromCharCode(65 + left)} and ${String.fromCharCode(65 + right)} may be too similar.`,
          })
        }
      }
    }

    const correctAnswers = Array.isArray(question?.correctAnswers)
      ? question.correctAnswers
      : [correctAnswerFor(question, options)]
    if (correctAnswers.length !== 1 || correctAnswers[0] == null || !normalizeQuizText(correctAnswers[0])) {
      errors.push({ code: 'invalid-correct-answer-count', questionId, message: 'Exactly one correct answer is required.' })
      return
    }

    const correct = normalizeQuizText(correctAnswers[0])
    if (!normalizedOptions.includes(correct)) {
      errors.push({ code: 'missing-correct-answer', questionId, message: 'The correct answer must match a displayed option.' })
    }

    if (question?.correct != null && question?.correct_answer != null
      && normalizeQuizText(question.correct) !== normalizeQuizText(question.correct_answer)) {
      errors.push({ code: 'inconsistent-correct-answer', questionId, message: 'Correct-answer fields do not match.' })
    }
  })

  return { errors, warnings }
}

import React, { useEffect } from 'react'
import { RotateCcw, Shuffle } from 'lucide-react'
import toast from 'react-hot-toast'
import { useNoteStore } from '../store/noteStore'
import { markFlashcardReviewed } from '../utils/api'

const COLORS = ['var(--coral)', 'var(--teal)', 'var(--sky)', 'var(--saffron)', 'var(--rose)']

export default function FlashcardsPage() {
  const store = useNoteStore()
  const cards = store.flashcards
  const index = cards.length ? store.currentFlashcard % cards.length : 0
  const card = cards[index]

  const flipCard = async () => {
    const revealingAnswer = !store.flashcardFlipped
    store.flipFlashcard()
    if (!revealingAnswer || !card?.record_id) return

    try {
      const { data } = await markFlashcardReviewed(card.record_id)
      useNoteStore.setState((state) => ({
        flashcards: state.flashcards.map((item) => item.record_id === data.record_id
          ? { ...item, review_count: data.review_count, last_reviewed_at: data.last_reviewed_at }
          : item),
      }))
    } catch (error) {
      toast.error(error?.response?.data?.error || 'Review progress could not be saved.')
    }
  }

  const shuffleCards = () => {
    const shuffled = [...cards]
    for (let i = shuffled.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1))
      ;[shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]]
    }
    store.setFlashcards(shuffled)
  }

  useEffect(() => {
    if (!cards.length) return undefined
    const onKeyDown = (event) => {
      const target = event.target
      const typing = target instanceof HTMLElement && (
        target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)
      )
      if (typing || event.altKey || event.ctrlKey || event.metaKey) return

      if (event.code === 'Space') {
        if (target instanceof HTMLButtonElement) return
        event.preventDefault()
        flipCard()
      } else if (event.key === 'ArrowRight') {
        event.preventDefault()
        store.nextFlashcard()
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault()
        store.prevFlashcard()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [cards.length, store.flashcardFlipped, card?.record_id, store.nextFlashcard, store.prevFlashcard])

  if (!card) {
    return (
      <main className="flashcards-page flex min-h-[70vh] flex-col items-center justify-center text-center">
        <div className="surface w-full max-w-xl p-8 flashcard-empty">
          <div className="mx-auto mb-5 grid h-16 w-16 place-items-center rounded-[var(--radius-md)]" style={{ background: 'var(--paper)' }}>
            <RotateCcw size={28} aria-hidden="true" />
          </div>
          <h1 className="m-0 text-3xl">Summarise a document first</h1>
          <p className="mx-auto mt-3 max-w-md leading-relaxed">Add your notes to make a set of flashcards for quick recall practice.</p>
          <button type="button" className="btn-primary mt-5 px-5 py-2.5" onClick={() => store.setActiveView('summarize')}>Go to Workspace</button>
        </div>
      </main>
    )
  }

  return (
    <main className="flashcards-page flex min-h-full flex-col">
      <header className="mb-7">
        <div className="mb-2 flex items-center justify-between gap-4">
          <p className="m-0 text-sm font-semibold" style={{ color: 'var(--ink)' }}>Card {index + 1} of {cards.length}</p>
          <button type="button" className="btn-secondary inline-flex items-center gap-2 px-4 py-2" onClick={shuffleCards}>
            <Shuffle size={16} aria-hidden="true" />
            Shuffle
          </button>
        </div>
        <h1>Recall it before you flip it.</h1>
        <p className="page-description">Tap the card or press Space to reveal the answer. Use the arrow keys to move through your deck.</p>
      </header>

      <div className="flex flex-1 flex-col items-center justify-center gap-7">
        <div className="flashcard-perspective">
          <button
            type="button"
            className={`flashcard flashcard-color-${index % COLORS.length}`}
            onClick={flipCard}
            aria-label={store.flashcardFlipped ? 'Show the question' : 'Reveal the answer'}
            aria-pressed={store.flashcardFlipped}
          >
            <span
              key={`${card.id ?? ''}-${card.question}-${card.answer}`}
              className={`flashcard-inner${store.flashcardFlipped ? ' is-flipped' : ''}`}
            >
              <span className="flashcard-face flashcard-front" aria-hidden={store.flashcardFlipped}>
                <span className="chip" style={{ background: 'var(--paper)' }}>Question</span>
                <span className="text-sm font-semibold">
                  {[card.topic, card.difficulty, card.source_page ? `Page ${card.source_page}` : null].filter(Boolean).join(' · ')}
                </span>
                <span className="font-display text-3xl leading-snug md:text-4xl">{card.question}</span>
                <span className="text-sm font-semibold">Tap or press Space to flip</span>
              </span>
              <span className="flashcard-face flashcard-back" aria-hidden={!store.flashcardFlipped}>
                <span className="chip" style={{ background: 'var(--paper)' }}>Answer</span>
                <span className="font-display text-3xl leading-snug md:text-4xl">{card.answer}</span>
                {card.review_count !== undefined && (
                  <span className="text-sm font-semibold">Reviewed {card.review_count} {card.review_count === 1 ? 'time' : 'times'}</span>
                )}
                <span className="text-sm font-semibold">Tap or press Space to see the question</span>
              </span>
            </span>
          </button>
        </div>

        <div className="flashcard-controls flex w-full max-w-[780px] items-center justify-between gap-4">
          <button type="button" className="btn-secondary px-5 py-2.5" onClick={store.prevFlashcard}>Previous</button>
          <button type="button" className="btn-primary flashcard-flip px-5 py-2.5" onClick={flipCard}>
            {store.flashcardFlipped ? 'Show question' : 'Flip'}
          </button>
          <div className="flashcard-dots" role="group" aria-label="Choose a flashcard">
            {cards.map((item, dotIndex) => (
              <button
                key={item.id || `${item.question}-${dotIndex}`}
                type="button"
                className={`flashcard-dot${dotIndex === index ? ' is-current' : ''}`}
                style={{ borderColor: dotIndex === index ? 'var(--saffron)' : 'var(--line)', background: dotIndex === index ? 'var(--saffron)' : 'var(--line)' }}
                aria-label={`Card ${dotIndex + 1}`}
                aria-current={dotIndex === index ? 'true' : undefined}
                onClick={() => useNoteStore.setState({ currentFlashcard: dotIndex, flashcardFlipped: false })}
              />
            ))}
          </div>
          <button type="button" className="btn-secondary px-5 py-2.5" onClick={store.nextFlashcard}>Next</button>
        </div>
      </div>
    </main>
  )
}

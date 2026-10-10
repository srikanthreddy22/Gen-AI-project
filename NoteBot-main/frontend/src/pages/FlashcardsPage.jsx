import React from 'react'
import { motion } from 'framer-motion'
import { useNoteStore } from '../store/noteStore'

const FALLBACK = [
  {id:1,question:"What is tokenization?",answer:"Splitting raw text into individual units (tokens) such as words or subwords — the first step in any NLP preprocessing pipeline."},
  {id:2,question:"What does BERT stand for?",answer:"Bidirectional Encoder Representations from Transformers — a model that reads text in both directions for deeper contextual understanding."},
  {id:3,question:"What is a language model?",answer:"A probabilistic model that assigns probabilities to sequences of words, used for tasks like text generation, completion, and summarization."},
]

export default function FlashcardsPage() {
  const store = useNoteStore()
  const cards = store.flashcards.length ? store.flashcards : []
  const idx = cards.length ? (store.currentFlashcard % cards.length) : 0
  const card = cards[idx]

  if (!cards.length) {
    return (
      <div className="w-full h-full p-8 flex items-center justify-center text-zinc-300">
        <div className="text-center max-w-lg">
          <p className="text-2xl font-semibold mb-3">No flashcards for the current document</p>
          <p className="text-zinc-400">Upload a document or generate flashcards from the active content to view study cards.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full h-full p-8 overflow-y-auto custom-scrollbar relative scroll-smooth flex flex-col">
      <div className="max-w-[1200px] mx-auto w-full px-8 py-10 flex flex-col flex-1 z-10 relative">
        
        {/* Cinematic Hero Header */}
        <div className="text-center mb-16">
          <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}
            className="inline-block px-4 py-1.5 rounded-full bg-white/[0.03] border border-white/[0.06] backdrop-blur-xl mb-6">
            <span className="text-xs font-semibold tracking-[0.2em] uppercase text-zinc-400">Knowledge Deck • {idx + 1} / {cards.length}</span>
          </motion.div>
          <motion.h1 initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.1 }}
            className="text-6xl font-semibold tracking-tight text-zinc-100 leading-[0.95] font-display">
            Spaced Repetition <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-white via-violet-200 to-fuchsia-400">Memory Engine.</span>
          </motion.h1>
          <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.6, delay: 0.2 }}
            className="text-zinc-500 leading-relaxed max-w-2xl mx-auto mt-6 text-lg">
            Tap the card to reveal the answer. Use the controls below to navigate through your extracted concepts.
          </motion.p>
        </div>

        {/* Central Flashcard Area */}
        <div className="flex-1 flex flex-col items-center justify-center relative w-full mb-16 perspective-[2000px]">
          
          {/* Card Stack Illusion */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="w-full max-w-3xl h-[400px] bg-white/[0.01] border border-white/[0.02] rounded-[36px] absolute translate-y-8 scale-[0.94] blur-[3px] opacity-20" />
            <div className="w-full max-w-3xl h-[400px] bg-white/[0.02] border border-white/[0.04] rounded-[36px] absolute translate-y-4 scale-[0.97] blur-[1px] opacity-40" />
          </div>

          {/* Interactive Card */}
          <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, type: 'spring' }}
            className="w-full max-w-3xl relative z-10 perspective-[2000px] h-[400px]" onClick={store.flipFlashcard}>
            
            <motion.div className="relative w-full h-full cursor-pointer transform-gpu"
              whileHover={{ rotateX: 2, rotateY: -2, scale: 1.015, y: -4 }}
              transition={{ duration: 0.5, ease: 'easeOut' }}>
              
              {/* Front Face (Question) */}
              <motion.div
                initial={false}
                animate={{ 
                  rotateY: store.flashcardFlipped ? 180 : 0, 
                  opacity: store.flashcardFlipped ? 0 : 1,
                  y: [0, -6, 0]
                }}
                transition={{ 
                  duration: 0.7, type: 'tween', ease: [0.23, 1, 0.32, 1],
                  y: { repeat: Infinity, duration: 6, ease: "easeInOut" }
                }}
                className="surface absolute inset-0 rounded-[36px] flex flex-col items-center justify-center text-center p-16 transition-shadow duration-700"
                style={{ pointerEvents: store.flashcardFlipped ? 'none' : 'auto' }}>
                
                <div className="text-xs uppercase tracking-[0.3em] mb-10 font-semibold text-violet-400/80">Question</div>
                <p className="text-5xl leading-tight font-medium text-zinc-100 drop-shadow-lg">{card.question}</p>
              </motion.div>

              {/* Back Face (Answer) */}
              <motion.div
                initial={{ rotateY: -180, opacity: 0 }}
                animate={{ 
                  rotateY: store.flashcardFlipped ? 0 : -180, 
                  opacity: store.flashcardFlipped ? 1 : 0,
                  y: [0, -6, 0]
                }}
                transition={{ 
                  duration: 0.7, type: 'tween', ease: [0.23, 1, 0.32, 1],
                  y: { repeat: Infinity, duration: 6, ease: "easeInOut", delay: 3 }
                }}
                className="surface absolute inset-0 rounded-[36px] flex flex-col items-center justify-center text-center p-16 transition-shadow duration-700"
                style={{ pointerEvents: store.flashcardFlipped ? 'auto' : 'none' }}>
                
                <div className="text-xs uppercase tracking-[0.3em] mb-10 font-semibold text-fuchsia-400/80">Answer</div>
                <p className="text-3xl leading-relaxed text-zinc-300 drop-shadow-md">{card.answer}</p>
              </motion.div>
              
            </motion.div>
          </motion.div>
        </div>

        {/* Elegant Navigation Controls */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}
          className="w-full max-w-3xl mx-auto flex items-center justify-between gap-8">
          
          <motion.button whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} onClick={store.prevFlashcard}
            className="flex-1 py-5 rounded-3xl text-[15px] font-semibold text-zinc-300 bg-white/[0.03] backdrop-blur-xl border border-white/[0.06] shadow-[0_10px_40px_rgba(0,0,0,0.3)] hover:bg-white/[0.06] hover:border-white/[0.1] transition-all flex items-center justify-center gap-3">
            Previous
          </motion.button>
          
          <div className="flex gap-2.5 px-4">
            {cards.map((_, i) => (
              <motion.div key={i} animate={{ scale: i === idx ? 1 : 0.8, opacity: i === idx ? 1 : 0.2 }}
                className="cursor-pointer transition-all rounded-full"
                style={{ width: i === idx ? 40 : 12, height: 6, background: i === idx ? 'linear-gradient(90deg, #8B5CF6, #D946EF)' : '#ffffff' }}
                onClick={() => { useNoteStore.setState({ currentFlashcard: i, flashcardFlipped: false }) }}/>
            ))}
          </div>

          <motion.button whileHover={{ scale: 1.03, brightness: 1.1 }} whileTap={{ scale: 0.97 }} onClick={store.nextFlashcard}
            className="flex-1 py-5 rounded-3xl text-[15px] font-semibold text-white bg-gradient-to-r from-violet-600 via-fuchsia-500 to-purple-500 shadow-[0_15px_60px_rgba(168,85,247,0.35)] transition-all flex items-center justify-center gap-3">
            Next
          </motion.button>
        </motion.div>

      </div>
    </div>
  )
}

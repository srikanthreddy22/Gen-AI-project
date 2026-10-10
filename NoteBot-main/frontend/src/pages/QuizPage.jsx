import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle2, XCircle, Trophy, RotateCcw } from 'lucide-react'
import { useNoteStore } from '../store/noteStore'

export default function QuizPage() {
  const store = useNoteStore()
  const [current, setCurrent] = useState(0)
  const [selected, setSelected] = useState(null)
  const [score, setScore] = useState(0)
  const [done, setDone] = useState(false)
  const questions = store.quizQuestions.length ? store.quizQuestions : []
  const q = questions[current]

  if (!questions.length) {
    return (
      <div className="w-full h-full p-8 flex items-center justify-center text-zinc-300">
        <div className="text-center max-w-lg">
          <p className="text-2xl font-semibold mb-3">No quiz generated yet</p>
          <p className="text-zinc-400">Upload a document and generate a quiz from the current uploaded content.</p>
        </div>
      </div>
    )
  }

  const pick = (opt) => {
    if (selected) return
    setSelected(opt)
    if (opt === q.correct) setScore(s => s+1)
  }
  const next = () => {
    if (current+1 >= questions.length) { setDone(true); return }
    setCurrent(i => i+1); setSelected(null)
  }
  const restart = () => { setCurrent(0); setSelected(null); setScore(0); setDone(false) }

  const pct = Math.round((score/questions.length)*100)

  if (done) return (
    <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="flex flex-col items-center justify-center h-full gap-8 p-8 text-center relative">
      <motion.div initial={{ scale: 0, rotate: -20 }} animate={{ scale: 1, rotate: 0 }} transition={{ type: 'spring', stiffness: 200, delay: 0.2 }}
        className="w-28 h-28 rounded-[2rem] flex items-center justify-center bg-white/5 border border-white/10 backdrop-blur-xl shadow-[0_0_60px_rgba(139,92,246,0.15)] relative">
        <Trophy size={48} className="text-violet-400" />
      </motion.div>

      <div>
        <motion.h2 initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
          className="text-5xl font-semibold tracking-tight text-zinc-100 mb-3 font-display">
          Assessment <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-fuchsia-400">Complete</span>
        </motion.h2>
        <motion.div initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.4, type: 'spring' }}
          className="text-6xl font-bold font-mono mb-6 text-zinc-100">
          {score} <span className="text-zinc-500 text-4xl">/ {questions.length}</span>
        </motion.div>
        <div className="w-64 h-2 rounded-full mx-auto mb-6 bg-white/10 overflow-hidden">
          <motion.div initial={{ width: 0 }} animate={{ width: `${pct}%` }} transition={{ duration: 1, delay: 0.5, ease: 'easeOut' }}
            className="h-full rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500 shadow-[0_0_15px_rgba(139,92,246,0.5)]" />
        </div>
        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 }} className="text-lg text-zinc-400">
          {pct===100 ? 'Flawless execution. You have mastered these concepts.' : pct>=60 ? 'Solid understanding. A quick review of the missed points will solidify your knowledge.' : 'Keep exploring the material. You are building the foundation.'}
        </motion.p>
      </div>

      <motion.button initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.7 }}
        whileHover={{ scale: 1.05, y: -2 }} whileTap={{ scale: 0.95 }}
        onClick={restart}
        className="flex items-center gap-2 px-8 py-4 rounded-2xl text-sm font-semibold text-white bg-violet-600/80 hover:bg-violet-500 border border-violet-500/50 shadow-[0_0_30px_rgba(139,92,246,0.3)] backdrop-blur-md transition-all">
        <RotateCcw size={18} /> Retry Assessment
      </motion.button>
    </motion.div>
  )

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95 }} transition={{ duration: 0.6 }}
      className="flex flex-col items-center justify-start h-full p-8 pt-12 relative overflow-y-auto custom-scrollbar">

      <div className="w-full max-w-3xl relative">
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <div className="text-sm font-mono text-zinc-400">
              Question <span className="text-zinc-100 font-semibold">{current+1}</span> / {questions.length}
            </div>
            <div className="h-4 w-px bg-white/10" />
            <div className="flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${q.difficulty==='easy'?'bg-emerald-400':q.difficulty==='medium'?'bg-violet-400':'bg-fuchsia-400'} shadow-[0_0_10px_currentColor]`} />
              <span className="text-xs font-medium capitalize text-zinc-300">{q.difficulty}</span>
            </div>
          </div>
          <div className="flex items-center gap-2 text-sm px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-zinc-300 backdrop-blur-md">
            Score: <span className="font-bold text-violet-400 font-mono ml-1">{score}</span>
          </div>
        </motion.div>

        {/* Progress */}
        <div className="h-1.5 rounded-full mb-10 overflow-hidden bg-white/10">
          <motion.div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500 shadow-[0_0_15px_rgba(139,92,246,0.5)]"
            animate={{ width: `${((current)/questions.length)*100}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}/>
        </div>

        {/* Question */}
        <AnimatePresence mode="wait">
          <motion.div key={current} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.4 }}
            className="surface rounded-3xl p-10 mb-8">
            <p className="text-2xl leading-relaxed font-medium text-zinc-100">{q.question}</p>
          </motion.div>
        </AnimatePresence>

        {/* Options */}
        <div className="flex flex-col gap-4">
          <AnimatePresence>
            {q.options.map((opt, i) => {
              const isCorrect = opt === q.correct
              const isSelected = opt === selected
              let baseStyle = "bg-white/5 border-white/10 text-zinc-300"
              if (selected) {
                if (isCorrect) baseStyle = "bg-emerald-500/10 border-emerald-500/40 text-emerald-300 shadow-[0_0_30px_rgba(16,185,129,0.15)]"
                else if (isSelected) baseStyle = "bg-fuchsia-500/10 border-fuchsia-500/40 text-fuchsia-300 shadow-[0_0_30px_rgba(217,70,239,0.15)]"
                else baseStyle = "bg-white/5 border-white/5 text-zinc-500 opacity-50"
              }
              return (
                <motion.button key={`${current}-${i}`}
                  initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.32, ease: [0.4, 0, 0.2, 1] }}
                  whileHover={!selected ? { x: 6, scale: 1.01 } : {}}
                  onClick={() => pick(opt)}
                  className={`flex items-center gap-6 text-left px-6 py-5 rounded-2xl text-[15px] transition-all font-medium border backdrop-blur-md cursor-${selected?'default':'pointer'} ${baseStyle}`}>
                  <div className={`w-8 h-8 rounded-xl border flex items-center justify-center text-sm font-bold flex-shrink-0 opacity-70 border-current`}>
                    {String.fromCharCode(65+i)}
                  </div>
                  <span className="flex-1 leading-relaxed">{opt}</span>
                  {selected && isCorrect && <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 400 }}><CheckCircle2 size={24} className="text-emerald-400" /></motion.div>}
                  {selected && isSelected && !isCorrect && <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 400 }}><XCircle size={24} className="text-fuchsia-400" /></motion.div>}
                </motion.button>
              )
            })}
          </AnimatePresence>
        </div>

        {/* Next */}
        <AnimatePresence>
          {selected && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="surface mt-10 flex justify-between items-center p-6 rounded-2xl">
              <p className={`text-[15px] font-medium ${selected===q.correct ? 'text-emerald-400' : 'text-fuchsia-400'}`}>
                {selected===q.correct ? '✓ Precision confirmed. Excellent work.' : `✗ The accurate response is: "${q.correct}"`}
              </p>
              <motion.button whileHover={{ scale: 1.05, x: 2 }} whileTap={{ scale: 0.95 }} onClick={next}
                className="px-8 py-3 rounded-xl text-sm font-semibold text-white bg-violet-600/80 hover:bg-violet-500 border border-violet-500/50 shadow-[0_0_20px_rgba(139,92,246,0.3)] transition-all">
                {current+1 >= questions.length ? 'Finalize Assessment' : 'Proceed →'}
              </motion.button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}

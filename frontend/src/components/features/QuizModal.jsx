import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, CheckCircle, XCircle } from 'lucide-react'
import { useNoteStore } from '../../store/noteStore'

export default function QuizModal() {
  const { quizOpen, setQuizOpen, quizAnswer, setQuizAnswer, getDemoQuestions, quizQuestions } = useNoteStore()
  const questions = (quizQuestions.length ? quizQuestions : getDemoQuestions())
  const q = questions[0]
  if (!quizOpen || !q) return null

  return (
    <AnimatePresence>
      <motion.div initial={{ opacity:0 }} animate={{ opacity:1 }} exit={{ opacity:0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-6"
        style={{ background:'var(--scrim)', backdropFilter:'blur(12px)' }}
        onClick={e => { if(e.target===e.currentTarget) setQuizOpen(false) }}>
        <motion.div initial={{ scale:0.88, y:20, opacity:0 }} animate={{ scale:1, y:0, opacity:1 }}
          exit={{ scale:0.92, y:10, opacity:0 }} transition={{ type:'spring', stiffness:300, damping:25 }}
          className="quiz-modal-surface w-full max-w-lg rounded-[var(--radius-lg)] p-8 relative overflow-hidden"
          style={{ background:'var(--panel-raised)', border:'1px solid var(--line)', boxShadow:'0 12px 32px var(--panel-shadow)', color:'var(--text)' }}>
          {/* Glow */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-80 h-32 pointer-events-none"
            style={{ background:'radial-gradient(ellipse,var(--accent-10) 0%,transparent 70%)', filter:'blur(20px)' }}/>

          <div className="relative">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-xl font-bold" style={{ fontFamily:"'Playfair Display',serif", color:'var(--ink)' }}>Quick Quiz</h3>
                <p className="text-[11px] mt-0.5" style={{ color:'var(--ink-dim)' }}>Question 1 of {questions.length}</p>
              </div>
              <motion.button whileHover={{ scale:1.1, rotate:90 }} transition={{ type:'spring', stiffness:400 }}
                onClick={() => setQuizOpen(false)}
                className="w-8 h-8 rounded-[var(--radius-sm)] flex items-center justify-center transition-all"
                aria-label="Close quiz"
                style={{ background:'var(--surface)', border:'1px solid var(--line)', color:'var(--ink-dim)' }}>
                <X size={14}/>
              </motion.button>
            </div>

            <p className="text-[15px] leading-relaxed mb-6 font-medium" style={{ color:'var(--ink)' }}>{q.question}</p>

            <div className="flex flex-col gap-2.5">
              {q.options.map((opt, i) => {
                const isCorrect = opt === q.correct
                const isSelected = opt === quizAnswer
                let style = { background:'var(--panel)', border:'1px solid var(--line)', color:'var(--text)' }
                if (quizAnswer) {
                  if (isCorrect) style = { background:'var(--success-14)', border:'1px solid var(--success)', color:'var(--text)' }
                  else if (isSelected) style = { background:'var(--danger-12)', border:'1px solid var(--danger)', color:'var(--text)' }
                }
                return (
                  <motion.button key={opt}
                    initial={{ opacity:0, x:-10 }} animate={{ opacity:1, x:0 }}
                    transition={{ delay:i*0.06, ease:[0.16,1,0.3,1] }}
                    whileHover={!quizAnswer ? { x:4, scale:1.01 } : {}}
                    onClick={() => { if(!quizAnswer) setQuizAnswer(opt) }}
                    className={`quiz-modal-option flex items-center gap-3 text-left px-4 py-3.5 text-[13px] transition-all font-medium${quizAnswer ? isCorrect ? ' is-correct' : isSelected ? ' is-wrong' : '' : ''}`}
                    style={{ ...style, cursor:quizAnswer?'default':'pointer', fontFamily:"'Outfit',sans-serif" }}>
                    <div className="w-6 h-6 rounded-[var(--radius-sm)] border flex items-center justify-center text-[11px] font-bold flex-shrink-0"
                      style={{ borderColor:'currentColor' }}>
                      {String.fromCharCode(65+i)}
                    </div>
                    {opt}
                    {quizAnswer && isCorrect && <CheckCircle size={16} className="ml-auto flex-shrink-0" style={{ color:'var(--success)' }}/>}
                    {quizAnswer && isSelected && !isCorrect && <XCircle size={16} className="ml-auto flex-shrink-0" style={{ color:'var(--danger)' }}/>}
                  </motion.button>
                )
              })}
            </div>

            {quizAnswer && (
              <motion.div initial={{ opacity:0, y:8 }} animate={{ opacity:1, y:0 }} className="mt-6 flex justify-end">
                <motion.button whileHover={{ scale:1.03, y:-1 }} whileTap={{ scale:0.97 }}
                  onClick={() => setQuizOpen(false)}
                  className="px-6 py-2.5 rounded-[var(--radius-sm)] text-[13px] font-semibold btn-primary">
                  Continue
                </motion.button>
              </motion.div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

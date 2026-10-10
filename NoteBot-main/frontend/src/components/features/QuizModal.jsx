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
        style={{ background:'rgba(5,5,14,0.8)', backdropFilter:'blur(12px)' }}
        onClick={e => { if(e.target===e.currentTarget) setQuizOpen(false) }}>
        <motion.div initial={{ scale:0.88, y:20, opacity:0 }} animate={{ scale:1, y:0, opacity:1 }}
          exit={{ scale:0.92, y:10, opacity:0 }} transition={{ type:'spring', stiffness:300, damping:25 }}
          className="w-full max-w-lg rounded-3xl p-8 relative overflow-hidden"
          style={{ background:'linear-gradient(135deg,rgba(15,15,30,0.98),rgba(9,9,21,0.98))', border:'1px solid rgba(124,58,237,0.3)', boxShadow:'0 0 60px rgba(124,58,237,0.2),0 30px 60px rgba(0,0,0,0.5)' }}>
          {/* Glow */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-80 h-32 pointer-events-none"
            style={{ background:'radial-gradient(ellipse,rgba(124,58,237,0.15) 0%,transparent 70%)', filter:'blur(20px)' }}/>

          <div className="relative">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-xl font-bold text-white" style={{ fontFamily:"'Playfair Display',serif" }}>Quick Quiz</h3>
                <p className="text-[11px] text-ink-400 mt-0.5">Question 1 of {questions.length}</p>
              </div>
              <motion.button whileHover={{ scale:1.1, rotate:90 }} transition={{ type:'spring', stiffness:400 }}
                onClick={() => setQuizOpen(false)}
                className="w-8 h-8 rounded-full flex items-center justify-center transition-all"
                style={{ background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.1)', color:'#8884aa' }}>
                <X size={14}/>
              </motion.button>
            </div>

            <p className="text-[15px] leading-relaxed text-ink-100 mb-6 font-medium">{q.question}</p>

            <div className="flex flex-col gap-2.5">
              {q.options.map((opt, i) => {
                const isCorrect = opt === q.correct
                const isSelected = opt === quizAnswer
                let style = { background:'rgba(255,255,255,0.03)', border:'1px solid rgba(255,255,255,0.1)', color:'#8884aa' }
                if (quizAnswer) {
                  if (isCorrect) style = { background:'rgba(16,185,129,0.1)', border:'1px solid rgba(16,185,129,0.4)', color:'#34d399', boxShadow:'0 0 20px rgba(16,185,129,0.15)' }
                  else if (isSelected) style = { background:'rgba(244,63,94,0.1)', border:'1px solid rgba(244,63,94,0.4)', color:'#fb7185', boxShadow:'0 0 20px rgba(244,63,94,0.1)' }
                }
                return (
                  <motion.button key={opt}
                    initial={{ opacity:0, x:-10 }} animate={{ opacity:1, x:0 }}
                    transition={{ delay:i*0.06, ease:[0.16,1,0.3,1] }}
                    whileHover={!quizAnswer ? { x:4, scale:1.01 } : {}}
                    onClick={() => { if(!quizAnswer) setQuizAnswer(opt) }}
                    className="flex items-center gap-3 text-left px-4 py-3.5 rounded-2xl text-[13px] transition-all font-medium"
                    style={{ ...style, cursor:quizAnswer?'default':'pointer', fontFamily:"'Outfit',sans-serif" }}>
                    <div className="w-6 h-6 rounded-full border flex items-center justify-center text-[11px] font-bold flex-shrink-0"
                      style={{ borderColor:'currentColor', opacity:0.6 }}>
                      {String.fromCharCode(65+i)}
                    </div>
                    {opt}
                    {quizAnswer && isCorrect && <CheckCircle size={16} className="ml-auto flex-shrink-0" style={{ color:'#34d399' }}/>}
                    {quizAnswer && isSelected && !isCorrect && <XCircle size={16} className="ml-auto flex-shrink-0" style={{ color:'#fb7185' }}/>}
                  </motion.button>
                )
              })}
            </div>

            {quizAnswer && (
              <motion.div initial={{ opacity:0, y:8 }} animate={{ opacity:1, y:0 }} className="mt-6 flex justify-end">
                <motion.button whileHover={{ scale:1.03, y:-1 }} whileTap={{ scale:0.97 }}
                  onClick={() => setQuizOpen(false)}
                  className="px-6 py-2.5 rounded-full text-[13px] font-semibold text-white btn-primary">
                  Continue →
                </motion.button>
              </motion.div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

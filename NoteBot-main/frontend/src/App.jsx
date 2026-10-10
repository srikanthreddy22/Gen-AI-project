import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import SceneBackdrop from './components/background/SceneBackdrop'
import Sidebar from './components/layout/Sidebar'
import Topbar from './components/layout/Topbar'
import SummarizePage from './pages/SummarizePage'
import FlashcardsPage from './pages/FlashcardsPage'
import QuizPage from './pages/QuizPage'
import { useNoteStore } from './store/noteStore'

export default function App() {
  const { activeView } = useNoteStore()

  return (
    <div className="app-shell flex h-screen w-screen overflow-hidden relative text-zinc-100 font-sans">
      <SceneBackdrop />
      <Sidebar />
      <div className="app-content flex flex-col flex-1 min-w-0 relative z-10">
        <Topbar />
        <div className="content-scroll flex-1 overflow-y-auto custom-scrollbar">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={activeView}
              className="page-transition"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.32, ease: [0.4, 0, 0.2, 1] }}
            >
              {activeView === 'summarize' && <SummarizePage />}
              {activeView === 'flashcards' && <FlashcardsPage />}
              {activeView === 'quiz' && <QuizPage />}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}

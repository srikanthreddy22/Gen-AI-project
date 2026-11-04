import React, { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import { motion, AnimatePresence, MotionConfig, useReducedMotion } from 'framer-motion'
import Preloader from './components/animations/Preloader'
import SceneBackdrop from './components/background/SceneBackdrop'
import Sidebar from './components/layout/Sidebar'
import Topbar from './components/layout/Topbar'
import { useNoteStore } from './store/noteStore'

const SummarizePage = lazy(() => import('./pages/SummarizePage'))
const FlashcardsPage = lazy(() => import('./pages/FlashcardsPage'))
const QuizPage = lazy(() => import('./pages/QuizPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))

function resolveView(pathname) {
  if (pathname === '/' || pathname === '/workspace') return 'summarize'
  if (pathname === '/flashcards') return 'flashcards'
  if (pathname === '/knowledge') return 'quiz'
  return null
}

export default function App() {
  const activeView = useNoteStore((state) => state.activeView)
  const routeView = resolveView(window.location.pathname)
  const [notFound, setNotFound] = useState(routeView === null)
  const [showPreloader, setShowPreloader] = useState(true)
  const finishPreloader = useCallback(() => setShowPreloader(false), [])
  const reduceMotion = useReducedMotion()
  const displayedView = routeView || activeView

  useEffect(() => {
    if (routeView) useNoteStore.setState({ activeView: routeView })

    const restoreView = () => {
      const view = resolveView(window.location.pathname)
      setNotFound(view === null)
      useNoteStore.setState({
        activeView: view || 'summarize',
      })
    }
    window.addEventListener('popstate', restoreView)
    return () => window.removeEventListener('popstate', restoreView)
  }, [routeView])

  return (
    <MotionConfig reducedMotion={reduceMotion ? 'always' : 'never'}>
      <div className="app-shell flex h-screen w-full overflow-hidden relative font-sans">
        {showPreloader && <Preloader onDone={finishPreloader} />}
        <SceneBackdrop />
        <Sidebar />
        <div className="app-content flex flex-col flex-1 min-w-0 relative z-10">
          <Topbar />
          <div className="content-scroll flex-1 overflow-y-auto custom-scrollbar">
            {notFound ? (
              <Suspense fallback={<div className="route-loading" role="status">Loading…</div>}>
                <NotFoundPage />
              </Suspense>
            ) : (
              <AnimatePresence mode="wait" initial={false}>
                <motion.div
                  key={displayedView}
                  className="page-transition"
                  initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={reduceMotion ? false : { opacity: 0, y: -6 }}
                  transition={{ duration: reduceMotion ? 0 : 0.32, ease: [0.4, 0, 0.2, 1] }}
                >
                  <Suspense fallback={<div className="route-loading" role="status">Loading…</div>}>
                    {displayedView === 'summarize' && <SummarizePage />}
                    {displayedView === 'flashcards' && <FlashcardsPage />}
                    {displayedView === 'quiz' && <QuizPage />}
                  </Suspense>
                </motion.div>
              </AnimatePresence>
            )}
          </div>
        </div>
      </div>
    </MotionConfig>
  )
}

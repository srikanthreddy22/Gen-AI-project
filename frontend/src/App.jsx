import React, { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import { motion, AnimatePresence, MotionConfig, useReducedMotion } from 'framer-motion'
import Preloader from './components/animations/Preloader'
import SceneBackdrop from './components/background/SceneBackdrop'
import Sidebar from './components/layout/Sidebar'
import Topbar from './components/layout/Topbar'
import { useNoteStore } from './store/noteStore'
import AuthPage from './pages/AuthPage'
import { ACCESS_TOKEN_KEY, getCurrentUser, logout } from './utils/api'
import toast from 'react-hot-toast'

const SummarizePage = lazy(() => import('./pages/SummarizePage'))
const FlashcardsPage = lazy(() => import('./pages/FlashcardsPage'))
const QuizPage = lazy(() => import('./pages/QuizPage'))
const ChatPage = lazy(() => import('./pages/ChatPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))

function resolveView(pathname) {
  if (pathname === '/' || pathname === '/workspace') return 'summarize'
  if (pathname === '/flashcards') return 'flashcards'
  if (pathname === '/knowledge') return 'quiz'
  if (pathname === '/chat') return 'chat'
  return null
}

export default function App() {
  const activeView = useNoteStore((state) => state.activeView)
  const routeView = resolveView(window.location.pathname)
  const [notFound, setNotFound] = useState(routeView === null)
  const [showPreloader, setShowPreloader] = useState(true)
  const [user, setUser] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)
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

  useEffect(() => {
    let active = true
    const handleExpired = () => {
      if (active) setUser(null)
    }
    window.addEventListener('notebot:auth-expired', handleExpired)

    if (!window.localStorage.getItem(ACCESS_TOKEN_KEY)) {
      setAuthLoading(false)
    } else {
      getCurrentUser()
        .then((response) => {
          if (active) setUser(response.data)
        })
        .catch(() => {
          if (active) {
            window.localStorage.removeItem(ACCESS_TOKEN_KEY)
            setUser(null)
          }
        })
        .finally(() => {
          if (active) setAuthLoading(false)
        })
    }

    return () => {
      active = false
      window.removeEventListener('notebot:auth-expired', handleExpired)
    }
  }, [])

  const handleLogout = useCallback(async () => {
    try {
      await logout()
    } catch {
      toast.error('The session could not be revoked by the server.')
    } finally {
      window.localStorage.removeItem(ACCESS_TOKEN_KEY)
      setUser(null)
    }
  }, [])

  if (authLoading) {
    return <div className="scene-backdrop" role="status" style={{ display: 'grid', placeItems: 'center' }}>Checking your session…</div>
  }

  if (!user) {
    return <AuthPage onAuthenticated={setUser} />
  }

  return (
    <MotionConfig reducedMotion={reduceMotion ? 'always' : 'never'}>
      <div className="app-shell flex h-screen w-full overflow-hidden relative font-sans">
        {showPreloader && <Preloader onDone={finishPreloader} />}
        <SceneBackdrop />
        <Sidebar />
        <div className="app-content flex flex-col flex-1 min-w-0 relative z-10">
          <Topbar user={user} onLogout={handleLogout} />
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
                    {displayedView === 'chat' && <ChatPage />}
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

import React, { useCallback, useEffect, useRef, useState } from 'react'

const DWELL_TIME = 5000
const CROSSFADE_TIME = 1800
const WAIT_AFTER_CROSSFADE = DWELL_TIME - CROSSFADE_TIME
const CROSSFADE_EASE = 'cubic-bezier(0.4, 0, 0.2, 1)'

function shuffled(items) {
  const result = [...items]
  for (let i = result.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[result[i], result[j]] = [result[j], result[i]]
  }
  return result
}

export default function SceneBackdrop({
  variant = 'default',
  veilStyle = null,
  imageStackOpacity = null,
  showBlobs = true,
  children = null,
} = {}) {
  const [layers, setLayers] = useState([null, null])
  const [activeScene, setActiveScene] = useState(null)
  const [incomingScene, setIncomingScene] = useState(null)
  const [activeSlot, setActiveSlot] = useState(0)
  const [incomingSlot, setIncomingSlot] = useState(null)
  const [reducedMotion, setReducedMotion] = useState(false)
  const [documentHidden, setDocumentHidden] = useState(false)
  const [hoverPaused, setHoverPaused] = useState(false)

  const mountedRef = useRef(false)
  const orderRef = useRef([])
  const failedRef = useRef(new Set())
  const preloadRef = useRef(new Map())
  const activeRef = useRef(null)
  const activeSlotRef = useRef(0)
  const transitionTimerRef = useRef(null)
  const transitioningRef = useRef(false)
  const reducedMotionRef = useRef(false)

  const preload = useCallback((scene) => {
    if (!scene) return Promise.resolve(null)
    if (preloadRef.current.has(scene.id)) return preloadRef.current.get(scene.id)

    const imagePromise = new Promise((resolve) => {
      try {
        const image = new Image()
        image.onload = () => resolve(scene)
        image.onerror = () => {
          failedRef.current.add(scene.id)
          console.warn(`Background scene failed to load: ${scene.id}`)
          resolve(null)
        }
        image.src = scene.src
        if (image.complete && image.naturalWidth > 0) resolve(scene)
      } catch (error) {
        failedRef.current.add(scene.id)
        console.warn(`Background scene could not be preloaded: ${scene.id}`, error)
        resolve(null)
      }
    })

    preloadRef.current.set(scene.id, imagePromise)
    return imagePromise
  }, [])

  const showScene = useCallback(async (scene, initial = false) => {
    if (!scene || scene.id === activeRef.current?.id) return false

    const loadedScene = await preload(scene)
    if (!mountedRef.current || !loadedScene) return false

    if (initial || !activeRef.current) {
      const firstSlot = 0
      setLayers([loadedScene, null])
      setActiveSlot(firstSlot)
      setActiveScene(null)
      setIncomingScene(loadedScene)
      setIncomingSlot(firstSlot)
      activeSlotRef.current = firstSlot
      transitioningRef.current = true
      if (transitionTimerRef.current) clearTimeout(transitionTimerRef.current)
      transitionTimerRef.current = setTimeout(() => {
        if (!mountedRef.current) return
        activeRef.current = loadedScene
        transitioningRef.current = false
        setActiveScene(loadedScene)
        setIncomingScene(null)
        setIncomingSlot(null)
      }, reducedMotionRef.current ? 0 : CROSSFADE_TIME)
    } else {
      const nextSlot = activeSlotRef.current === 0 ? 1 : 0
      setLayers((currentLayers) => {
        const nextLayers = [...currentLayers]
        nextLayers[nextSlot] = loadedScene
        return nextLayers
      })
      setIncomingScene(loadedScene)
      setIncomingSlot(nextSlot)
      transitioningRef.current = true

      if (transitionTimerRef.current) clearTimeout(transitionTimerRef.current)
      transitionTimerRef.current = setTimeout(() => {
        if (!mountedRef.current) return
        activeRef.current = loadedScene
        activeSlotRef.current = nextSlot
        transitioningRef.current = false
        setActiveScene(loadedScene)
        setActiveSlot(nextSlot)
        setIncomingScene(null)
        setIncomingSlot(null)
      }, reducedMotionRef.current ? 0 : CROSSFADE_TIME)
    }

    return true
  }, [preload])

  const nextSceneFrom = useCallback((scene) => {
    const order = orderRef.current
    if (!order.length) return null
    const startIndex = order.findIndex((candidate) => candidate.id === scene?.id)
    for (let offset = 1; offset <= order.length; offset += 1) {
      const candidate = order[(startIndex + offset + order.length) % order.length]
      if (candidate.id !== scene?.id && !failedRef.current.has(candidate.id)) return candidate
    }
    return null
  }, [])

  const advance = useCallback(async (scene = activeRef.current) => {
    let candidate = nextSceneFrom(scene)
    while (candidate && mountedRef.current) {
      if (await showScene(candidate)) return
      candidate = nextSceneFrom(candidate)
    }
  }, [nextSceneFrom, showScene])

  useEffect(() => {
    mountedRef.current = true

    try {
      const preference = window.matchMedia('(prefers-reduced-motion: reduce)')
      reducedMotionRef.current = preference.matches
      setReducedMotion(preference.matches)
      const updatePreference = (event) => {
        reducedMotionRef.current = event.matches
        setReducedMotion(event.matches)
      }
      preference.addEventListener('change', updatePreference)
      return () => {
        preference.removeEventListener('change', updatePreference)
        mountedRef.current = false
        if (transitionTimerRef.current) clearTimeout(transitionTimerRef.current)
      }
    } catch (error) {
      console.warn('Could not read the reduced-motion preference.', error)
      return () => {
        mountedRef.current = false
        if (transitionTimerRef.current) clearTimeout(transitionTimerRef.current)
      }
    }
  }, [])

  useEffect(() => {
    const updateVisibility = () => {
      try {
        setDocumentHidden(document.visibilityState === 'hidden')
      } catch (error) {
        console.warn('Could not read document visibility.', error)
      }
    }

    try {
      updateVisibility()
      document.addEventListener('visibilitychange', updateVisibility)
      return () => document.removeEventListener('visibilitychange', updateVisibility)
    } catch (error) {
      console.warn('Could not observe document visibility.', error)
      return undefined
    }
  }, [])

  useEffect(() => {
    const isHoverTarget = (target) => target instanceof Element && Boolean(
      target.closest('button, a, input, textarea, select, [role="button"], .surface, .glass-panel, .glass-card, .glass-raised'),
    )
    const handlePointerOver = (event) => {
      if (isHoverTarget(event.target)) setHoverPaused(true)
    }
    const handlePointerOut = (event) => {
      if (isHoverTarget(event.target) && !isHoverTarget(event.relatedTarget)) setHoverPaused(false)
    }

    document.addEventListener('pointerover', handlePointerOver)
    document.addEventListener('pointerout', handlePointerOut)
    return () => {
      document.removeEventListener('pointerover', handlePointerOver)
      document.removeEventListener('pointerout', handlePointerOut)
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    const loadManifest = async () => {
      try {
        const response = await fetch('/backgrounds/manifest.json')
        if (!response.ok) throw new Error(`Manifest request failed with ${response.status}`)
        const manifest = await response.json()
        if (!Array.isArray(manifest.scenes) || manifest.scenes.length === 0) {
          throw new Error('The scene manifest contains no scenes.')
        }

        const prefersReducedMotion = typeof window.matchMedia === 'function'
          && window.matchMedia('(prefers-reduced-motion: reduce)').matches
        const orderedScenes = prefersReducedMotion ? manifest.scenes : shuffled(manifest.scenes)
        if (cancelled) return

        orderRef.current = orderedScenes
        for (const scene of orderedScenes) {
          if (await showScene(scene, true)) return
          if (cancelled) return
        }
      } catch (error) {
        if (!cancelled) console.error('Could not load the background scene manifest.', error)
      }
    }

    loadManifest()
    return () => {
      cancelled = true
    }
  }, [reducedMotion, showScene])

  useEffect(() => {
    if (!activeScene || reducedMotion || documentHidden || hoverPaused) return undefined

    const nextScene = nextSceneFrom(activeScene)
    if (nextScene) preload(nextScene)

    const timer = setTimeout(() => advance(activeScene), WAIT_AFTER_CROSSFADE)
    return () => clearTimeout(timer)
  }, [activeScene, advance, documentHidden, hoverPaused, nextSceneFrom, preload, reducedMotion])

  const isVisible = (slot) => (
    (incomingScene && incomingSlot === slot) || (!incomingScene && activeScene && activeSlot === slot)
  )

  const isAuth = variant === 'auth'
  const computedImageStackStyle = imageStackOpacity !== null
    ? { opacity: imageStackOpacity }
    : (isAuth ? { opacity: 0.82 } : undefined)

  const defaultAuthVeil = {
    background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.78) 0%, rgba(207, 250, 254, 0.72) 100%)',
  }
  const computedVeilStyle = veilStyle || (isAuth ? defaultAuthVeil : undefined)

  return (
    <>
      <div className="scene-backdrop" aria-hidden="true">
        <div className="scene-image-stack" style={computedImageStackStyle}>
          {layers.map((scene, slot) => scene && (
            <div
              className={`scene-layer${incomingScene?.id === scene.id ? ' scene-layer-entering' : ''}`}
              key={`${slot}-${scene.id}`}
              style={{
                opacity: isVisible(slot) ? 1 : 0,
                transitionDuration: `${reducedMotion ? 0 : CROSSFADE_TIME}ms`,
                transitionTimingFunction: CROSSFADE_EASE,
                animationDuration: `${reducedMotion ? 0 : CROSSFADE_TIME}ms`,
              }}
            >
              <img
                className={`scene-image${reducedMotion ? ' scene-image-static' : (isAuth ? ' scene-image-auth' : '')}`}
                src={scene.src}
                alt=""
                draggable="false"
                style={{
                  objectPosition: scene.focal || '50% 50%',
                  filter: isAuth ? 'saturate(1.05) brightness(1.02)' : 'saturate(0.9) brightness(1.04)',
                  animationDuration: isAuth ? '8000ms' : `${DWELL_TIME}ms`,
                }}
              />
            </div>
          ))}
        </div>
        <div className="scene-warm-veil" style={computedVeilStyle} />
        {(!isAuth && showBlobs) && (
          <div className="scene-blobs">
            <div className="scene-blob scene-blob-coral" />
            <div className="scene-blob scene-blob-saffron" />
            <div className="scene-blob scene-blob-teal" />
          </div>
        )}
        {children}
      </div>
    </>
  )
}

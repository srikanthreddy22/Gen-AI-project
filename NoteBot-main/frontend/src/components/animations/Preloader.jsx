import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNoteStore } from '../../store/noteStore'

const STAGES = [
  { msg:'Initializing NLP engine…',   pct:15 },
  { msg:'Loading BART transformer…',  pct:35 },
  { msg:'Calibrating spaCy pipeline…',pct:57 },
  { msg:'Warming LSA & TF-IDF…',      pct:78 },
  { msg:'Preparing your workspace…',  pct:100 },
]

export default function Preloader() {
  const { preloaderDone, setPreloaderDone } = useNoteStore()
  const [stage, setStage] = useState(0)
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    const ts = STAGES.map((_, i) => setTimeout(() => setStage(i), i * 600))
    ts.push(setTimeout(() => {
      setVisible(false)
      setTimeout(() => setPreloaderDone(true), 800)
    }, STAGES.length * 600 + 200))
    return () => ts.forEach(clearTimeout)
  }, [])

  const particles = Array.from({ length: 12 }, (_, i) => ({
    angle: (i / 12) * 360,
    delay: i * 0.15,
    size: 2 + Math.random() * 3,
    dx: (Math.random() - 0.5) * 60,
  }))

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 1 }}
          exit={{ opacity: 0, scale: 1.04 }}
          transition={{ duration: 0.8, ease: [0.4, 0, 0.2, 1] }}
          style={{
            position: 'fixed', inset: 0, zIndex: 9999,
            background: '#080611',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            overflow: 'hidden',
          }}
        >
          {/* ── Ambient background ── */}
          <div style={{ position:'absolute', inset:0, pointerEvents:'none' }}>
            {/* Primary violet orb */}
            <motion.div
              animate={{ scale:[1,1.4,1], opacity:[0.4,0.8,0.4] }}
              transition={{ duration:6, repeat:Infinity, ease:'easeInOut' }}
              style={{
                position:'absolute', top:'50%', left:'50%',
                transform:'translate(-50%,-50%)',
                width:700, height:700, borderRadius:'50%',
                background:'radial-gradient(circle,rgba(124,58,237,0.14) 0%,transparent 65%)',
                filter:'blur(80px)',
              }}
            />
            {/* Rose accent */}
            <motion.div
              animate={{ scale:[1,1.2,1], x:[0,-40,0], y:[0,30,0] }}
              transition={{ duration:9, repeat:Infinity, ease:'easeInOut', delay:2 }}
              style={{
                position:'absolute', bottom:'15%', right:'20%',
                width:350, height:350, borderRadius:'50%',
                background:'radial-gradient(circle,rgba(244,63,94,0.07) 0%,transparent 65%)',
                filter:'blur(60px)',
              }}
            />
            {/* Amber */}
            <motion.div
              animate={{ scale:[1,1.3,1], y:[0,-30,0] }}
              transition={{ duration:7, repeat:Infinity, ease:'easeInOut', delay:1 }}
              style={{
                position:'absolute', top:'20%', left:'15%',
                width:300, height:300, borderRadius:'50%',
                background:'radial-gradient(circle,rgba(251,146,60,0.05) 0%,transparent 65%)',
                filter:'blur(50px)',
              }}
            />
            {/* Fine grid */}
            <div style={{
              position:'absolute', inset:0, opacity:0.025,
              backgroundImage:`
                linear-gradient(rgba(255,255,255,0.6) 1px,transparent 1px),
                linear-gradient(90deg,rgba(255,255,255,0.6) 1px,transparent 1px)
              `,
              backgroundSize:'64px 64px',
            }}/>
          </div>

          {/* ── Orbital rings ── */}
          <div style={{ position:'absolute', top:'50%', left:'50%', transform:'translate(-50%,-50%)', pointerEvents:'none' }}>
            {[560, 400, 280].map((sz, i) => (
              <motion.div key={sz}
                animate={{ rotate: i % 2 === 0 ? 360 : -360 }}
                transition={{ duration: 18 - i * 3, repeat:Infinity, ease:'linear' }}
                style={{
                  position:'absolute',
                  width:sz, height:sz,
                  top:'50%', left:'50%',
                  marginTop:-sz/2, marginLeft:-sz/2,
                  borderRadius:'50%',
                  border:`1px ${i===1?'dashed':'solid'} rgba(124,58,237,${0.04+i*0.02})`,
                }}
              />
            ))}
          </div>

          {/* ── Logo ── */}
          <motion.div
            initial={{ scale: 0.3, opacity: 0, rotate: -20 }}
            animate={{ scale: 1, opacity: 1, rotate: 0 }}
            transition={{ type: 'spring', stiffness: 160, damping: 18, delay: 0.1 }}
            style={{ position:'relative', marginBottom: 44 }}
          >
            {/* Animated border ring */}
            <div style={{
              position:'absolute', inset:-10, borderRadius:32,
              padding:1,
              background:'conic-gradient(from 0deg,#7c3aed,#f472b6,#fb923c,#10b981,#7c3aed)',
              WebkitMask:'linear-gradient(#fff 0 0) content-box,linear-gradient(#fff 0 0)',
              WebkitMaskComposite:'xor',
              maskComposite:'exclude',
              animation:'orbitSpin 4s linear infinite',
            }}/>

            {/* Core mark */}
            <div style={{
              width:96, height:96, borderRadius:28,
              background:'linear-gradient(135deg,#3b0764,#5b21b6,#7c3aed)',
              display:'flex', alignItems:'center', justifycontent:'center',
              position:'relative',
              animation:'logoGlow 3s ease-in-out infinite',
              border:'1px solid rgba(196,181,253,0.25)',
            }}>
              <div style={{
                position:'absolute', inset:3, borderRadius:24,
                border:'1px solid rgba(255,255,255,0.12)',
              }}/>
              <span style={{
                fontFamily:"'Cormorant Garamond',Georgia,serif",
                fontSize:48, fontWeight:700, color:'#fff',
                position:'relative', zIndex:1,
                textShadow:'0 0 30px rgba(255,255,255,0.4)',
                lineHeight:1,
              }}>N</span>
            </div>

            {/* Floating particles */}
            {particles.map((p, i) => (
              <motion.div key={i}
                initial={{ opacity:0, x:0, y:0 }}
                animate={{ opacity:[0,1,0], x:p.dx, y:-70 }}
                transition={{ duration:2.5, repeat:Infinity, delay:i*0.2, ease:'easeOut' }}
                style={{
                  position:'absolute',
                  top:`${40+Math.sin(p.angle*Math.PI/180)*20}%`,
                  left:`${40+Math.cos(p.angle*Math.PI/180)*20}%`,
                  width:p.size, height:p.size,
                  borderRadius:'50%',
                  background:`hsl(${260+i*18},70%,75%)`,
                }}
              />
            ))}
          </motion.div>

          {/* ── Brand ── */}
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.38, ease: [0.16,1,0.3,1] }}
            style={{ textAlign:'center', marginBottom: 52 }}
          >
            <h1 style={{
              fontFamily:"'Cormorant Garamond',Georgia,serif",
              fontSize: 64,
              fontWeight: 700,
              letterSpacing: '-0.04em',
              lineHeight: 1,
              marginBottom: 10,
              background: 'linear-gradient(135deg,#fff 0%,#c4b5fd 35%,#f472b6 70%,#fb923c 100%)',
              WebkitBackgroundClip:'text',
              WebkitTextFillColor:'transparent',
              backgroundClip:'text',
            }}>NoteBot</h1>
            <p style={{
              fontFamily:"'DM Sans',sans-serif",
              fontSize: 12,
              letterSpacing: '0.2em',
              textTransform: 'uppercase',
              color: 'rgba(196,181,253,0.55)',
              fontWeight: 500,
            }}>AI Study Intelligence</p>
          </motion.div>

          {/* ── Progress ── */}
          <motion.div
            initial={{ opacity:0, y:8 }}
            animate={{ opacity:1, y:0 }}
            transition={{ delay: 0.55 }}
            style={{ width: 320 }}
          >
            {/* Track */}
            <div style={{
              height:2, borderRadius:99, overflow:'hidden', marginBottom:14,
              background:'rgba(255,255,255,0.06)',
            }}>
              <motion.div
                style={{
                  height:'100%', borderRadius:99,
                  background:'linear-gradient(90deg,#5b21b6,#7c3aed,#a78bfa,#f472b6)',
                  backgroundSize:'300% 100%',
                  animation:'barShimmer 2s linear infinite',
                  boxShadow:'0 0 12px rgba(124,58,237,0.8)',
                }}
                animate={{ width:`${STAGES[stage].pct}%` }}
                transition={{ duration:0.5, ease:'easeOut' }}
              />
            </div>
            {/* Label row */}
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
              <motion.span
                key={stage}
                initial={{ opacity:0, y:4 }}
                animate={{ opacity:1, y:0 }}
                transition={{ duration:0.25 }}
                style={{
                  fontFamily:"'Fira Code',monospace",
                  fontSize:11,
                  color:'rgba(168,160,196,0.8)',
                  letterSpacing:'0.02em',
                }}
              >
                {STAGES[stage].msg}
              </motion.span>
              <span style={{
                fontFamily:"'Fira Code',monospace",
                fontSize:11,
                color:'rgba(124,58,237,0.8)',
                fontWeight:600,
              }}>{STAGES[stage].pct}%</span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

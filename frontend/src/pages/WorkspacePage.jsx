import React, { useEffect, useCallback, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useDropzone } from 'react-dropzone'
import toast from 'react-hot-toast'
import clsx from 'clsx'
import { useNoteStore } from '../store/noteStore'
import { checkHealth, uploadFile, summarize, getFlashcards, getQuiz } from '../utils/api'
import QuizModal from '../components/modals/QuizModal'

/* ── Tag config ─────────────────────────────── */
const TAG_CFG = {
  core:     { bg:'color-mix(in srgb,var(--accent) 14%,transparent)', color:'var(--accent)', border:'color-mix(in srgb,var(--accent) 30%,transparent)', dot:'var(--accent)', hoverBg:'color-mix(in srgb,var(--accent) 6%,transparent)' },
  concept:  { bg:'color-mix(in srgb,var(--success) 14%,transparent)', color:'var(--success)', border:'color-mix(in srgb,var(--success) 30%,transparent)', dot:'var(--success)', hoverBg:'color-mix(in srgb,var(--success) 6%,transparent)' },
  advanced: { bg:'color-mix(in srgb,var(--warn) 14%,transparent)', color:'var(--warn)', border:'color-mix(in srgb,var(--warn) 30%,transparent)', dot:'var(--warn)', hoverBg:'color-mix(in srgb,var(--warn) 6%,transparent)' },
  applied:  { bg:'color-mix(in srgb,var(--danger) 14%,transparent)', color:'var(--danger)', border:'color-mix(in srgb,var(--danger) 30%,transparent)', dot:'var(--danger)', hoverBg:'color-mix(in srgb,var(--danger) 6%,transparent)' },
  eval:     { bg:'color-mix(in srgb,var(--info) 14%,transparent)', color:'var(--info)', border:'color-mix(in srgb,var(--info) 30%,transparent)', dot:'var(--info)', hoverBg:'color-mix(in srgb,var(--info) 6%,transparent)' },
  key:      { bg:'color-mix(in srgb,var(--accent-2) 14%,transparent)', color:'var(--accent-2)', border:'color-mix(in srgb,var(--accent-2) 30%,transparent)', dot:'var(--accent-2)', hoverBg:'color-mix(in srgb,var(--accent-2) 6%,transparent)' },
  theory:   { bg:'color-mix(in srgb,var(--accent) 14%,transparent)', color:'var(--accent)', border:'color-mix(in srgb,var(--accent) 30%,transparent)', dot:'var(--accent)', hoverBg:'color-mix(in srgb,var(--accent) 6%,transparent)' },
  example:  { bg:'color-mix(in srgb,var(--danger) 14%,transparent)', color:'var(--danger)', border:'color-mix(in srgb,var(--danger) 30%,transparent)', dot:'var(--danger)', hoverBg:'color-mix(in srgb,var(--danger) 6%,transparent)' },
}
const KW_COLORS = [
  { bg:'color-mix(in srgb,var(--accent) 14%,transparent)', color:'var(--accent)', border:'color-mix(in srgb,var(--accent) 30%,transparent)' },
  { bg:'color-mix(in srgb,var(--success) 14%,transparent)', color:'var(--success)', border:'color-mix(in srgb,var(--success) 30%,transparent)' },
  { bg:'color-mix(in srgb,var(--warn) 14%,transparent)', color:'var(--warn)', border:'color-mix(in srgb,var(--warn) 30%,transparent)' },
  { bg:'color-mix(in srgb,var(--danger) 14%,transparent)', color:'var(--danger)', border:'color-mix(in srgb,var(--danger) 30%,transparent)' },
  { bg:'color-mix(in srgb,var(--info) 14%,transparent)', color:'var(--info)', border:'color-mix(in srgb,var(--info) 30%,transparent)' },
]
const MODELS = [
  { id:'auto',   label:'Auto — Best available', sub:'OpenAI → BART → LSA' },
  { id:'openai', label:'OpenAI GPT-4o-mini',    sub:'Requires OPENAI_API_KEY' },
  { id:'bart',   label:'BART-large-cnn',         sub:'HuggingFace local transformer' },
  { id:'lsa',    label:'LSA — sumy',             sub:'Latent Semantic Analysis' },
]

/* ── Sub-components ─────────────────────────── */
function Tag({ tag }) {
  const cfg = TAG_CFG[tag] || TAG_CFG.core
  return (
    <span style={{
      display:'inline-flex', alignItems:'center', gap:5,
      padding:'3px 10px', borderRadius:'var(--radius-sm)',
      fontSize:10, fontWeight:700, letterSpacing:'0.06em', textTransform:'uppercase',
      background:cfg.bg, color:'var(--text)',
      border:`1px solid ${cfg.border}`,
      flexShrink:0,
    }}>
      <span style={{ width:5, height:5, clipPath:'circle(50%)', background:cfg.dot, flexShrink:0 }}/>
      {tag}
    </span>
  )
}

function NumberBadge({ n, tag }) {
  const cfg = TAG_CFG[tag] || TAG_CFG.core
  return (
    <div style={{
      width:32, height:32, borderRadius:'var(--radius-sm)', flexShrink:0,
      background:`linear-gradient(135deg,${cfg.bg},color-mix(in srgb,var(--page) 10%,transparent))`,
      border:`1px solid ${cfg.border}`,
      display:'flex', alignItems:'center', justifyContent:'center',
      fontFamily:"'Fira Code','JetBrains Mono',monospace",
      fontSize:13, fontWeight:700, color:'var(--text)',
      boxShadow:`0 0 12px ${cfg.bg}`,
    }}>{n}</div>
  )
}

function MetricRow({ label, value, unit, glow }) {
  return (
    <div style={{ marginBottom:28, position:'relative' }}>
      <div style={{
        fontSize:10, fontWeight:600, letterSpacing:'0.15em',
        textTransform:'uppercase', color:'var(--text-soft)',
        marginBottom:6, fontFamily:"'DM Sans','Outfit',sans-serif",
      }}>{label}</div>
      <div style={{ display:'flex', alignItems:'baseline', gap:8 }}>
        <span style={{
          fontFamily:"'Cormorant Garamond',Georgia,serif",
          fontSize:62, fontWeight:700, lineHeight:1,
          letterSpacing:'-0.04em', color:'var(--text)',
          textShadow:`0 0 40px ${glow}`,
        }}>{value}</span>
        <span style={{
          fontSize:14, color:'var(--text-soft)',
          fontFamily:"'DM Sans',sans-serif", fontWeight:400,
        }}>{unit}</span>
      </div>
    </div>
  )
}

/* ── Main Component ─────────────────────────── */
export default function WorkspacePage() {
  const store = useAppStore()
  const [uploadPct, setUploadPct] = useState(0)
  const [modelOpen, setModelOpen] = useState(false)
  const selModel = MODELS.find(m => m.id === store.selectedModel) || MODELS[0]

  useEffect(() => {
    checkHealth()
      .then(() => { store.setBackendOnline(true); toast.success('Backend connected', { duration:2000 }) })
      .catch(() => { store.setBackendOnline(false); toast('Demo mode — backend offline', { icon:'ℹ️', duration:3000 }) })
  }, [])

  const onDrop = useCallback(async ([file]) => {
    if (!file) return
    store.setUploadedFile(file)
    store.setDocumentTitle(file.name.replace(/\.[^.]+$/, ''))
    const tid = toast.loading(`Uploading ${file.name}…`)
    try {
      const res = await uploadFile(file, p => setUploadPct(p))
      store.setInputText(res.data.text)
      store.setDocumentId(res.data.doc_id)
      toast.success(`✓ ${res.data.pages || 1} page(s) · ${res.data.word_count?.toLocaleString()} words · ${res.data.extraction_method || 'uploaded'}`, { id:tid, duration:4000 })
      setUploadPct(0)
    } catch (err) {
      toast.error(err?.response?.data?.error || 'Upload failed — is backend running?', { id:tid })
      setUploadPct(0)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept:{'application/pdf':['.pdf'],'text/plain':['.txt','.md']},
    maxFiles:1,
    maxSize:32*1024*1024,
  })

  const run = async () => {
    const text = store.inputText.trim()
    const docId = store.documentId
    if (text.length < 30) { toast.error('Need at least 30 characters!'); return }
    if (!docId) { toast.error('Please upload a document first'); return }
    store.setProcessing(true, `Running ${selModel.label}…`)
    try {
      const [s, f, q] = await Promise.all([
        summarize(text, store.selectedModel, store.bulletCount),
        getFlashcards(docId, 8),
        getQuiz(docId, 5),
      ])
      store.setResult(s.data)
      store.setFlashcards(f.data.flashcards)
      store.setQuizQuestions(q.data.questions)
      toast.success(`✓ Synthesized via ${s.data.stats.model}`)
    } catch {
      toast('Backend offline — loading demo', { icon:'⚡' })
      store.loadDemo()
    } finally {
      store.setProcessing(false)
    }
  }

  const result = store.result

  /* ══ RESULT VIEW ══ */
  if (result) return (
    <>
      <QuizModal/>
      <motion.div initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}} style={{height:'100%', overflow:'hidden', display:'flex', flexDirection:'column'}}>
        {/* Header */}
        <motion.div initial={{opacity:0, y:-12}} animate={{opacity:1, y:0}} transition={{ease:[0.16,1,0.3,1], duration:0.5}} style={{padding:'24px 32px 20px', background:'linear-gradient(180deg,var(--accent-10) 0%,transparent 100%)', borderBottom:'1px solid var(--line)', flexShrink:0}}>
          <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:10}}>
            <div style={{display:'flex', alignItems:'center', gap:8}}>
              <div style={{width:8, height:8, clipPath:'circle(50%)', background:'var(--success)', animation:'preloaderPulse 2s ease-in-out infinite'}}/>
              <span style={{fontSize:11, fontWeight:700, letterSpacing:'0.18em', textTransform:'uppercase', color:'var(--success)', fontFamily:"'DM Sans',sans-serif"}}>Synthesis Complete</span>
            </div>
            <motion.button whileHover={{scale:1.02, y:-1}} whileTap={{scale:0.98}} onClick={store.reset} style={{display:'flex', alignItems:'center', gap:8, padding:'8px 18px', borderRadius:'var(--radius-sm)', background:'transparent', border:'1px solid var(--line)', color:'var(--text)', fontSize:12, fontWeight:500, cursor:'pointer', fontFamily:"'DM Sans',sans-serif"}}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
              Reset Workspace
            </motion.button>
          </div>
          <div style={{position:'relative'}}>
            <h1 style={{fontFamily:"'Cormorant Garamond',Georgia,serif", fontSize:'clamp(42px,5vw,68px)', fontWeight:700, letterSpacing:'-0.04em', lineHeight:1, margin:0, background:'linear-gradient(135deg,var(--text) 0%,var(--accent) 100%)', WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent', backgroundClip:'text'}}>
              Intelligence Report
            </h1>
            <div style={{marginTop:12, height:1, background:'linear-gradient(90deg,var(--accent-30),var(--accent-10),transparent)', borderRadius:'var(--radius-sm)'}}/>
          </div>
        </motion.div>
        {/* Body */}
        <div style={{flex:1, overflow:'hidden', display:'flex', gap:0}}>
          {/* Left Metrics */}
          <motion.div initial={{opacity:0, x:-20}} animate={{opacity:1, x:0}} transition={{delay:0.12, ease:[0.16,1,0.3,1]}} style={{width:280, flexShrink:0, overflow:'hidden', borderRight:'1px solid var(--line)', position:'relative'}}>
            <div style={{position:'absolute', inset:0, background:'linear-gradient(180deg,var(--panel) 0%,var(--panel-raised) 100%)', overflow:'hidden'}}>
              <div style={{position:'absolute', bottom:'-30%', right:'-30%', width:400, height:400, clipPath:'circle(50%)', background:'conic-gradient(from 0deg,transparent 60%,var(--accent-10) 75%,transparent 90%)', animation:'orbitSpin 20s linear infinite'}}/>
              <div style={{position:'absolute', top:'30%', left:'50%', transform:'translate(-50%,-50%)', width:200, height:200, clipPath:'circle(50%)', background:'radial-gradient(circle,var(--accent-2-12) 0%,transparent 70%)', filter:'blur(30px)'}}/>
            </div>
            <div style={{position:'relative', padding:'32px 28px', height:'100%', overflow:'auto'}}>
              <div style={{display:'flex', alignItems:'center', gap:8, marginBottom:32}}>
                <div style={{width:28, height:28, borderRadius:'var(--radius-sm)', background:'var(--accent-14)', border:'1px solid var(--accent-30)', display:'flex', alignItems:'center', justifyContent:'center'}}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
                </div>
                <span style={{fontSize:11, fontWeight:700, letterSpacing:'0.14em', textTransform:'uppercase', color:'var(--text-soft)', fontFamily:"'DM Sans',sans-serif"}}>Compression Metrics</span>
              </div>
              <MetricRow label="Source Material Length" value={result.stats.input_words?.toLocaleString()} unit="words" color="var(--accent)" glow="var(--glow)"/>
              <MetricRow label="Conceptual Insights" value={result.stats.bullet_count} unit="points" color="var(--info)" glow="var(--info-30)"/>
              <MetricRow label="Information Compression" value={result.stats.compression_pct} unit="%" color="var(--success)" glow="var(--success-30)"/>
              <div style={{height:1, margin:'8px 0 24px', background:'linear-gradient(90deg,var(--accent-30),transparent)'}}/>
              <div style={{marginBottom:16}}>
                <div style={{fontSize:9, fontWeight:700, letterSpacing:'0.14em', textTransform:'uppercase', color:'var(--text-soft)', marginBottom:8}}>NLP Engine</div>
                <div style={{display:'flex', alignItems:'center', gap:7, padding:'8px 12px', borderRadius:'var(--radius-sm)', background:'var(--success-10)', border:'1px solid var(--success-30)'}}>
                  <div style={{width:6, height:6, clipPath:'circle(50%)', background:'var(--success)', animation:'preloaderPulse 2s ease-in-out infinite'}}/>
                  <span style={{fontSize:11, fontFamily:"'Fira Code',monospace", color:'var(--success)'}}>{result.stats.model}</span>
                </div>
              </div>
              {result.models_available && (
                <div>
                  <div style={{fontSize:9, fontWeight:700, letterSpacing:'0.14em', textTransform:'uppercase', color:'var(--text-soft)', marginBottom:8}}>Available Models</div>
                  <div style={{display:'flex', flexDirection:'column', gap:4}}>
                    {Object.entries(result.models_available).map(([k,v]) => (
                      <div key={k} style={{display:'flex', alignItems:'center', justifyContent:'space-between', padding:'5px 10px', borderRadius:'var(--radius-sm)', background:'var(--panel-raised)', border:'1px solid var(--line)'}}>
                        <span style={{fontSize:11, fontFamily:"'Fira Code',monospace", color:'var(--text-soft)'}}>{k}</span>
                        <div style={{width:6, height:6, clipPath:'circle(50%)', background: v ? 'var(--success)' : 'var(--text-soft)'}}/>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {result.keywords?.length > 0 && (
                <div style={{marginTop:24}}>
                  <div style={{fontSize:9, fontWeight:700, letterSpacing:'0.14em', textTransform:'uppercase', color:'var(--text-soft)', marginBottom:10}}>Key Terms</div>
                  <div style={{display:'flex', flexWrap:'wrap', gap:6}}>
                    {result.keywords.slice(0,12).map((kw,i)=>{
                      const c=KW_COLORS[i%KW_COLORS.length]
                      return (
                        <motion.span key={kw} initial={{opacity:0, scale:0.85}} animate={{opacity:1, scale:1}} transition={{delay:i*0.03}} whileHover={{scale:1.07, y:-1}} style={{fontSize:10, fontWeight:600, padding:'3px 9px', borderRadius:'var(--radius-sm)', background:c.bg, color:'var(--text)', border:`1px solid ${c.border}`, cursor:'default'}}>{kw}</motion.span>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
          {/* Right Executive Insights */}
          <motion.div initial={{opacity:0, x:20}} animate={{opacity:1, x:0}} transition={{delay:0.18, ease:[0.16,1,0.3,1]}} style={{flex:1, overflow:'hidden', display:'flex', flexDirection:'column'}}>
            <div style={{padding:'20px 32px 16px', borderBottom:'1px solid var(--line)', flexShrink:0, background:'var(--panel)'}}>
              <div style={{display:'flex', alignItems:'center', gap:10}}>
                <div style={{width:32, height:32, borderRadius:'var(--radius-sm)', background:'var(--accent-14)', border:'1px solid var(--accent-30)', display:'flex', alignItems:'center', justifyContent:'center'}}>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.8" strokeLinecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                </div>
                <div>
                  <h2 style={{fontFamily:"'Cormorant Garamond',serif", fontSize:22, fontWeight:700, color:'var(--text)', letterSpacing:'-0.03em', margin:0, lineHeight:1.1}}>Executive Insights Matrix</h2>
                  <p style={{fontSize:11, color:'var(--text-soft)', margin:'3px 0 0', fontFamily:"'DM Sans',sans-serif"}}>{result.bullets.length} synthesized insights · ordered by conceptual depth</p>
                </div>
                <div style={{marginLeft:'auto', display:'flex', gap:8}}>
                  <motion.button whileHover={{scale:1.04}} whileTap={{scale:0.97}} onClick={()=>{navigator.clipboard.writeText(result.bullets.map(b=>'• '+b.text).join('\n')); toast.success('Copied!')}} style={{display:'flex', alignItems:'center', gap:6, padding:'6px 14px', borderRadius:'var(--radius-sm)', background:'transparent', border:'1px solid var(--line)', color:'var(--text)', fontSize:11, fontWeight:500, cursor:'pointer'}}>
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                    Copy all
                  </motion.button>
                  <motion.button whileHover={{scale:1.04}} whileTap={{scale:0.97}} onClick={run} style={{display:'flex', alignItems:'center', gap:6, padding:'6px 14px', borderRadius:'var(--radius-sm)', background:'var(--accent)', border:'1px solid var(--accent)', color:'var(--button-text)', fontSize:11, fontWeight:500, cursor:'pointer'}}>
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/></svg>
                    Retry
                  </motion.button>
                </div>
              </div>
            </div>
            <div style={{flex:1, overflowY:'auto', padding:'20px 32px 32px'}}>
              <div style={{display:'flex', flexDirection:'column', gap:12}}>
                {result.bullets.map((b,i)=>{
                  const tag=b.tag||'core'
                  const cfg=TAG_CFG[tag]||TAG_CFG.core
                  return (
                    <motion.div key={i} initial={{opacity:0, y:12, x:-8}} animate={{opacity:1, y:0, x:0}} transition={{delay:i*0.07, ease:[0.16,1,0.3,1]}} whileHover={{x:4, transition:{duration:0.18}}} style={{display:'flex', gap:14, alignItems:'flex-start', padding:'16px 20px', borderRadius:'var(--radius-md)', background:'var(--panel)', border:'1px solid var(--line)', cursor:'default', position:'relative', overflow:'hidden', transition:'border-color 0.2s, background 0.2s'}} onMouseEnter={e=>{e.currentTarget.style.borderColor=cfg.border;e.currentTarget.style.background=cfg.hoverBg}} onMouseLeave={e=>{e.currentTarget.style.borderColor='var(--line)';e.currentTarget.style.background='var(--panel)'}}>
                      <NumberBadge n={i+1} tag={tag}/>
                      <div style={{flex:1, minWidth:0}}>
                        <div style={{display:'flex', alignItems:'center', gap:8, marginBottom:8}}>
                          <Tag tag={tag}/>
                        </div>
                        <p style={{fontSize:14, lineHeight:1.75, color:'var(--text)', margin:0, fontFamily:"'DM Sans',system-ui,sans-serif", fontWeight:400, letterSpacing:'-0.01em'}}>{b.text}</p>
                      </div>
                    </motion.div>
                  )
                })}
                {store.quizQuestions?.length>0 && (
                  <motion.div initial={{opacity:0, y:16}} animate={{opacity:1, y:0}} transition={{delay:result.bullets.length*0.07+0.1, ease:[0.16,1,0.3,1]}} style={{marginTop:28}}>
                    <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:14, paddingBottom:12, borderBottom:'1px solid var(--line)'}}>
                      <div style={{width:28, height:28, borderRadius:'var(--radius-sm)', background:'var(--warn-14)', border:'1px solid var(--warn-30)', display:'flex', alignItems:'center', justifyContent:'center'}}>
                        <span style={{fontSize:13, color:'var(--warn)'}}>✦</span>
                      </div>
                      <h3 style={{fontFamily:"'Cormorant Garamond',serif", fontSize:18, fontWeight:700, color:'var(--text)', letterSpacing:'-0.02em', margin:0}}>Likely Exam Questions</h3>
                      <button onClick={()=>store.setView('quiz')} style={{marginLeft:'auto', fontSize:11, color:'var(--warn)', background:'none', border:'none', cursor:'pointer', fontFamily:"'DM Sans',sans-serif"}}>Take quiz →</button>
                    </div>
                    <div style={{display:'flex', flexDirection:'column', gap:8}}>
                      {store.quizQuestions.map((q,i)=>(
                        <motion.div key={i} initial={{opacity:0, y:8}} animate={{opacity:1, y:0}} transition={{delay:i*0.06+0.1}} whileHover={{x:4, transition:{duration:0.15}}} style={{padding:'14px 18px', borderRadius:'var(--radius-sm)', background:'var(--panel)', border:'1px solid var(--line)', cursor:'pointer', transition:'border-color 0.18s'}} onMouseEnter={e=>e.currentTarget.style.borderColor='var(--warn)'} onMouseLeave={e=>e.currentTarget.style.borderColor='var(--line)'}>
                          <p style={{fontSize:13.5, color:'var(--text)', margin:'0 0 8px', lineHeight:1.65, fontFamily:"'DM Sans',sans-serif"}}>{q.question}</p>
                          <div style={{display:'flex', alignItems:'center', gap:8}}>
                            <span style={{fontSize:9, fontWeight:700, letterSpacing:'0.1em', textTransform:'uppercase', padding:'3px 9px', borderRadius:'var(--radius-sm)', background:q.difficulty==='hard' ? 'color-mix(in srgb,var(--warn) 14%,transparent)' : q.difficulty==='medium' ? 'color-mix(in srgb,var(--accent) 14%,transparent)' : 'color-mix(in srgb,var(--success) 14%,transparent)', color:q.difficulty==='hard' ? 'var(--warn)' : q.difficulty==='medium' ? 'var(--accent)' : 'var(--success)', border:`1px solid ${q.difficulty==='hard' ? 'color-mix(in srgb,var(--warn) 30%,transparent)' : q.difficulty==='medium' ? 'color-mix(in srgb,var(--accent) 30%,transparent)' : 'color-mix(in srgb,var(--success) 30%,transparent)'}`}}>{q.difficulty==='hard' ? '✦ High Yield' : q.difficulty==='medium' ? '◈ Medium' : '◦ Easy'}</span>
                            <span style={{fontSize:10, color:'var(--text-soft)'}}>· MCQ</span>
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  </motion.div>
                )}
              </div>
            </div>
          </motion.div>
        </div>
      </motion.div>
    </>
  )

  /* ══ INPUT VIEW ══ */
  return (
    <>
      <QuizModal/>
      <motion.div initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}} style={{height:'100%', overflow:'auto', display:'flex', flexDirection:'column'}}>
        <AnimatePresence>{store.isProcessing && (<motion.div initial={{scaleX:0}} animate={{scaleX:1}} exit={{opacity:0}} style={{height:2, flexShrink:0, transformOrigin:'left', background:'linear-gradient(90deg,var(--accent),var(--info),var(--success))', boxShadow:'0 0 12px var(--glow)'}} transition={{duration:3.5, ease:'linear'}}/>)}</AnimatePresence>
        <motion.div initial={{opacity:0, y:20}} animate={{opacity:1, y:0}} transition={{ease:[0.16,1,0.3,1]}} style={{padding:'60px 48px 40px', textAlign:'center', position:'relative'}}>
          <div style={{position:'absolute', top:0, left:'50%', transform:'translateX(-50%)', width:600, height:300, clipPath:'circle(50%)', background:'radial-gradient(ellipse,var(--accent-10) 0%,transparent 65%)', filter:'blur(40px)', pointerEvents:'none'}}/>
          {/* SVG decorations omitted for brevity */}
          <motion.div animate={{y:[0,-10,0]}} transition={{duration:4, repeat:Infinity, ease:'easeInOut'}} style={{display:'inline-flex', alignItems:'center', justifyContent:'center', width:68, height:68, borderRadius:'var(--radius-md)', marginBottom:28, background:'linear-gradient(135deg,var(--accent-14),var(--accent-10))', border:'1px solid var(--accent-30)', position:'relative'}}>
            <div style={{position:'absolute', inset:-6, borderRadius:'var(--radius-lg)', border:'1px dashed var(--accent-30)', animation:'orbitSpin 20s linear infinite'}}/>
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
          </motion.div>
          <h2 style={{fontFamily:"'Cormorant Garamond',Georgia,serif", fontSize:'clamp(40px,5vw,64px)', fontWeight:700, letterSpacing:'-0.04em', lineHeight:1, marginBottom:16, background:'linear-gradient(135deg,var(--text) 0%,var(--accent) 100%)', WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent', backgroundClip:'text'}}>AI Workspace</h2>
          <p style={{fontSize:15, color:'var(--text-soft)', maxWidth:460, margin:'0 auto 36px', lineHeight:1.7, fontFamily:"'DM Sans',sans-serif"}}>Upload your lecture notes or paste text to instantly generate intelligent summaries, flashcards, and exam questions.</p>
          <div style={{display:'flex', justifyContent:'center', gap:8, marginBottom:32}}>
            {[['upload','Upload File'],['paste','Paste Text']].map(([mode,label])=>(
              <motion.button key={mode} whileHover={{scale:1.03}} whileTap={{scale:0.97}} onClick={()=>store.setInputMode(mode)} style={{padding:'9px 22px', borderRadius:'var(--radius-sm)', fontSize:13, fontWeight:500, cursor:'pointer', fontFamily:"'DM Sans',sans-serif", background: store.inputMode===mode ? 'var(--accent)' : 'transparent', border: store.inputMode===mode ? '1px solid var(--accent)' : '1px solid var(--line)', color: store.inputMode===mode ? 'var(--button-text)' : 'var(--text)', boxShadow:'none' }}>{label}</motion.button>
            ))}
          </div>
        </motion.div>
        {/* Content omitted for brevity */}
      </motion.div>
    </>
  )
}

export default WorkspacePage;

import { create } from 'zustand'
import DEMO_QUESTIONS from '../data/demoQuestions.js'
import { selectSampleQuizQuestions } from '../utils/quizValidation.js'

const DEMO = {
  bullets:[
    {text:"NLP pipelines use tokenization, POS tagging, and named entity recognition as essential preprocessing steps before applying downstream transformer models.",tag:"core"},
    {text:"TF-IDF weighs term relevance across a corpus by balancing local frequency with inverse document occurrence — the foundation of keyword extraction.",tag:"concept"},
    {text:"Transformer architectures like BERT and GPT use multi-head self-attention mechanisms, enabling contextual understanding across long token sequences.",tag:"advanced"},
    {text:"Fine-tuning a pre-trained model on domain-specific data significantly improves task performance without training from scratch on large corpora.",tag:"applied"},
    {text:"ROUGE scores measure summarization quality by comparing n-gram overlap between machine-generated and reference human summaries.",tag:"eval"},
    {text:"Extractive summarization selects key sentences verbatim; abstractive generates new condensed sentences preserving semantic meaning.",tag:"key"},
  ],
  keywords:["Transformer","NLP","Self-attention","TF-IDF","ROUGE","BERT","Fine-tuning","Tokenization","Abstractive","Extractive","POS Tagging","GPT","spaCy","Embeddings","Corpus","Neural Network"],
  stats:{input_words:847,bullet_count:6,compression_pct:82,model:"bart-large-cnn"},
  flashcards:[
    {id:1,question:"What is self-attention in transformer models?",answer:"A mechanism allowing each token to attend to all others in a sequence, computing weighted context representations without recurrence or convolution.",type:"definition"},
    {id:2,question:"What does TF-IDF stand for?",answer:"Term Frequency–Inverse Document Frequency. It weights the importance of a term in a document relative to a corpus, used in keyword extraction.",type:"definition"},
    {id:3,question:"What does ROUGE measure?",answer:"N-gram overlap between machine-generated and reference summaries. ROUGE-1, ROUGE-2, and ROUGE-L are common variants used in NLP evaluation.",type:"definition"},
    {id:4,question:"Extractive vs Abstractive summarization?",answer:"Extractive selects existing sentences verbatim from source; abstractive generates new sentences that may not appear in the original text.",type:"comparison"},
    {id:5,question:"What is fine-tuning in NLP?",answer:"Adapting a pre-trained language model on a smaller, domain-specific dataset to improve task-specific performance without training from scratch.",type:"definition"},
    {id:6,question:"What is tokenization in NLP?",answer:"The process of splitting raw text into individual units (tokens) such as words, subwords, or characters as the first preprocessing step.",type:"definition"},
  ],
}

export const useNoteStore = create((set,get) => ({
  inputText:'', uploadedFile:null, documentId:null, documentTitle:'', isProcessing:false,
  activeTab:'text', activeView:'summarize',
  result:null, flashcards:[], quizQuestions:[], quizHistory:[], quizMessage:'',
  quizMode:null, sampleQuizUsedIds:[],
  currentFlashcard:0, flashcardFlipped:false,
  quizOpen:false, quizAnswer:null,
  quizQuestionCount:5,
  preloaderDone:false,
  options:{bullets:true,keywords:true,examQs:true},
  selectedModel:'auto', bulletCount:6, backendOnline:true,

  setInputText:(t)=>set({inputText:t}),
  setUploadedFile:(f)=>set({uploadedFile:f}),
  setDocumentId:(id)=>set(s=>({documentId:id, ...(s.documentId !== id ? {quizHistory:[],quizMessage:''} : {})})),
  setDocumentTitle:(t)=>set({documentTitle:t}),
  setProcessing:(v)=>set({isProcessing:v}),
  setActiveTab:(t)=>set({activeTab:t}),
  setActiveView:(view)=>{
    if (view === get().activeView) return
    if (typeof window !== 'undefined') {
      const route = view === 'flashcards' ? '/flashcards' : view === 'quiz' ? '/knowledge' : view === 'chat' ? '/chat' : '/'
      window.history.pushState({ ...window.history.state, notebotView: view }, '', route)
    }
    set({activeView:view})
  },
  setResult:(r)=>set({result:r}),
  setFlashcards:(f)=>set({flashcards:f,currentFlashcard:0,flashcardFlipped:false}),
  setQuizMessage:(message)=>set({quizMessage:message || ''}),
  setQuizQuestionCount:(count)=>set({quizQuestionCount:Math.min(15,Math.max(1,Number(count) || 5))}),
  setQuizQuestions:(q, mode='pdf')=>set(s=>({
    quizQuestions:q,
    quizMode:mode,
    ...(Array.isArray(q) && q.length > 0 ? {quizMessage:''} : {}),
    quizHistory: Array.from(new Set([
      ...(s.quizHistory || []),
      ...(Array.isArray(q) ? q.map(item => typeof item === 'string' ? item : item?.question).filter(Boolean) : [])
    ]))
  })),
  setPreloaderDone:(v)=>set({preloaderDone:v}),
  setSelectedModel:(m)=>set({selectedModel:m}),
  setBulletCount:(c)=>set({bulletCount:c}),
  setBackendOnline:(v)=>set({backendOnline:v}),
  nextFlashcard:()=>set(s=>({currentFlashcard:(s.currentFlashcard+1)%Math.max(s.flashcards.length,1),flashcardFlipped:false})),
  prevFlashcard:()=>set(s=>({currentFlashcard:(s.currentFlashcard-1+Math.max(s.flashcards.length,1))%Math.max(s.flashcards.length,1),flashcardFlipped:false})),
  flipFlashcard:()=>set(s=>({flashcardFlipped:!s.flashcardFlipped})),
  setQuizOpen:(v)=>set({quizOpen:v,quizAnswer:null}),
  setQuizAnswer:(a)=>set({quizAnswer:a}),
  toggleOption:(k)=>set(s=>({options:{...s.options,[k]:!s.options[k]}})),
  reset:()=>set({inputText:'',uploadedFile:null,documentId:null,documentTitle:'',result:null,flashcards:[],quizQuestions:[],quizHistory:[],quizMessage:'',quizMode:null,sampleQuizUsedIds:[],currentFlashcard:0,flashcardFlipped:false}),
  startSampleQuiz:()=>{
    const state=get()
    const usedIds=state.quizMode === 'sample' ? state.sampleQuizUsedIds : []
    const previousIds=state.quizMode === 'sample' ? state.quizQuestions.map(question=>question.id) : []
    const remaining=DEMO_QUESTIONS.filter(question=>!usedIds.includes(question.id))
    const questions=selectSampleQuizQuestions(DEMO_QUESTIONS,{count:5,usedIds,previousIds})
    const cycleUsedIds=remaining.length < 5
      ? questions.map(question=>question.id)
      : [...usedIds,...questions.map(question=>question.id)]
    set({
      result:{bullets:DEMO.bullets,keywords:DEMO.keywords,stats:DEMO.stats},
      flashcards:DEMO.flashcards,
      quizQuestions:questions,
      quizHistory:questions.map(question=>question.question),
      quizMessage:'',
      quizMode:'sample',
      sampleQuizUsedIds:cycleUsedIds,
    })
  },
  loadDemo:()=>get().startSampleQuiz(),
  getDemoQuestions:()=>DEMO_QUESTIONS,
}))

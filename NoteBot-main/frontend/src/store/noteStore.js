import { create } from 'zustand'

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
  quizQuestions:[
    {id:1,question:"What does TF-IDF stand for and what is it primarily used for?",options:["Token Frequency — Inverse Document Flow","Term Frequency — Inverse Document Frequency","Text Feature — Indexed Data Format","Token Field — Integrated Data Fusion"],correct:"Term Frequency — Inverse Document Frequency",difficulty:"medium"},
    {id:2,question:"Which evaluation metric is most commonly used for text summarization systems?",options:["BLEU","ROUGE","F1-Score","Perplexity"],correct:"ROUGE",difficulty:"easy"},
    {id:3,question:"What core architecture does BERT use as its foundation?",options:["Recurrent Neural Network","LSTM","Transformer","Convolutional Neural Network"],correct:"Transformer",difficulty:"easy"},
    {id:4,question:"What distinguishes abstractive summarization from extractive summarization?",options:["It is faster","It generates new sentences rather than selecting existing ones","It uses less memory","It only works on short texts"],correct:"It generates new sentences rather than selecting existing ones",difficulty:"medium"},
    {id:5,question:"What is the primary advantage of self-attention over traditional RNN-based sequence modeling?",options:["Less computation","Parallel processing of all positions without sequential dependency","Smaller model size","Works only on short inputs"],correct:"Parallel processing of all positions without sequential dependency",difficulty:"hard"},
  ]
}

export const useNoteStore = create((set,get) => ({
  inputText:'', uploadedFile:null, documentId:null, documentTitle:'', isProcessing:false,
  activeTab:'text', activeView:'summarize',
  result:null, flashcards:[], quizQuestions:[],
  currentFlashcard:0, flashcardFlipped:false,
  quizOpen:false, quizAnswer:null,
  preloaderDone:false,
  options:{bullets:true,keywords:true,examQs:true},
  selectedModel:'auto', bulletCount:6, backendOnline:true,

  setInputText:(t)=>set({inputText:t}),
  setUploadedFile:(f)=>set({uploadedFile:f}),
  setDocumentId:(id)=>set({documentId:id}),
  setDocumentTitle:(t)=>set({documentTitle:t}),
  setProcessing:(v)=>set({isProcessing:v}),
  setActiveTab:(t)=>set({activeTab:t}),
  setActiveView:(v)=>set({activeView:v}),
  setResult:(r)=>set({result:r}),
  setFlashcards:(f)=>set({flashcards:f}),
  setQuizQuestions:(q)=>set({quizQuestions:q}),
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
  reset:()=>set({inputText:'',uploadedFile:null,documentId:null,documentTitle:'',result:null,flashcards:[],quizQuestions:[],currentFlashcard:0,flashcardFlipped:false}),
  loadDemo:()=>set({result:{bullets:DEMO.bullets,keywords:DEMO.keywords,stats:DEMO.stats},flashcards:DEMO.flashcards,quizQuestions:DEMO.quizQuestions}),
  getDemoQuestions:()=>DEMO.quizQuestions,
}))

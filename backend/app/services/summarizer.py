"""
NLP Services: summarization and keyword extraction via lightweight TF-IDF.
Heavy transformer libraries have been removed to improve deployment suitability.
"""
import re
import math
from collections import Counter

_STOPWORDS = set(
    "a an the and or but in on at to for of with is are was were be been being have has had do does did will would could should may might shall that this these those it its we our they their i me my he she him her you your".split()
)

def _tokenize(text: str):
    return re.findall(r"[a-z]+", text.lower())

def _tfidf_keywords(text: str, top_n: int = 16) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return []
    doc_freq: Counter = Counter()
    tf_per_sent = []
    for s in sentences:
        tokens = [t for t in _tokenize(s) if t not in _STOPWORDS and len(t) > 3]
        tf_per_sent.append(Counter(tokens))
        doc_freq.update(set(tokens))
    N = len(sentences)
    scores: Counter = Counter()
    for tf in tf_per_sent:
        for word, freq in tf.items():
            idf = math.log((N + 1) / (doc_freq[word] + 1))
            scores[word] += freq * idf
    return [w.title() for w, _ in scores.most_common(top_n)]

def _extractive_summary(text: str, bullet_count: int = 6) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [s for s in sentences if len(s.split()) > 8]
    if not sentences:
        return [text[:400]]
    words = [t for t in _tokenize(text) if t not in _STOPWORDS and len(t) > 3]
    word_freq = Counter(words)
    def score(s):
        return sum(word_freq.get(t, 0) for t in _tokenize(s) if t not in _STOPWORDS)
    ranked = sorted(sentences, key=score, reverse=True)
    return [s for s in ranked[:bullet_count]]

def _assign_tag(sentence: str) -> str:
    s = sentence.lower()
    if any(w in s for w in ["define", "is a", "refers to", "means"]): return "concept"
    if any(w in s for w in ["model", "bert", "gpt", "neural", "transformer"]): return "advanced"
    if any(w in s for w in ["applied", "use case", "practical", "real-world"]): return "applied"
    if any(w in s for w in ["evaluate", "metric", "score", "measure", "rouge", "bleu"]): return "eval"
    if any(w in s for w in ["key", "important", "essential", "critical", "fundament"]): return "key"
    return "core"

def chunk_text(text: str, max_chunk_words: int = 400) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks = []
    current_chunk = []
    current_length = 0
    
    for s in sentences:
        words = len(s.split())
        if current_length + words > max_chunk_words and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [s]
            current_length = words
        else:
            current_chunk.append(s)
            current_length += words
            
    if current_chunk:
        chunks.append(" ".join(current_chunk))
        
    return chunks

def summarize(text: str, method: str = "auto", bullet_count: int = 6) -> dict:
    input_words = len(text.split())
    text = re.sub(r"\s+", " ", text).strip()  # normalize whitespace

    bullets = _extractive_summary(text, bullet_count)
    model_name = "tfidf-extractive"

    bullet_objs = [{"text": s.strip(), "tag": _assign_tag(s)} for s in bullets if s.strip()]
    keywords = _tfidf_keywords(text)
    compression = round((1 - len(" ".join(bullets).split()) / max(input_words, 1)) * 100)

    return {
        "bullets": bullet_objs,
        "keywords": keywords,
        "stats": {
            "input_words": input_words,
            "bullet_count": len(bullet_objs),
            "compression_pct": max(0, min(99, compression)),
            "model": model_name
        }
    }

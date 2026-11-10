# Changes

## Completed phases

### Phase 1 — Database and document persistence

- Connected SQLAlchemy records to document uploads, conversations, messages, flashcards, quizzes, and attempts.
- Added relational models and Alembic migrations; MySQL is configured with `DATABASE_URL`.
- Added page citations to stored messages and review tracking to flashcards.

### Phase 2 — Authentication and authorization

- Implemented registration, login, current-user/profile, JWT expiry, and server-side logout revocation.
- Protected document processing, generation, chat, review, and quiz-attempt routes; operations enforce user ownership.
- Integrated frontend authentication, token persistence, protected application access, and sign-out.

### Phases 3–4 — Gemini and embeddings

- Centralized model calls in `gemini_service.py` using Google Gen AI SDK and Gemini 2.5 Flash, with timeout, quota/error handling, and structured response validation.
- Routed flashcard, quiz, and chat generation through Gemini; removed obsolete provider code.
- Added lazy, process-wide `all-MiniLM-L6-v2` embeddings and removed the approximate low-dimensional fallback.

### Phases 5–6 — ChromaDB and PDF processing

- Replaced active SQLite vector retrieval with persistent ChromaDB, user/document-scoped similarity search, reindexing, and vector cleanup.
- Added a one-time legacy SQLite vector import that re-embeds text with MiniLM; unmapped records remain unavailable to scoped retrieval.
- Preserved PDF pages through extraction and paragraph/sentence-aware 1,000-character chunks with 200-character overlap.
- Persisted processing status, handled empty/scanned PDFs, and added owned document deletion.

### Phases 7–10 — Chat, study tools, and frontend

- Added authenticated multi-conversation RAG chat with persisted messages and page citations.
- Added flashcard topic, difficulty, source-page metadata, persistent near-duplicate prevention, shuffle, and per-card review tracking.
- Added validated four-option quizzes, configurable set sizes, scoring and explanations, and persistent per-answer attempts/history.
- Connected these workflows to the existing React interface without a visual redesign.

## Validation completed

- Full backend suite: **66 passed**.
- Frontend tests: **15 passed**; Vite production build succeeded.
- An isolated SQLite `flask db upgrade` and `flask db check` completed with no schema differences.
- The real MiniLM model was previously exercised and produced normalized 384-dimensional vectors.

## Remaining verification / deployment notes

- A live MySQL connection and production database upgrade have not been verified; migration validation used isolated SQLite.
- The existing legacy SQLite vector index was not imported into a production Chroma store during this work.
- Live Gemini quota/network behavior and deployed frontend/backend operation require deployment credentials and infrastructure.
- Existing deprecation warnings include `datetime.utcnow()` defaults elsewhere in the models and chatbot route.

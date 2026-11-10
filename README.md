# NoteBot — Premium AI Notes Platform

NoteBot turns study material into concise summaries, flashcards, and quizzes. It pairs a React and Vite frontend with a Flask API, persistent document indexing, and Gemini-powered generation.

## Overview

Students often have to turn long lecture notes and documents into practical revision material. NoteBot provides a single workspace to extract text, review key points, and create study aids grounded in an uploaded or pasted source.

### Objectives

- Reduce the effort required to prepare study material.
- Keep generated questions and cards tied to the source document.
- Support local development without requiring paid AI credentials.
- Keep deployment split between a static frontend and a lightweight Python API.

### Features

- Upload PDF, TXT, and Markdown files, or paste text.
- Extract text from PDFs and index it for later retrieval.
- Create extractive summaries, keywords, and compression statistics.
- Generate document-grounded flashcards and multiple-choice quizzes.
- Sign in to manage owned documents, cited chatbot conversations, and study history.
- Shuffle and track flashcard reviews; save quiz answers, scores, and answer explanations.
- Fall back to local heuristic generation when LLM generation is unavailable.
- Export summaries and study material to PDF.
- Responsive React interface with route navigation, loading states, and health checks.

## Technology stack

| Area | Technologies |
| --- | --- |
| Frontend | React 18, Vite, Tailwind CSS, Framer Motion, Zustand |
| UI and requests | Lucide React, React Dropzone, React Hot Toast, Axios, clsx |
| Backend | Python 3.10+, Flask, Flask-CORS, Flask-SQLAlchemy, Flask-Migrate, Flask-JWT-Extended, PyMySQL, python-dotenv, Gunicorn |
| Documents and export | PyMuPDF, ReportLab |
| AI and retrieval | Google Gen AI SDK (Gemini 2.5 Flash), Sentence Transformers (`all-MiniLM-L6-v2`), ChromaDB |
| Tests | pytest, Node.js built-in test runner |

## AI and document architecture

### Summarization

The current summarizer is a lightweight extractive TF-IDF implementation. It selects sentences from the input and ranks keywords locally; summarization does **not** call an LLM.

### Gemini generation

Flashcard and quiz generation now use the Google Gen AI SDK with `gemini-2.5-flash`. Set `GEMINI_API_KEY` in the backend environment. Requests have a configurable timeout, bounded retry handling, quota/rate-limit errors, and JSON response validation. Local source-grounded generators remain available when Gemini is unavailable.

Embeddings use the locally loaded Sentence Transformers `all-MiniLM-L6-v2` model for both indexing and retrieval queries. The model is loaded once per backend process. If it is unavailable, indexing and retrieval return explicit errors rather than creating approximate vectors.

### RAG architecture

When a document is uploaded or pasted, the backend creates a relational document record, chunks its extracted text, creates embeddings, and stores chunks in the persistent `notebot_documents` ChromaDB collection. Retrieval filters by both document and user. Flashcards and quiz questions are persisted in the relational database and associated with the document. Generation requests retrieve source chunks and build the Gemini prompt. Generated responses are validated, with a local fallback available for generation failures.

The vector database is runtime data, not a checked-in dataset. It is excluded from Git and stored under `CHROMA_PERSIST_DIRECTORY`. Existing `backend/.vector_store.db` indexes are imported into Chroma on first access, with legacy chunk text re-embedded using `all-MiniLM-L6-v2`. Ownership is associated from relational document records when available. Records whose owners cannot be resolved remain unavailable to user-scoped retrieval until reindexed.

### Relational persistence and migrations

The backend uses SQLAlchemy and Flask-Migrate for users, documents, conversations, messages, flashcards, quizzes, attempts, and revoked JWTs. Uploads, generated content, chat history, flashcard reviews, and quiz attempts are persisted. Protected API operations enforce user ownership.

Set `DATABASE_URL` to a MySQL connection string before running migrations. Apply the schema from the backend directory with `python -m flask --app run db upgrade`. `NOTEBOT_AUTO_CREATE_SCHEMA` is intended only for isolated tests; production schema changes should use migrations.

### PDF processing workflow

1. The upload route accepts PDF, TXT, or Markdown files.
2. PyMuPDF extracts text from PDF pages; text files are decoded as UTF-8.
3. Empty or unreadable documents are rejected. Image-only PDFs are not OCR-processed.
4. Extracted text is chunked, embedded, and indexed in ChromaDB for retrieval.
5. The frontend can request a summary and use the document ID for flashcards and quizzes.

### Quiz generation workflow

The quiz endpoint retrieves document chunks and asks Gemini for validated four-option questions. Question count is configurable up to 15. Correct answers and explanations are reviewed in the existing UI; each authenticated answer is persisted and can be retrieved from the user's quiz history. If Gemini generation fails, a local source-grounded generator is used and the endpoint reports which path ran.

### Flashcard generation workflow

The flashcard endpoint retrieves indexed document chunks and requests source-grounded cards from Gemini, including topic, difficulty, and supported PDF page references. Saved cards are deduplicated; revealing an answer records a review. The existing card UI supports navigation and shuffle. If Gemini generation fails, a local heuristic extractor remains available.

### Chat workflow

Authenticated users can create multiple conversations for their documents, send follow-up questions, and revisit stored message history. Responses use document-scoped RAG context and include validated source-page citations; questions unsupported by retrieved context are handled as unanswerable.

### PDF export workflow

The export endpoint uses ReportLab to create a downloadable PDF from provided summaries, keywords, flashcards, and quiz questions.

### System architecture

```mermaid
flowchart LR
    Browser[React frontend] -->|HTTP and JSON| API[Flask API]
    Browser -->|PDF, TXT, or Markdown| Upload[Upload and extraction]
    Upload --> API
    API --> Summary[TF-IDF extractive summarizer]
    Upload --> Chunk[Text chunking]
    Chunk --> Embeddings[Sentence Transformers]
    Chunk --> Store[(ChromaDB)]
    Store --> Retrieve[RAG retrieval]
    Retrieve --> Generation[Quiz and flashcard generation]
    Generation -->|Configured provider| LLM[Gemini 2.5 Flash]
    Generation -->|Fallback| LocalGen[Local heuristic generation]
    API --> Export[ReportLab PDF export]
    Summary --> Browser
    Generation --> Browser
    Export --> Browser
```

## Project structure

```text
.
├── backend/
│   ├── app/
│   │   ├── routes/       # Upload, summary, quiz, cards, export, and admin APIs
│   │   └── services/     # PDF/text processing, RAG, generation, and validation
│   ├── tests/
│   ├── .env.example
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── public/
│   ├── screenshots/
│   ├── src/
│   │   ├── components/
│   │   ├── data/
│   │   ├── pages/
│   │   ├── store/
│   │   ├── styles/
│   │   └── utils/
│   ├── tests/
│   ├── .env.example
│   └── package.json
├── render.yaml
└── README.md
```

## Local setup

### Prerequisites

- Node.js 18 or newer and npm.
- Python 3.10 or newer.
- A Gemini API key for hosted generation; Sentence Transformers downloads `all-MiniLM-L6-v2` on first use.

### Backend

From the repository root, create and activate a virtual environment, install dependencies, and create the local environment file.

**Windows PowerShell**

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

**macOS or Linux**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `backend/.env` as needed, then start the API:

```bash
python -m flask --app run db upgrade
python run.py
```

The backend listens on `http://localhost:5000` by default. `PORT` can override the port.

### Frontend

In a second terminal:

```bash
cd frontend
npm install
```

Optionally create `frontend/.env.local` from the example. For local development, the configured API base URL should be `http://localhost:5000`.

```powershell
Copy-Item .env.example .env.local
npm run dev
```

The Vite development server is available at `http://localhost:5173`.

### Environment variables

The backend reads `backend/.env`; the Vite frontend reads its own environment file. Keep real credentials out of both files in Git.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy connection string; configure MySQL for deployments |
| `NOTEBOT_AUTO_CREATE_SCHEMA` | Test-only switch for creating tables without migrations |
| `UPLOAD_FOLDER` | Private filesystem location for uploaded source files |
| `CHROMA_PERSIST_DIRECTORY` | Persistent ChromaDB data directory |
| `GEMINI_API_KEY` | Backend credential for Gemini generation |
| `GEMINI_TIMEOUT_SECONDS` | Gemini request timeout; default is 45 seconds |
| `RAG_TOP_K` | Maximum retrieval context size |
| `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` | Document chunking parameters |
| `ADMIN_API_KEY` | Optional key for protected administrative routes |
| `VITE_API_URL` | Frontend API origin; use the backend origin, without a trailing `/api` |

Templates are provided at `backend/.env.example` and `frontend/.env.example`. The frontend variable is public at build time; never put API keys or other secrets in `VITE_*` variables.

## API overview

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Backend health check |
| `POST` | `/api/auth/register` | Register a user and issue a JWT |
| `POST` | `/api/auth/login` | Authenticate and issue a JWT |
| `GET` | `/api/auth/me` | Return the authenticated user's profile |
| `POST` | `/api/auth/logout` | Revoke the current JWT |
| `POST` | `/api/upload/` | Upload a PDF, TXT, or Markdown file |
| `POST` | `/api/upload/text/` | Index pasted text |
| `DELETE` | `/api/documents/<doc_id>` | Delete an owned document and its ChromaDB vectors |
| `POST` | `/api/summarize/` | Generate an extractive summary and keywords |
| `POST` | `/api/flashcards/` | Generate cards from an indexed document ID |
| `POST` | `/api/flashcards/<card_id>/review` | Record a review for an owned flashcard |
| `POST` | `/api/quiz/` | Generate questions from an indexed document ID |
| `POST` | `/api/quiz/attempts` | Save an answer and return correctness/explanation |
| `GET` | `/api/quiz/attempts?doc_id=<doc_id>` | List the authenticated user's quiz attempts |
| `GET` / `POST` | `/api/chat/conversations` | List or create owned conversations |
| `GET` / `POST` | `/api/chat/conversations/<id>/messages` | Read history or send a chat message |
| `POST` | `/api/export/pdf` | Export study content to PDF |

Administrative routes are defined in `backend/app/routes/admin.py`; configure `ADMIN_API_KEY` before exposing administrative actions.

## Tests and build

Run the frontend tests and production build:

```bash
cd frontend
npm test
npm run build
```

Run the backend test suite from the backend directory:

```bash
cd backend
python -m pytest -q tests
```

This runs the backend unit tests in `backend/tests`. The separate `backend/test_rag_integration.py` script targets a running local API and requires the optional `requests` package; it is not part of this pytest command. Automated generation tests mock provider responses; successful local-fallback tests are not live-provider integration tests.

## Deployment

- **Backend:** the root `render.yaml` describes the Render web service. Configure runtime secrets and model settings in Render's environment settings rather than committing them.
- **Frontend:** deploy the `frontend/` directory to Vercel, using `npm run build` and `dist` as the output directory. Set `VITE_API_URL` to the deployed backend origin.
- **SPA routing:** `frontend/vercel.json` and `frontend/public/_redirects` provide single-page-app rewrites for supported static hosts.
- **CORS:** the current Flask app uses a permissive CORS configuration. Restrict allowed origins to the deployed frontend before using the API publicly.
- **Persistence:** relational records use `DATABASE_URL`; uploaded files and the ChromaDB index use filesystem storage. Configure durable database and filesystem storage before deploying.

Deployment configuration in the repository does not establish that a live Render or Vercel deployment is currently available or healthy.

## Screenshots

Representative UI captures are available in [`frontend/screenshots/`](frontend/screenshots/).

### Workspace

![NoteBot workspace](frontend/screenshots/Final-Workspace-1357.png)

### Flashcards

![NoteBot flashcards](frontend/screenshots/Responsive-Flashcards-1357.png)

## Future enhancements

- Add OCR for scanned and image-only PDFs.
- Add OCR for scanned and image-only PDFs.
- Restrict CORS and add API rate limits for public deployments.
- Verify MySQL connectivity and production migrations; tests currently use isolated SQLite.
- Import and validate the legacy vector index against a deployed relational database and Chroma store.
- Use managed/durable storage for production uploads and vector data.
- Add live-provider integration tests and accessible end-to-end coverage across desktop and mobile layouts.
- Add accessible end-to-end tests across desktop and mobile layouts.

## Contributing

Open an issue to discuss a bug or proposed change, then submit a focused pull request with relevant tests and setup notes. Do not include private documents, generated vector databases, environment files, or credentials in contributions.

## License

There is currently no `LICENSE` file in this repository. Until a license is selected and added, the project is not explicitly licensed for reuse or redistribution. Choose a license before accepting external contributions or publishing this as an open-source package.

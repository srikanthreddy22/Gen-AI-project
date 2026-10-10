# NoteBot Premium

NoteBot is a study assistant for turning raw notes, PDFs, and lecture text into concise summaries, flashcards, and quizzes. The app combines a React frontend with a Flask backend and uses a lightweight local summarization pipeline plus optional OpenAI-powered RAG generation for richer study outputs.

## What the project does

- Upload a PDF, TXT, or MD file and extract readable text
- Paste raw study text directly into the workspace
- Generate structured study bullets with keywords and compression stats
- Build flashcards from uploaded content
- Generate multiple-choice quiz questions from the same source material
- View the app in a dark glassmorphism UI with animated layouts and live backend health status

## Tech stack

### Frontend
- React 18
- Vite
- Tailwind CSS
- Framer Motion
- Zustand
- React Dropzone
- Axios

### Backend
- Python 3.10+
- Flask
- Flask-CORS
- python-dotenv
- PyMuPDF
- ReportLab
- OpenAI Python SDK
- NumPy
- pytest

## Current architecture

The app is organized like this:

```text
NoteBot-main/
├── backend/
│   ├── app/
│   │   ├── routes/
│   │   │   ├── admin.py
│   │   │   ├── export.py
│   │   │   ├── flashcards.py
│   │   │   ├── quiz.py
│   │   │   ├── summarize.py
│   │   │   └── upload.py
│   │   ├── services/
│   │   │   ├── generation_service.py
│   │   │   ├── openai_service.py
│   │   │   ├── rag_service.py
│   │   │   ├── summarizer.py
│   │   │   ├── validation_service.py
│   │   │   └── vector_store.py
│   │   └── __init__.py
│   ├── tests/
│   ├── .env.example
│   ├── requirements.txt
│   ├── run.py
│   └── verify_rag_architecture.py
├── frontend/
│   ├── src/
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── postcss.config.js
├── README.md
└── .gitignore
```

## Prerequisites

- Node.js 18 or newer
- Python 3.10 or newer

## Setup

### 1) Backend

```bash
cd backend
python -m venv venv
```

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

macOS / Linux:

```bash
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Update `.env` with your values. At minimum, set `OPENAI_API_KEY` if you want the RAG-backed generation features:

```env
OPENAI_API_KEY=your_key_here
OPENAI_GENERATION_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
RAG_TOP_K=8
ADMIN_API_KEY=optional_admin_key
```

Start the backend:

```bash
python run.py
```

The API runs at:

```text
http://localhost:5000
```

### 2) Frontend

Open a second terminal and run:

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

The app runs at:

```text
http://localhost:5173
```

## API endpoints

The current backend exposes these routes:

- `GET /api/health` — health check
- `POST /api/upload/` — upload PDF/TXT/MD and extract text
- `POST /api/summarize` — generate summary bullets and keywords
- `POST /api/flashcards/` — generate flashcards from the indexed document
- `POST /api/quiz/` — generate multiple-choice questions from the indexed document
- `POST /api/export/pdf` — export generated study content as a PDF (if enabled in the app flow)
- Admin endpoints under `/api` for document reindexing and maintenance

## Notes on generation behavior

- The default summarizer uses a TF-IDF extractive pipeline in `backend/app/services/summarizer.py`.
- The application also includes an OpenAI + RAG generation service for flashcards and quizzes when `OPENAI_API_KEY` is configured.
- If the key is missing, the app can still run in local demo mode, but AI-generated content features will not be fully available.

## Testing

The backend includes a test suite under `backend/tests`.

```bash
cd backend
source venv/bin/activate   # or .\venv\Scripts\Activate.ps1 on Windows
pytest
```

## License

This project is intended for study and educational use. Add your preferred license before production deployment.

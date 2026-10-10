<div align="center">

<img src="assets/banner.svg" alt="NoteBot banner" width="100%"/>

<br/>

[![Python](https://img.shields.io/badge/Python-3.10%2B-0f0c0a?style=for-the-badge&logo=python&logoColor=C9A063&labelColor=1C1612)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18-0f0c0a?style=for-the-badge&logo=react&logoColor=61DAFB&labelColor=1C1612)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-5-0f0c0a?style=for-the-badge&logo=vite&logoColor=A78BFA&labelColor=1C1612)](https://vitejs.dev/)
[![Flask](https://img.shields.io/badge/Flask-3-0f0c0a?style=for-the-badge&logo=flask&logoColor=EFE5CF&labelColor=1C1612)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-C9A063?style=for-the-badge&labelColor=1C1612)](LICENSE)

</div>

---

## ✨ What is NoteBot?

NoteBot is a study platform for students. Upload a lecture PDF or paste your notes, and it condenses the material into the points that matter, builds flashcards for active recall, and writes practice questions from the same text.

The summarizer is not tied to one service. It runs a **cascade of five NLP models**, from a hosted LLM down to a fully offline method, so it still produces results when an API key is missing or a network call fails.

<!-- Add a screen recording at assets/demo.gif and uncomment the block below.
<div align="center">
  <img src="assets/demo.gif" alt="NoteBot demo" width="85%"/>
</div>
-->

---

## 🎨 Features

<table>
<tr>
<td width="50%" valign="top">

### 📄 Document ingestion
Upload **PDF or TXT** files up to 32 MB, or paste text directly. PDF extraction falls back through three engines, so scanned and unusual layouts still work.

`PyMuPDF → pdfplumber → PDFMiner`

</td>
<td width="50%" valign="top">

### 🧠 Multi-model summaries
Choose a model or leave it on **Auto**:

- 🟣 GPT-4o-mini *(needs API key)*
- 🟠 BART-large-CNN
- 🟢 LSA extractive (sumy)
- 🔵 spaCy + TF-IDF
- ⚪ NLTK frequency *(fully offline)*

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🃏 Flashcards
Generated from your material. Flip with a click or the **Space** key, move with the arrow keys, and track your position.

</td>
<td width="50%" valign="top">

### 🎯 Quiz mode
Multiple-choice questions with **instant feedback** and an explanation for every answer. Finish with a score and a retry.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 📑 PDF export
Download a formatted report of your summary, key terms, and insights.

</td>
<td width="50%" valign="top">

### 🎬 Polished interface
Cinematic preloader, rotating study-themed backgrounds with smooth crossfades, and motion that respects *reduced-motion* settings.

</td>
</tr>
</table>

---

## 🏗️ How it works

```mermaid
flowchart LR
    A["📄 Upload or paste"] --> B["🔍 Extract text<br/>PyMuPDF → pdfplumber → PDFMiner"]
    B --> C{"🧠 Summarizer<br/>cascade"}
    C -->|"API key set"| D["🟣 GPT-4o-mini"]
    C -->|"fallback"| E["🟠 BART-large"]
    E -->|"fallback"| F["🟢 LSA"]
    F -->|"fallback"| G["🔵 spaCy + TF-IDF"]
    G -->|"fallback"| H["⚪ NLTK frequency"]
    D --> I["📝 Summary"]
    E --> I
    F --> I
    G --> I
    H --> I
    I --> J["🃏 Flashcards"]
    I --> K["🎯 Quiz"]
    I --> L["📑 PDF export"]

    classDef step fill:#1C1612,stroke:#C9A063,color:#EFE5CF,stroke-width:1.5px
    classDef out fill:#C9A063,stroke:#C9A063,color:#120E0B,stroke-width:1.5px
    class A,B,C,D,E,F,G,H step
    class I,J,K,L out
```

---

## 🧰 Tech stack

<table>
<tr>
<td align="center" width="50%"><h4>🖥️ Frontend</h4>

![React](https://img.shields.io/badge/React_18-61DAFB?style=flat-square&logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat-square&logo=vite&logoColor=white)
![Tailwind](https://img.shields.io/badge/Tailwind-38BDF8?style=flat-square&logo=tailwindcss&logoColor=white)
![Framer Motion](https://img.shields.io/badge/Framer_Motion-0055FF?style=flat-square&logo=framer&logoColor=white)
![Zustand](https://img.shields.io/badge/Zustand-443E38?style=flat-square)

</td>
<td align="center" width="50%"><h4>⚙️ Backend & AI</h4>

![Flask](https://img.shields.io/badge/Flask-000000?style=flat-square&logo=flask&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=flat-square&logo=openai&logoColor=white)
![Hugging Face](https://img.shields.io/badge/HuggingFace-FFD21E?style=flat-square&logo=huggingface&logoColor=black)
![spaCy](https://img.shields.io/badge/spaCy-09A3D5?style=flat-square&logo=spacy&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?style=flat-square&logo=scikitlearn&logoColor=white)
![NLTK](https://img.shields.io/badge/NLTK-154F3C?style=flat-square)

</td>
</tr>
</table>

---

## 📁 Project structure

```
notebot/
├── 🐍 backend/
│   ├── app/
│   │   ├── routes/          upload · process · export · health
│   │   └── services/
│   │       ├── nlp/         model cascade
│   │       └── pdf/         extraction cascade
│   ├── requirements.txt
│   └── run.py
├── ⚛️  frontend/
│   ├── src/
│   │   ├── components/      logo · preloader · background · layout · modals
│   │   ├── pages/           workspace · flashcards · quiz
│   │   ├── store/           Zustand state
│   │   └── utils/api.js     API client
│   └── package.json
└── assets/                  banner.svg · logo.svg · demo.gif
```

---

## 🚀 Quick start

<details open>
<summary><b>1️⃣ Clone the repository</b></summary>

```bash
git clone https://github.com/srikanthreddy22/notebot.git
cd notebot
```
</details>

<details open>
<summary><b>2️⃣ Start the backend</b></summary>

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python run.py
```

The API runs at **http://localhost:5000**.
</details>

<details open>
<summary><b>3️⃣ Start the frontend</b></summary>

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.
</details>

<details>
<summary><b>🔑 Optional: environment variables</b></summary>

Create `backend/.env`:

```env
# Enables the GPT-4o-mini model. Without it, the cascade uses local models.
OPENAI_API_KEY=sk-...

MAX_UPLOAD_MB=32
```
</details>

---

## 🔌 API

| Method | Endpoint | Purpose |
|:--:|---|---|
| 🟢 `GET` | `/health` | Backend status and available models |
| 🔵 `POST` | `/upload` | Upload PDF or TXT, return extracted text |
| 🔵 `POST` | `/process/summarize` | Summarize with a chosen model and bullet count |
| 🔵 `POST` | `/process/flashcards` | Generate flashcards |
| 🔵 `POST` | `/process/quiz` | Generate multiple-choice questions |
| 🟠 `POST` | `/export/pdf` | Download a PDF report |

```bash
curl -X POST http://localhost:5000/process/summarize \
  -H "Content-Type: application/json" \
  -d '{"text": "Photosynthesis converts light energy into chemical energy...", "model": "auto", "bullet_count": 5}'
```

---

## 🗺️ Roadmap

- [ ] 🔁 Spaced-repetition scheduling for flashcards
- [ ] 📚 DOCX and EPUB input
- [ ] 📈 Study sessions and progress tracking
- [ ] 🐳 One-command Docker Compose setup

---

## 🤝 Contributing

Contributions are welcome.

```bash
git checkout -b feature/your-feature
git commit -m "Add your feature"
git push origin feature/your-feature
```

Then open a pull request.

---

## 👨‍💻 Author

**Singareddy Venkata Srikanth Reddy**
B.Tech Computer Science Engineering · Kalasalingam University

[![GitHub](https://img.shields.io/badge/GitHub-srikanthreddy22-181717?style=flat-square&logo=github)](https://github.com/srikanthreddy22)

---

<div align="center">

**📜 License:** MIT · see [LICENSE](LICENSE)

</div>

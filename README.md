# AstroVed AI Chatbot 🕉️

A modern, full-stack AI astrological consultation platform and customer support inbox built from scratch for AstroVed.

## Architecture & Tech Stack

- **Frontend**: React 19 + TypeScript + Vite
  - Styled with custom responsive CSS (Deep Indigo & Temple Gold palette, typography pairing Cinzel & Plus Jakarta Sans).
  - Public Seeker Welcome Form (Lead intake: Name, Email, Phone, Consultation Focus).
  - Real-time Interactive Chat Interface with planetary prompt suggestions.
  - Internal Astrologer Dashboard with live conversation inbox, seeker dossier, and live reply controls.
- **Backend**: FastAPI + Python 3.14+
  - Package & virtualenv management strictly via `uv`.
  - Public `/api/chat/*` endpoints for seeker engagement.
  - Secured `/api/agent/*` endpoints protected via `x-agent-key` header to ensure private customer leads and transcripts are never exposed to public chat endpoints.
  - Domain-aware Vedic Astrological mock responder for Career (10th house), Relationships (7th house), Health, Wealth, and Sade Sati when `OPENAI_API_KEY` is not provided.
  - Seamless OpenAI API integration via `.env` configuration.
  - In-memory data store with MongoDB-ready schema contracts.
- **Deployment Target**: Render

---

## Directory Structure

```
ai-chatbot/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── endpoints.py      # Public chat & Internal agent routes
│   │   ├── core/
│   │   │   └── config.py         # Pydantic Settings
│   │   ├── schemas/
│   │   │   └── chat.py           # Pydantic models (Leads, Messages, Sessions)
│   │   ├── services/
│   │   │   ├── llm.py            # OpenAI + Vedic Astrology Mock engine
│   │   │   └── store.py          # Session and lead store
│   │   └── main.py               # FastAPI entrypoint & CORS middleware
│   ├── tests/
│   │   └── test_api.py           # Pytest test suite
│   ├── pyproject.toml            # uv project definition
│   └── uv.lock
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── WelcomeForm.tsx   # Seeker lead capture form
│   │   │   ├── ChatInterface.tsx # Vedic consultation chat window
│   │   │   └── AgentDashboard.tsx# Internal astrologer inbox & controls
│   │   ├── App.tsx               # Primary container & view toggle
│   │   ├── api.ts                # Frontend API client
│   │   ├── index.css             # Theme & component styling
│   │   ├── main.tsx              # React DOM entrypoint
│   │   └── types.ts              # TypeScript interfaces
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── .env.example
├── .gitignore
└── README.md
```

---

## Getting Started

### 1. Prerequisites
- [uv](https://docs.astral.sh/uv/) installed: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Node.js (v18+) & npm

### 2. Backend Setup
```bash
cd backend
# Install dependencies
uv sync

# Run tests
PYTHONPATH=. uv run pytest tests/

# Start FastAPI dev server (Port 8000)
uv run uvicorn app.main:app --reload --port 8000
```
- Swagger API Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/api/health`

### 3. Frontend Setup
```bash
cd frontend
# Install dependencies
npm install

# Start Vite dev server (Port 5173 with proxy to backend)
npm run dev

# Or build for production
npm run build
```
- Open browser: `http://localhost:5173`

---

## Key Features & Security

1. **Lead Intake & Session Continuity**:
   Every consultation initiates with Seeker Name, Email, and Mobile number.
2. **AI & Mock Fallback**:
   If no OpenAI API key is configured, the system automatically answers with authentic Vedic Astrology insights across Career, Relationships, Wealth, and Saturn/Sade Sati queries.
3. **Internal Agent Separation**:
   Customer chats only access their own session (`/api/chat/{id}/messages`). The full inbox, customer dossiers, and status change endpoints reside under `/api/agent/*` guarded by the internal agent key (`astro-agent-secret-token`).
4. **Live Human Takeover**:
   Internal astrologers can reply directly to any consultation from the Agent Desk. Sending an agent message places the session into advisor handling mode.

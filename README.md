# AstroVed AI Chatbot 🕉️

A modern, full-stack AI astrological consultation platform, RAG knowledge assistant, and live advisor desk built for AstroVed.

---

## 1. Quick Start

### Prerequisites
- Python 3.14+ with [uv](https://docs.astral.sh/uv/) installed: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Node.js (v18+) & npm

### One-Command Local Development Startup

Start both FastAPI and the Vite dev server with a single command from the project root:

```bash
# 1. Ensure dependencies are installed (one-time setup)
cd backend && uv sync && cd ../frontend && npm install && cd ..

# 2. Configure environment (copy example)
cp .env.example .env
# Edit .env to set your MongoDB URI and OpenAI API Key

# 3. Launch both backend & frontend concurrently
uv run python run.py
```

- **Frontend (Vite Dev Server)**: `http://127.0.0.1:5173`
- **Backend (FastAPI)**: `http://127.0.0.1:8000`
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`
- **Health Check**: `http://127.0.0.1:8000/api/health`

Press `Ctrl+C` in the terminal to cleanly terminate both processes. If either server terminates unexpectedly, the launcher automatically halts the other process.

---

## 2. Environment Variables & Configuration

The project uses a single canonical environment file at `/opt/ai-chatbot/.env`. The backend settings module and launcher load this file directly regardless of current working directory.

| Variable | Default (Dev) | Description |
|---|---|---|
| `APP_ENV` | `development` | Set to `production` in production environments. |
| `API_MODE` | `full` | Backend operating mode (`full` or `api-only`). |
| `HOST` | `127.0.0.1` | Host address for servers (use `0.0.0.0` on Render/cloud). |
| `BACKEND_PORT` | `8000` | Port for the FastAPI backend. |
| `FRONTEND_PORT` | `5173` | Port for the Vite development server. |
| `PORT` | `8000` | Cloud dynamic port override (provided automatically by Render). |
| `CORS_ORIGINS` | `*` | Allowed CORS origins (comma-separated or `*`). |
| `MONGODB_URI` | `mongodb://127.0.0.1:27017/` | MongoDB connection URI (Atlas SRV or local). |
| `MONGODB_DATABASE` | `astroved-chatbot` | Active MongoDB database name. |
| `JWT_SECRET` | `development-jwt-secret...` | Secret key for agent auth tokens (min 32 chars in prod). |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm. |
| `JWT_EXPIRE_MINUTES` | `720` | Token expiration time (12 hours). |
| `OPENAI_API_KEY` | *(empty / placeholder)* | OpenAI API key for RAG responses (mock fallback if empty). |
| `OPENAI_MODEL` | `gpt-4o-mini` | Chat model for astrological responses. |
| `OPENAI_EMBEDDING_MODEL`| `text-embedding-3-small`| Model used for knowledge embeddings. |

---

## 3. Development vs. Production Behavior

### Development Mode (`uv run python run.py`)
- Runs **two processes concurrently**:
  - FastAPI backend on `HOST:BACKEND_PORT` with `--reload`.
  - Vite dev server on `HOST:FRONTEND_PORT` with Hot Module Replacement (HMR).
- Vite proxies `/api` and Server-Sent Events (SSE) requests directly to `http://HOST:BACKEND_PORT`.
- Secret variables (`OPENAI_API_KEY`, `MONGODB_URI`, `JWT_SECRET`) remain strictly server-side and are never exposed to Vite or client bundles.

### Production Mode (`uv run python run.py --prod`)
- Runs **a single unified service**:
  - FastAPI handles all `/api/*` REST endpoints and real-time SSE streams (`/api/conversations/{id}/events`).
  - FastAPI serves the pre-compiled React SPA assets from `frontend/dist/` and falls back to `index.html` for client-side routing.
  - Vite is **not** run in production.
- **One-time requirement before production start**:
  The production bundle must be compiled before starting in production mode:
  ```bash
  cd frontend && npm run build
  cd ..
  uv run python run.py --prod
  ```
  If `frontend/dist` is missing, the launcher halts with a clear notice instructing you to run `npm run build`.

---

## 4. Render Deployment Guide

To deploy AstroVed Chatbot as a single web service on [Render](https://render.com/):

### Service Settings
- **Environment**: `Python 3`
- **Build Command**:
  ```bash
  npm --prefix frontend install && npm --prefix frontend run build && uv sync --project backend
  ```
- **Start Command**:
  ```bash
  uv run python run.py --prod
  ```
  *(Alternative direct start: `uv run --project backend uvicorn app.main:app --host 0.0.0.0 --port $PORT`)*

### Render Environment Variables
Configure the following in the Render Dashboard (**Environment** tab):
- `APP_ENV`: `production`
- `HOST`: `0.0.0.0`
- `MONGODB_URI`: `mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority`
- `MONGODB_DATABASE`: `astroved-chatbot`
- `JWT_SECRET`: *(Strong 64-character secret, see below)*
- `OPENAI_API_KEY`: `sk-...`
- `CORS_ORIGINS`: `*` (or your custom domain)

Render automatically provides the `PORT` variable, which both `run.py` and FastAPI read dynamically.

---

## 5. Security & Best Practices

### Strong JWT Secret Configuration
In production mode (`APP_ENV=production`), the application enforces strict JWT security. It will fail to start if the JWT secret is shorter than 32 characters or uses insecure defaults.

Generate a cryptographically secure key:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```
Place this value in `JWT_SECRET` in `.env` (locally) and in your Render environment variables.

### MongoDB Atlas Network Access
If using MongoDB Atlas:
1. Log in to the [MongoDB Atlas Console](https://cloud.mongodb.com/).
2. Navigate to **Security** -> **Network Access**.
3. Click **Add IP Address**.
4. For cloud deployments like Render (which use dynamic outbound IPs), add `0.0.0.0/0` ("Allow Access from Anywhere") or configure private endpoints if using enterprise peering.
5. In **Database Access**, ensure your database user has read/write privileges to `astroved-chatbot`.

### Secret File Protection (`.env`)
- `.env` files contain sensitive credentials and must **never** be committed to Git.
- Both project-level and backend `.gitignore` rules prevent `.env`, `.env.*`, and secret files from being committed:
  ```
  .env
  .env.*
  backend/.env
  ```
- Only commit `.env.example`, keeping actual values replaced with placeholders.

---

## 6. Agent Management CLI

To securely manage astrologer/advisor accounts in MongoDB:

```bash
# Add, list, activate, or reset passwords for agents:
uv run --project backend python backend/scripts/manage_agents.py
```
Passwords are encrypted using Argon2id with memory-hard cost parameters.

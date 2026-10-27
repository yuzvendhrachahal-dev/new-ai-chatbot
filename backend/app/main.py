import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.core.config import settings
from app.api.endpoints import api_router
from app.core.database import check_mongo_connection, init_db_indexes

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup verification: verify MongoDB and create indexes
    try:
        status = check_mongo_connection()
        init_db_indexes()
        logger.info("MongoDB connection verified (%s): %s", settings.MONGODB_DATABASE, status)
    except Exception as err:
        logger.error("CRITICAL: MongoDB is unavailable on startup: %s", err)
        raise RuntimeError(f"Startup aborted: MongoDB is unavailable: {err}") from err
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AstroVed AI Chatbot backend with MongoDB persistence, real-time SSE, Argon2id agent auth, and RAG knowledge foundations.",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

# Production frontend SPA static serving
FRONTEND_DIST_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if (FRONTEND_DIST_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST_DIR / "assets")), name="assets")

@app.get("/")
async def root():
    index_file = FRONTEND_DIST_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return {
        "message": "Welcome to AstroVed AI Chatbot API",
        "docs": "/docs",
        "health": f"{settings.API_V1_STR}/health",
        "frontend": "Frontend production build not found at frontend/dist. Run 'cd frontend && npm run build' for production single-service hosting."
    }

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path in ("docs", "redoc", "openapi.json"):
        return None
    if FRONTEND_DIST_DIR.is_dir():
        target_file = FRONTEND_DIST_DIR / full_path
        if target_file.is_file():
            return FileResponse(target_file)
        index_file = FRONTEND_DIST_DIR / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
    return {
        "message": "AstroVed AI Chatbot Backend",
        "status": "online",
        "docs": "/docs",
        "health": f"{settings.API_V1_STR}/health",
        "frontend": "Frontend production build not found at frontend/dist. Run 'cd frontend && npm run build' for production single-service hosting."
    }

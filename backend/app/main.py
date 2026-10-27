import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

@app.get("/")
def root():
    return {
        "message": "Welcome to AstroVed AI Chatbot API",
        "docs": "/docs",
        "health": f"{settings.API_V1_STR}/health"
    }

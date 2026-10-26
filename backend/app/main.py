from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.endpoints import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AstroVed AI Chatbot backend with public seeker conversation endpoints and internal agent support inbox.",
    version="1.0.0"
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

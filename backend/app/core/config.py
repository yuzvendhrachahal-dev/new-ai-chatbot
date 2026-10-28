import os
import json
from pathlib import Path
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Canonical root .env location
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent  # /opt/ai-chatbot
ROOT_ENV = ROOT_DIR / ".env"
BACKEND_ENV = ROOT_DIR / "backend" / ".env"

# Load environment from root .env first as canonical source of truth
if ROOT_ENV.exists():
    load_dotenv(dotenv_path=ROOT_ENV, override=True)
elif BACKEND_ENV.exists():
    load_dotenv(dotenv_path=BACKEND_ENV, override=True)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=(str(ROOT_ENV), str(BACKEND_ENV), ".env"),
        extra="ignore"
    )

    PROJECT_NAME: str = "AstroVed AI Chatbot"
    API_V1_STR: str = "/api"

    # Environment & Mode
    APP_ENV: str = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower()
    API_MODE: str = os.getenv("API_MODE", "full")

    # Host & Port Settings
    HOST: str = os.getenv("HOST", "127.0.0.1")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", os.getenv("PORT", "8000")))
    FRONTEND_PORT: int = int(os.getenv("FRONTEND_PORT", "5173"))

    # Backwards-compatible aliases
    @property
    def ENVIRONMENT(self) -> str:
        return self.APP_ENV

    @property
    def PORT(self) -> int:
        return self.BACKEND_PORT

    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    # RAG Knowledge Retrieval Configuration (default: false)
    RAG_ENABLED: bool = os.getenv("RAG_ENABLED", "false").lower() in ("true", "1", "yes")

    # MongoDB Configuration
    MONGODB_URI: str = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI") or "mongodb://127.0.0.1:27017/"
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", os.getenv("MONGODB_DB_NAME", "astroved-chatbot"))

    # Backwards-compatible alias
    @property
    def MONGODB_DB_NAME(self) -> str:
        return self.MONGODB_DATABASE

    # JWT Agent Authentication
    JWT_SECRET: str = os.getenv("JWT_SECRET", "astroved-super-secret-jwt-key-2026-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "720"))

    INTERNAL_AGENT_KEY: str = os.getenv("INTERNAL_AGENT_KEY", "astro-agent-secret-token")
    CORS_ORIGINS: Union[List[str], str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            v = v.strip()
            if v == "*" or not v:
                return ["*"]
            if v.startswith("[") and v.endswith("]"):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return parsed
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    def model_post_init(self, __context):
        # Enforce strong JWT secret in production
        if self.APP_ENV == "production":
            insecure_keys = [
                "astroved-super-secret-jwt-key-2026-production",
                "secret",
                "changeme",
                "your-secret-key-here"
            ]
            if not self.JWT_SECRET or self.JWT_SECRET in insecure_keys or len(self.JWT_SECRET) < 32:
                raise ValueError(
                    "CRITICAL: A secure, strong JWT_SECRET (at least 32 characters) must be configured in production environment."
                )

settings = Settings()

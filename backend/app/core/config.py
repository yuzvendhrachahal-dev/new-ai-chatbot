import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", extra="ignore")

    PROJECT_NAME: str = "AstroVed AI Chatbot"
    API_V1_STR: str = "/api"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    # MongoDB Configuration
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017/")
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
    CORS_ORIGINS: list[str] = ["*"]

settings = Settings()

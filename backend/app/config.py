from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.embedding_config import EMBEDDING_DIMENSIONS

_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    database_url: str

    google_api_key: str
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_fallback_models: list[str] = Field(
        default_factory=lambda: ["gemini-3.8-flash", "gemini-3.6-flash"]
    )
    gemini_embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = Field(
        default=EMBEDDING_DIMENSIONS,
        ge=EMBEDDING_DIMENSIONS,
        le=EMBEDDING_DIMENSIONS,
    )
    retrieval_candidate_k: int = 50
    retrieval_top_k: int = 8
    retrieval_rrf_k: int = 60
    retrieval_neighbor_radius: int = 1
    retrieval_fts_config: Literal["english", "simple"] = "english"

    # Comma-separated in .env; use `cors_origins` for the parsed list.
    allowed_origins: str = "http://localhost:5173"

    @computed_field
    @property
    def sqlalchemy_database_url(self) -> str:
        """Normalize Supabase-style URLs for SQLAlchemy + psycopg v3."""
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        return url

    @computed_field
    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.allowed_origins.split(",")
            if origin.strip()
        ]


settings = Settings()

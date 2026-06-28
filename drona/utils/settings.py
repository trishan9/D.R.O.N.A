"""
D.R.O.N.A. runtime settings loaded from environment / .env file.

All configuration lives here - no other module should read os.environ directly.
Settings are validated by Pydantic on first import; bad config fails fast.

Usage:
    from drona.utils.settings import settings
    print(settings.ollama_model)
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DronaSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # ignore unknown env vars (Docker, CI, etc.)
    )

    # --- Logging ---
    log_level: str = Field("INFO", description="Minimum log level")
    log_file: str | None = Field("logs/drona.log", description="Rotating log file path")

    # --- Data paths ---
    data_dir: Path = Field(Path("data"))
    data_raw_dir: Path = Field(Path("data/raw"))
    data_processed_dir: Path = Field(Path("data/processed"))
    data_manual_dir: Path = Field(Path("data/manual_collection"))

    # --- LLM (Ollama) ---
    ollama_host: str = Field("http://localhost:11434")
    # Primary = Qwen2.5-3B: faster on modest hardware, robust to typos/spelling,
    # and strong multilingual (Nepali/code-switch). Still local, no API cost.
    ollama_model: str = Field("qwen2.5:3b-instruct-q4_K_M")
    ollama_fallback_model: str = Field(
        "phi3.5:3.8b-mini-instruct-q4_K_M",
        description="Fallback if the primary model isn't loaded; still local, no API cost.",
    )
    llm_max_tokens: int = Field(1024, ge=64, le=4096)  # = Ollama num_predict cap
    llm_temperature: float = Field(0.3, ge=0.0, le=2.0)
    # "Fast mode" knobs: keep the model resident between requests (avoids the
    # multi-second cold reload) and bound the KV-cache context window.
    ollama_keep_alive: str = Field("30m", description="How long Ollama keeps the model loaded.")
    ollama_num_ctx: int = Field(4096, ge=512, le=32768)

    # --- Embeddings ---
    curriculum_embed_model: str = Field("BAAI/bge-small-en-v1.5")
    career_embed_model: str = Field("TechWolf/JobBERT-v2")
    reranker_model: str = Field("BAAI/bge-reranker-base")

    # --- Vector store ---
    # Backend selector lets dev run on local ChromaDB while prod/thesis demo
    # can switch to pgvector or Pinecone without touching call sites.
    vector_backend: Literal["chroma", "pgvector", "pinecone"] = Field("chroma")
    chroma_dir: Path = Field(Path("data/chromadb"))
    chroma_collection_prefix: str = Field("drona")

    # --- PostgreSQL 16 + pgvector ---
    postgres_dsn: str = Field(
        "postgresql+psycopg://drona:drona@localhost:5432/drona",
        description="SQLAlchemy DSN for Postgres+pgvector (matches docker-compose).",
    )

    # --- Pinecone (managed cloud vector store, optional) ---
    pinecone_api_key: str | None = Field(default=None)
    pinecone_environment: str = Field("us-east-1")
    pinecone_index_curriculum: str = Field("drona-curriculum")
    pinecone_index_career: str = Field("drona-career")

    # --- Google Gemini (OFFLINE USE ONLY - synthetic gen + eval sets) ---
    gemini_api_key: str | None = Field(default=None)
    gemini_model: str = Field("gemini-1.5-flash")
    # Hard guard: code asserts this is False before any request-path LLM call.
    allow_gemini_in_request_path: bool = Field(
        False,
        description="MUST stay False - preserves the local-only advising claim.",
    )

    # --- Google Vertex AI Agent Builder (optional, default OFF) ---
    enable_vertex_agent: bool = Field(False)
    vertex_project_id: str | None = Field(default=None)
    vertex_location: str = Field("us-central1")

    # --- FastAPI backend ---
    api_host: str = Field("0.0.0.0")
    api_port: int = Field(8000, ge=1, le=65535)
    api_cors_origins: str = Field("http://localhost:3000")

    # --- Retrieval ---
    retrieval_top_k: int = Field(20, ge=1, le=100)
    rerank_top_k: int = Field(5, ge=1, le=20)
    hybrid_dense_weight: float = Field(0.6, ge=0.0, le=1.0)
    hybrid_bm25_weight: float = Field(0.4, ge=0.0, le=1.0)

    # --- Tier boosts (anti-anchoring: Nepal data weighted higher) ---
    tier_nepal_boost: float = Field(1.5, ge=1.0)
    tier_regional_boost: float = Field(1.1, ge=1.0)
    tier_international_boost: float = Field(1.0, ge=1.0)
    tier_synthetic_penalty: float = Field(0.7, gt=0.0, le=1.0)

    # --- Session / orchestrator ---
    session_timeout_s: float = Field(
        8.0,
        description="Seconds without engagement before session times out.",
        ge=1.0,
    )
    perception_interval_s: float = Field(
        0.1,
        description="Seconds between perception ticks.",
        ge=0.01,
    )

    # --- Scraper behaviour ---
    scraper_requests_per_second: float = Field(
        0.5,
        description="Max requests/sec per portal. 0.5 = 2s gap between requests.",
        ge=0.1,
        le=2.0,
    )
    scraper_timeout_seconds: int = Field(15, ge=5, le=60)
    scraper_user_agent: str = Field(
        "DRONAResearchBot/0.1 (BSc thesis; contact: trisan.wagle@softwarica.edu.np)"
    )

    @field_validator("hybrid_dense_weight", "hybrid_bm25_weight", mode="before")
    @classmethod
    def _weights_are_floats(cls, v: str | float) -> float:
        return float(v)

    def tier_boost(self, tier: str) -> float:
        """Return the score multiplier for a given tier string."""
        return {
            "nepal": self.tier_nepal_boost,
            "regional": self.tier_regional_boost,
            "international": self.tier_international_boost,
            "synthetic": self.tier_synthetic_penalty,
        }.get(tier.lower(), 1.0)

    def ensure_dirs(self) -> None:
        """Create all configured data directories if they don't exist."""
        for d in (self.data_dir, self.data_raw_dir, self.data_processed_dir,
                  self.data_manual_dir, self.chroma_dir):
            d.mkdir(parents=True, exist_ok=True)


# Module-level singleton - import this everywhere
settings = DronaSettings()

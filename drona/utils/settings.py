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

    # --- LLM backend selection ---
    # "ollama" (default): GGUF via local Ollama - fastest on CPU-only boxes.
    # "transformers": weights directly from Hugging Face (incl. the LoRA
    # adapter, no GGUF conversion) - best on any CUDA GPU. Both local (C4).
    llm_backend: str = Field("ollama", pattern="^(ollama|transformers)$")
    hf_model: str = Field("Qwen/Qwen3-4B-Instruct-2507")
    hf_adapter_path: Path = Field(Path("models/advising-lora"))
    hf_load_4bit: bool = Field(True, description="4-bit NF4 on GPU; ignored on CPU.")

    # --- Remote advising brain (robot deployment) ---
    # When set, the robot stops running the engine in-process and becomes a thin
    # client against a GPU-served advising API (e.g. the Colab T4 notebook, or a
    # deployed server). Empty = run the engine locally.
    #   ADVISOR_REMOTE_URL=https://xyz.trycloudflare.com
    # Rationale: the robot's SBC cannot hold ChromaDB + a cross-encoder + a 4B
    # LLM, but it can make one HTTP call. See drona/advising/remote.py.
    advisor_remote_url: str = Field(
        "", description="Base URL of a remote advising API; empty = run locally."
    )

    # --- LLM (Ollama) ---
    ollama_host: str = Field("http://localhost:11434")
    # Primary = Qwen3-4B-Instruct-2507: the strongest ~4B open instruct model
    # (Apache-2.0), still fast at Q4 on modest hardware. Fallback = Qwen2.5-3B
    # (lighter, strong multilingual/Nepali). Both local, no API cost.
    ollama_model: str = Field("qwen3:4b-instruct-2507-q4_K_M")
    ollama_fallback_model: str = Field(
        "qwen2.5:3b-instruct-q4_K_M",
        description="Fallback if the primary model isn't loaded; still local, no API cost.",
    )
    # Ceiling on generated tokens (Ollama num_predict / HF max_new_tokens).
    # Sized for NEPALI: Devanagari is very token-dense - measured ~1.7 chars per
    # token, so 2048 tokens bought only ~3.5k chars and cut a 3-pathway answer off
    # mid-JSON (unparseable). 3072 completes it. Only a ceiling: English answers
    # stop around 600-800 tokens regardless, so this costs them nothing.
    llm_max_tokens: int = Field(3072, ge=64, le=4096)
    llm_temperature: float = Field(0.3, ge=0.0, le=2.0)
    # "Fast mode" knobs: keep the model resident between requests (avoids the
    # multi-second cold reload) and bound the KV-cache context window.
    ollama_keep_alive: str = Field("30m", description="How long Ollama keeps the model loaded.")
    ollama_num_ctx: int = Field(4096, ge=512, le=32768)

    # --- Bilingual advising (English + Nepali) ---
    # advisor_language: 'auto' detects Nepali (Devanagari) vs English per query;
    # 'en'/'ne' force one. When Nepali is served, the query is routed to a
    # Nepali-specialised model (Himalaya Gemma) while retrieval stays shared, so
    # answers are grounded in the same Softwarica curriculum in either language.
    advisor_language: str = Field(
        "auto", pattern="^(auto|en|ne)$",
        description="Language to advise in: auto|en|ne.",
    )
    # Himalaya Gemma (Nepali) served via Ollama. Pull the Q4_K_M quant (~3.4 GB) -
    # the bare tag resolves to the bf16 build (9.3 GB) which needs > 4 GB VRAM and
    # crashes when split across GPU/CPU (Gemma-3n GGML_SCHED assert):
    #   ollama pull hf.co/himalaya-ai/himalaya-gemma-4-e2b-it-gguf:Q4_K_M
    # Fits fully on a T4 (fast); on a 4 GB laptop it runs but slowly (CPU offload).
    nepali_ollama_model: str = Field(
        "hf.co/himalaya-ai/himalaya-gemma-4-e2b-it-gguf:Q4_K_M",
        description="Ollama model id for Nepali advising (Himalaya Gemma GGUF, Q4_K_M).",
    )
    # Which cognitive-bias detector the advising pipeline uses.
    #
    #   rules   regex only.  P=1.000 R=0.511 F1=0.645 on held-out v2, ~0 ms.
    #   hybrid  rules union retrieval-augmented LLM with verified evidence spans.
    #           P=0.917 R=0.633 F1=0.731, 0/8 false positives, ~4 s per query.
    #
    # "hybrid" is the default because recall matters here: a missed bias is advice
    # that quietly reinforces it. It degrades to "rules" automatically whenever the
    # LLM is unavailable, so no deployment loses bias detection entirely - it just
    # loses the extra recall. Set to "rules" on latency-critical or offline robots.
    # See scripts/benchmark_bias_detectors.py for the full comparison.
    bias_detector: str = Field(
        "hybrid",
        pattern="^(rules|hybrid)$",
        description="Bias detector: rules (regex only) or hybrid (rules + RAG LLM).",
    )
    # Character budget for the retrieved context, per language. This must leave
    # room INSIDE num_ctx for the system prompt AND a full generated answer:
    #   prompt(system ~1.2k tok + citations) + answer(up to llm_max_tokens) <= num_ctx
    # Nepali is token-dense and its answers are long, so on a 4k-context serve the
    # citation block is kept small (3000 chars ~ 750 tok): 750 + ~1.2k system +
    # ~1.8k answer ~ 3.75k, inside 4096. Raise it when serving with a bigger
    # num_ctx (e.g. on the T4). Too big here truncates the answer -> JSON won't parse.
    nepali_context_char_budget: int = Field(3000, ge=1000, le=40000)
    english_context_char_budget: int = Field(9000, ge=1000, le=60000)

    # --- Embeddings ---
    curriculum_embed_model: str = Field("BAAI/bge-small-en-v1.5")
    career_embed_model: str = Field("TechWolf/JobBERT-v2")
    # v2-m3: measurably better + multilingual (future Nepali queries);
    # ~2x base's CPU latency but rerank runs once per query (LLM dominates).
    reranker_model: str = Field("BAAI/bge-reranker-v2-m3")

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

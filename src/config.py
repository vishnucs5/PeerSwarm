"""
Configuration system for Multi-Agent Research Lab.
Centralized settings management with Pydantic Settings.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelConfig(BaseSettings):
    """Model routing configuration."""
    planner: str = Field(default="gpt-4o", validation_alias=AliasChoices("MODEL_PI", "MODEL_PLANNER"))
    researcher_a: str = "gpt-4o-mini"
    researcher_b: str = "gpt-4o-mini"
    researcher_c: str = "gpt-4o-mini"
    analyst: str = "gpt-4o"
    critic: str = "gpt-4o"
    writer: str = "claude-3-5-sonnet-20241022"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="MODEL_",
        case_sensitive=False,
        extra="ignore",
    )

    def get_model(self, agent_role: str) -> str:
        """Get model for agent role."""
        return getattr(self, agent_role.lower().replace(" ", "_"), self.planner)


class QualityConfig(BaseSettings):
    """Quality evaluation thresholds."""
    threshold: float = Field(default=8.0, ge=0, le=10)
    hard_gate_threshold: float = Field(default=6.0, ge=0, le=10)
    max_iterations: int = Field(default=3, ge=1, le=10)
    token_budget_per_run: int = Field(default=200000, ge=10000)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="QUALITY_",
        case_sensitive=False,
        extra="ignore",
    )


class StorageConfig(BaseSettings):
    """Storage backend configuration."""
    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    chroma_persist_dir: Path = Path("./data/knowledge_base")
    chroma_collection_name: str = "research_findings"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = Field(default="", alias="NEO4J_PASSWORD")
    neo4j_database: str = "neo4j"

    # SQLite
    sqlite_db_path: Path = Path("./data/research_history.db")

    # File storage
    output_dir: Path = Path("./data/outputs")
    cache_dir: Path = Path("./data/cache")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("chroma_persist_dir", "output_dir", "cache_dir", mode="before")
    @classmethod
    def ensure_path(cls, v: str | Path) -> Path:
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @field_validator("sqlite_db_path", mode="before")
    @classmethod
    def ensure_sqlite_parent(cls, v: str | Path) -> Path:
        path = Path(v)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


class APIConfig(BaseSettings):
    """External API keys."""
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    tavily_api_key: str | None = None
    serper_api_key: str | None = None
    arxiv_api_key: str | None = None
    crossref_api_key: str | None = None
    semantic_scholar_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class ObservabilityConfig(BaseSettings):
    """Observability configuration."""
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"
    phoenix_api_key: str | None = None
    phoenix_endpoint: str = "http://localhost:6006"
    sentry_dsn: str | None = None
    sentry_environment: str = "development"
    prometheus_port: int = 9090

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )


class ServerConfig(BaseSettings):
    """Server configuration."""
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    streamlit_port: int = 8501
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"
    log_file: Path | None = Path("./data/logs/app.log")
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("log_file", mode="before")
    @classmethod
    def ensure_log_dir(cls, v: str | Path | None) -> Path | None:
        if v is None:
            return None
        path = Path(v)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


class SecurityConfig(BaseSettings):
    """Security configuration."""
    api_key_enabled: bool = Field(default=False, alias="SECURITY_API_KEY_ENABLED")
    api_keys: list[str] = Field(default_factory=list, alias="SECURITY_API_KEYS")
    secret_key: str | None = Field(default=None, alias="SECURITY_SECRET_KEY")
    encryption_key: str | None = Field(default=None, alias="SECURITY_ENCRYPTION_KEY")
    input_validation_enabled: bool = Field(default=True, alias="SECURITY_INPUT_VALIDATION_ENABLED")
    max_request_body_size: int = Field(default=1048576, alias="SECURITY_MAX_REQUEST_BODY_SIZE")  # 1MB
    allowed_domains: list[str] = Field(default_factory=list, alias="SECURITY_ALLOWED_DOMAINS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",
    )


class FeatureFlags(BaseSettings):
    """Feature flags."""
    enable_ollama: bool = False
    enable_langfuse: bool = True
    enable_phoenix: bool = False
    enable_prometheus: bool = True
    enable_sentry: bool = False
    enable_local_llm: bool = False
    enable_human_in_loop: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ENABLE_",
        case_sensitive=False,
        extra="ignore",
    )


class Settings(BaseSettings):
    """Main application settings."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Sub-configs
    models: ModelConfig = Field(default_factory=ModelConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    api_keys: APIConfig = Field(default_factory=APIConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    features: FeatureFlags = Field(default_factory=FeatureFlags)

    # Flow settings
    flow_max_retries: int = Field(default=2, ge=0, le=5)
    flow_timeout_seconds: int = Field(default=300, ge=30, le=3600)

    # Memory settings
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Knowledge Graph settings
    kg_entity_extraction_model: str = "gpt-4o-mini"
    kg_relation_extraction_model: str = "gpt-4o-mini"

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: [
        "http://localhost:3000",
        "http://localhost:8501",
    ])

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    def validate_required_keys(self) -> list[str]:
        """Validate required API keys are present."""
        missing = []
        if not (
            self.api_keys.openai_api_key
            or self.api_keys.anthropic_api_key
            or self.api_keys.google_api_key
            or self.api_keys.gemini_api_key
            or self.api_keys.groq_api_key
        ):
            missing.append("OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, or GROQ_API_KEY")
        if not self.api_keys.tavily_api_key and not self.api_keys.serper_api_key:
            missing.append("TAVILY_API_KEY or SERPER_API_KEY")
        return missing


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def get_model_for_agent(agent_role: str) -> str:
    """Get model name for agent role."""
    settings = get_settings()
    return settings.models.get_model(agent_role)

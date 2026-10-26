"""Settings loaded from environment variables (prefix TA_) and an optional repo-root .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TA_", env_file=REPO_ROOT / ".env", extra="ignore")

    database_url: str = f"sqlite:///{DATA_DIR / 'app.db'}"
    # Admin routes are refused unless this is set. There is deliberately no default key.
    admin_key: str | None = None
    # Hard cap on cumulative LLM spend per run, in USD.
    llm_budget_usd: float = 5.0
    cors_origins: list[str] = ["http://localhost:5173"]
    runs_dir: Path = DATA_DIR / "runs"

    # Pipeline A goes through OpenRouter for now (a direct Anthropic provider can replace it later).
    # The key is read as OPENROUTER_API_KEY, the name OpenRouter's own tools use.
    openrouter_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("OPENROUTER_API_KEY", "TA_OPENROUTER_API_KEY")
    )
    openrouter_model: str = "anthropic/claude-sonnet-5.5"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Pipeline B: any OpenAI-compatible local server. Defaults to Ollama.
    local_base_url: str = "http://localhost:11434/v1"
    local_model: str = "qwen3.6:latest"

    # A section pair becomes a candidate edge when the cross-references between them reach this.
    edge_min_weight: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()

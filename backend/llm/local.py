"""Pipeline B: a model on this machine behind an OpenAI-compatible endpoint (Ollama etc.)."""

import httpx

from backend.llm.openai_compat import OpenAICompatProvider

DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen3.6:latest"


class LocalProvider(OpenAICompatProvider):
    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.Client | None = None,
        timeout: float = 600.0,  # a first call can include loading a large model into memory
        **kwargs,
    ) -> None:
        super().__init__(
            provider="local",
            model=model,
            base_url=base_url,
            usd_per_token_in=0.0,
            usd_per_token_out=0.0,
            client=client,
            timeout=timeout,
            **kwargs,
        )


def server_reachable(base_url: str = DEFAULT_BASE_URL, timeout: float = 0.5) -> bool:
    try:
        return httpx.get(f"{base_url.rstrip('/')}/models", timeout=timeout).status_code == 200
    except httpx.HTTPError:
        return False

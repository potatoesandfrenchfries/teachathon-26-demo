"""Pipeline A: Claude (or any other hosted model) through OpenRouter."""

import httpx

from backend.llm.openai_compat import OpenAICompatProvider, ProviderError

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "anthropic/claude-sonnet-5.5"


class OpenRouterProvider(OpenAICompatProvider):
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        usd_per_token_in: float | None = None,
        usd_per_token_out: float | None = None,
        client: httpx.Client | None = None,
        **kwargs,
    ) -> None:
        if not api_key:
            raise ProviderError("OPENROUTER_API_KEY is not set (put it in .env or the environment)")
        super().__init__(
            provider="openrouter",
            model=model,
            base_url=base_url,
            api_key=api_key,
            headers={"X-Title": "TeachAThon 2026"},
            extra_body={
                # Ask OpenRouter to report the exact charge in `usage.cost`.
                "usage": {"include": True},
                # Only route to upstream providers that honour response_format.
                "provider": {"require_parameters": True},
            },
            usd_per_token_in=usd_per_token_in,
            usd_per_token_out=usd_per_token_out,
            client=client,
            **kwargs,
        )


def fetch_model_pricing(
    model: str, base_url: str = DEFAULT_BASE_URL, client: httpx.Client | None = None
) -> tuple[float, float]:
    """USD per token (input, output) for a model, from OpenRouter's public model list.

    Needs no API key. Used for dry-run cost estimates.
    """
    http = client or httpx.Client(timeout=30.0)
    try:
        response = http.get(f"{base_url.rstrip('/')}/models")
    except httpx.TransportError as error:
        raise ProviderError(f"openrouter: cannot fetch the model list ({error})") from error
    if response.status_code != 200:
        raise ProviderError(f"openrouter: model list returned HTTP {response.status_code}")
    for entry in response.json().get("data", []):
        if entry.get("id") == model:
            pricing = entry.get("pricing", {})
            return float(pricing.get("prompt", 0)), float(pricing.get("completion", 0))
    raise ProviderError(f"openrouter: no model with id {model!r}")

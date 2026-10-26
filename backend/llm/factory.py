"""Build a provider by name. Pipelines map to providers: A is OpenRouter, B is the local server."""

from backend.llm.base import TextLLM
from backend.llm.fake import FakeProvider
from backend.llm.local import LocalProvider
from backend.llm.openai_compat import ProviderError
from backend.llm.openrouter import OpenRouterProvider
from backend.settings import Settings

PIPELINE_PROVIDERS = {"A": "openrouter", "B": "local"}
PROVIDER_NAMES = ("fake", "openrouter", "local")


def make_provider(
    name: str,
    settings: Settings,
    usd_per_token: tuple[float, float] | None = None,
) -> TextLLM:
    """`usd_per_token` is (input, output) and is only a fallback when the server does not report
    the cost itself."""
    if name == "fake":
        return FakeProvider()
    if name == "openrouter":
        price_in, price_out = usd_per_token or (None, None)
        return OpenRouterProvider(
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
            base_url=settings.openrouter_base_url,
            usd_per_token_in=price_in,
            usd_per_token_out=price_out,
        )
    if name == "local":
        return LocalProvider(model=settings.local_model, base_url=settings.local_base_url)
    raise ProviderError(f"Unknown provider {name!r}. Choose one of {', '.join(PROVIDER_NAMES)}.")

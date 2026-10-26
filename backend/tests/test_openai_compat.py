"""The OpenAI-compatible client, OpenRouter (Pipeline A) and the local provider (Pipeline B)."""

import httpx
import pytest

from backend.llm.base import EdgeClassification, LLMRequest
from backend.llm.estimate import estimate_cost, estimate_tokens
from backend.llm.factory import make_provider
from backend.llm.local import LocalProvider
from backend.llm.openai_compat import (
    OpenAICompatProvider,
    ProviderError,
    StructuredOutputError,
    parse_json_object,
    strict_json_schema,
)
from backend.llm.openrouter import OpenRouterProvider, fetch_model_pricing
from backend.settings import Settings
from backend.tests.http_mock import VALID_EDGE, Recorder, chat_response, ok

REQUEST = LLMRequest(stage="edge", prompt_version="edge-v1", system="Be brief.", user="Classify.")
KEY = "sk-or-secret-key"


def _openrouter(recorder: Recorder, **kwargs) -> OpenRouterProvider:
    return OpenRouterProvider(api_key=KEY, client=recorder.client, sleep=lambda _: None, **kwargs)


# --- Request shape ---------------------------------------------------------------------------


def test_openrouter_request_asks_for_strict_json_and_reports_usage():
    recorder = ok()
    _openrouter(recorder).complete(REQUEST, EdgeClassification)

    (request,) = recorder.requests
    body = recorder.json_bodies()[0]
    assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert request.headers["x-title"] == "TeachAThon 2026"
    assert body["model"] == "anthropic/claude-sonnet-5.5"
    assert body["messages"] == [
        {"role": "system", "content": "Be brief."},
        {"role": "user", "content": "Classify."},
    ]
    assert body["temperature"] == 0
    assert body["usage"] == {"include": True}
    assert body["provider"] == {"require_parameters": True}
    fmt = body["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["name"] == "EdgeClassification"
    assert fmt["json_schema"]["strict"] is True


def test_the_schema_sent_is_strict_and_drops_unsupported_keywords():
    schema = strict_json_schema(EdgeClassification)

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"type", "justification", "confidence"}
    flat = str(schema)
    for keyword in ("minimum", "maximum", "title", "default"):
        assert keyword not in flat
    assert schema["properties"]["type"]["enum"] == ["required", "optional", "none"]


def test_no_system_message_is_sent_when_the_system_prompt_is_empty():
    recorder = ok()
    _openrouter(recorder).complete(
        LLMRequest(stage="edge", prompt_version="v", user="only user"), EdgeClassification
    )
    assert recorder.json_bodies()[0]["messages"] == [{"role": "user", "content": "only user"}]


def test_local_provider_sends_no_credentials_and_no_openrouter_fields():
    recorder = ok()
    provider = LocalProvider(client=recorder.client)
    provider.complete(REQUEST, EdgeClassification)

    assert "authorization" not in recorder.requests[0].headers
    body = recorder.json_bodies()[0]
    assert "usage" not in body and "provider" not in body
    assert (provider.provider, provider.model) == ("local", "qwen3.6:latest")
    assert str(recorder.requests[0].url) == "http://localhost:11434/v1/chat/completions"


# --- Parsing and validation -----------------------------------------------------------------


def test_a_valid_response_becomes_a_typed_result():
    completion = _openrouter(ok()).complete(REQUEST, EdgeClassification)

    assert completion.result == EdgeClassification(**VALID_EDGE)
    assert (completion.provider, completion.model) == ("openrouter", "anthropic/claude-sonnet-5.5")


@pytest.mark.parametrize(
    "text",
    [
        '{"type": "required", "justification": "j", "confidence": 0.5}',
        '```json\n{"type": "required", "justification": "j", "confidence": 0.5}\n```',
        'Sure: {"type": "required", "justification": "j", "confidence": 0.5} Hope that helps!',
    ],
)
def test_json_is_found_inside_a_code_fence_or_prose(text):
    assert parse_json_object(text)["type"] == "required"
    completion = _openrouter(ok(text)).complete(REQUEST, EdgeClassification)
    assert completion.result.confidence == 0.5


@pytest.mark.parametrize(
    "content",
    [
        "not json at all",
        "",
        {"type": "maybe", "justification": "j", "confidence": 0.5},  # outside the allowed values
        {
            "type": "required",
            "justification": "j",
            "confidence": 1.5,
        },  # bound dropped from the schema, still enforced
        {"type": "required"},  # missing fields
    ],
)
def test_output_that_does_not_match_the_schema_is_rejected(content):
    with pytest.raises(StructuredOutputError):
        _openrouter(ok(content)).complete(REQUEST, EdgeClassification)


def test_a_response_with_no_choices_is_rejected():
    recorder = Recorder(lambda request: httpx.Response(200, json={"choices": []}))
    with pytest.raises(StructuredOutputError):
        _openrouter(recorder).complete(REQUEST, EdgeClassification)


# --- Cost -----------------------------------------------------------------------------------


def test_cost_uses_the_charge_reported_by_openrouter():
    cost = _openrouter(ok()).complete(REQUEST, EdgeClassification).cost
    assert (cost.tokens_in, cost.tokens_out, cost.usd) == (100, 20, 0.0004)


def test_cost_falls_back_to_per_token_prices_when_no_charge_is_reported():
    recorder = ok(usage={"prompt_tokens": 1000, "completion_tokens": 100})
    provider = _openrouter(recorder, usd_per_token_in=2e-6, usd_per_token_out=1e-5)
    assert provider.complete(REQUEST, EdgeClassification).cost.usd == pytest.approx(0.003)


def test_cost_is_zero_when_the_server_reports_nothing():
    recorder = Recorder(lambda request: httpx.Response(200, json=chat_response(VALID_EDGE)))
    cost = LocalProvider(client=recorder.client).complete(REQUEST, EdgeClassification).cost
    assert (cost.tokens_in, cost.tokens_out, cost.usd) == (0, 0, 0.0)


# --- Errors and retries ---------------------------------------------------------------------


def test_a_rate_limit_is_retried_and_then_succeeds():
    sleeps: list[float] = []
    attempts = []

    def responder(request):
        attempts.append(request)
        if len(attempts) == 1:
            return httpx.Response(429, text="slow down")
        return httpx.Response(200, json=chat_response(VALID_EDGE))

    recorder = Recorder(responder)
    provider = OpenRouterProvider(api_key=KEY, client=recorder.client, sleep=sleeps.append)
    assert provider.complete(REQUEST, EdgeClassification).result.type == "required"
    assert len(recorder.requests) == 2
    assert sleeps == [2]


def test_a_persistent_server_error_gives_up_after_max_attempts():
    recorder = Recorder(lambda request: httpx.Response(503, text="down"))
    with pytest.raises(ProviderError, match="HTTP 503"):
        _openrouter(recorder).complete(REQUEST, EdgeClassification)
    assert len(recorder.requests) == 3


@pytest.mark.parametrize(
    ("status", "hint"), [(401, "key was rejected"), (402, "insufficient credits")]
)
def test_a_fatal_status_is_not_retried_and_never_leaks_the_key(status, hint):
    recorder = Recorder(lambda request: httpx.Response(status, text="denied"))
    with pytest.raises(ProviderError) as raised:
        _openrouter(recorder).complete(REQUEST, EdgeClassification)

    assert len(recorder.requests) == 1
    assert hint in str(raised.value)
    assert KEY not in str(raised.value)


def test_a_connection_error_is_retried_then_reported():
    def refuse(request):
        raise httpx.ConnectError("refused")

    recorder = Recorder(refuse)
    with pytest.raises(ProviderError, match="cannot reach"):
        _openrouter(recorder).complete(REQUEST, EdgeClassification)
    assert len(recorder.requests) == 3


def test_openrouter_needs_a_key():
    with pytest.raises(ProviderError, match="OPENROUTER_API_KEY"):
        OpenRouterProvider(api_key=None)
    with pytest.raises(ProviderError, match="OPENROUTER_API_KEY"):
        OpenRouterProvider(api_key="")


# --- Pricing, estimates and the factory ---------------------------------------------------


def test_model_pricing_is_read_from_the_public_model_list():
    listing = {
        "data": [
            {"id": "other/model", "pricing": {"prompt": "0.1", "completion": "0.2"}},
            {
                "id": "anthropic/claude-sonnet-5.5",
                "pricing": {"prompt": "0.000002", "completion": "0.00001"},
            },
        ]
    }
    recorder = Recorder(lambda request: httpx.Response(200, json=listing))

    assert fetch_model_pricing("anthropic/claude-sonnet-5.5", client=recorder.client) == (
        2e-6,
        1e-5,
    )
    assert str(recorder.requests[0].url) == "https://openrouter.ai/api/v1/models"
    assert "authorization" not in recorder.requests[0].headers
    with pytest.raises(ProviderError, match="no model"):
        fetch_model_pricing("nope/none", client=recorder.client)


def test_dry_run_estimate_scales_with_requests_and_prices():
    requests = [LLMRequest(stage="edge", prompt_version="v", user="x" * 400) for _ in range(10)]
    cost = estimate_cost(requests, EdgeClassification, 2e-6, 1e-5, expected_output_tokens=100)

    assert cost.tokens_out == 1000
    assert cost.tokens_in >= 10 * estimate_tokens("x" * 400)
    assert cost.usd == pytest.approx(cost.tokens_in * 2e-6 + 1000 * 1e-5)
    assert estimate_cost([], EdgeClassification, 1, 1).usd == 0


def test_factory_builds_each_provider_from_settings():
    settings = Settings(_env_file=None, openrouter_api_key="k", openrouter_model="vendor/model")

    assert make_provider("fake", settings).provider == "fake"
    router = make_provider("openrouter", settings)
    assert (router.provider, router.model) == ("openrouter", "vendor/model")
    assert make_provider("local", settings).provider == "local"
    with pytest.raises(ProviderError, match="Unknown provider"):
        make_provider("bogus", settings)
    with pytest.raises(ProviderError, match="OPENROUTER_API_KEY"):
        make_provider("openrouter", Settings(_env_file=None))


def test_the_openrouter_key_is_read_from_the_standard_environment_variable(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "from-env")
    assert Settings(_env_file=None).openrouter_api_key == "from-env"


def test_providers_satisfy_the_text_llm_shape():
    for provider in (
        LocalProvider(),
        OpenAICompatProvider(provider="x", model="m", base_url="http://h"),
    ):
        assert callable(provider.complete)
        assert provider.provider and provider.model

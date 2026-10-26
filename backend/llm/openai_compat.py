"""One client for any OpenAI-compatible chat-completions server.

OpenRouter (Pipeline A) and Ollama or any other local server (Pipeline B) both speak this
protocol, so they share this code and differ only in configuration. Output is requested as a JSON
schema and then validated again here, because servers vary in how strictly they enforce it.
"""

import json
import re
import time
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from backend.llm.base import Completion, Cost, LLMRequest, T


class ProviderError(RuntimeError):
    """The server refused the request or could not be reached."""


class StructuredOutputError(ProviderError):
    """The server answered, but not with JSON that matches the requested schema."""


_RETRY_STATUSES = {429, 500, 502, 503, 504}
_FATAL_HINTS = {
    401: "the API key was rejected",
    402: "the account has insufficient credits",
    403: "the request was refused (key or model not permitted)",
}


def strict_json_schema(schema: type[BaseModel]) -> dict[str, Any]:
    """The model's JSON schema, trimmed to what strict structured-output modes accept.

    Strict modes want `additionalProperties: false` on every object and reject some keywords
    (numeric bounds, defaults, titles). The dropped constraints are still enforced when the
    response is validated against the Pydantic model.
    """

    def clean(node: Any) -> Any:
        if isinstance(node, list):
            return [clean(item) for item in node]
        if not isinstance(node, dict):
            return node
        cleaned = {
            key: clean(value)
            for key, value in node.items()
            if key
            not in {
                "title",
                "default",
                "minimum",
                "maximum",
                "exclusiveMinimum",
                "exclusiveMaximum",
            }
        }
        if cleaned.get("type") == "object":
            cleaned["additionalProperties"] = False
            cleaned.setdefault("required", list(cleaned.get("properties", {})))
        return cleaned

    return clean(schema.model_json_schema())


def parse_json_object(text: str) -> Any:
    """Parse model output as JSON, tolerating a code fence or surrounding prose."""
    text = text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


class OpenAICompatProvider:
    def __init__(
        self,
        *,
        provider: str,
        model: str,
        base_url: str,
        api_key: str | None = None,
        headers: dict[str, str] | None = None,
        extra_body: dict[str, Any] | None = None,
        usd_per_token_in: float | None = None,
        usd_per_token_out: float | None = None,
        client: httpx.Client | None = None,
        timeout: float = 120.0,
        max_attempts: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.provider = provider
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.extra_body = extra_body or {}
        self.usd_per_token_in = usd_per_token_in
        self.usd_per_token_out = usd_per_token_out
        self.max_attempts = max_attempts
        self._sleep = sleep
        self._client = client or httpx.Client(timeout=timeout)
        self._headers = {"Content-Type": "application/json", **(headers or {})}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"

    def complete(self, request: LLMRequest, schema: type[T]) -> Completion[T]:
        data = self._post(self._body(request, schema))
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise StructuredOutputError(
                f"{self.provider}: no message in response: {data!r:.300}"
            ) from error
        if not isinstance(content, str) or not content.strip():
            raise StructuredOutputError(f"{self.provider}: empty response from {self.model}")
        try:
            result = schema.model_validate(parse_json_object(content))
        except (ValueError, ValidationError) as error:
            raise StructuredOutputError(
                f"{self.provider}: {self.model} did not return valid "
                f"{schema.__name__}: {content!r:.300}"
            ) from error
        return Completion(
            result=result,
            cost=self._cost(data.get("usage") or {}),
            provider=self.provider,
            model=self.model,
        )

    def _body(self, request: LLMRequest, schema: type[BaseModel]) -> dict[str, Any]:
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.user})
        return {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "strict": True,
                    "schema": strict_json_schema(schema),
                },
            },
            **self.extra_body,
        }

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self._client.post(url, headers=self._headers, json=body)
            except httpx.TransportError as error:
                if attempt == self.max_attempts:
                    raise ProviderError(
                        f"{self.provider}: cannot reach {self.base_url} ({error})"
                    ) from error
                self._sleep(2**attempt)
                continue
            if response.status_code == 200:
                return response.json()
            if response.status_code in _RETRY_STATUSES and attempt < self.max_attempts:
                self._sleep(2**attempt)
                continue
            hint = _FATAL_HINTS.get(response.status_code, "unexpected status")
            # The body can explain a rejection. It never holds our key, which only goes in a header.
            raise ProviderError(
                f"{self.provider}: HTTP {response.status_code}, {hint}: {response.text[:300]}"
            )
        raise ProviderError(
            f"{self.provider}: gave up after {self.max_attempts} attempts"
        )  # pragma: no cover

    def _cost(self, usage: dict[str, Any]) -> Cost:
        tokens_in = int(usage.get("prompt_tokens") or 0)
        tokens_out = int(usage.get("completion_tokens") or 0)
        if usage.get("cost") is not None:  # OpenRouter reports the exact charge
            usd = float(usage["cost"])
        elif self.usd_per_token_in is not None and self.usd_per_token_out is not None:
            usd = tokens_in * self.usd_per_token_in + tokens_out * self.usd_per_token_out
        else:
            usd = 0.0
        return Cost(tokens_in=tokens_in, tokens_out=tokens_out, usd=usd)

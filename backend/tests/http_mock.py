"""Helpers for testing HTTP providers without a network."""

import json
from collections.abc import Callable
from typing import Any

import httpx


def chat_response(content: Any, usage: dict[str, Any] | None = None) -> dict[str, Any]:
    """A minimal OpenAI-style chat completion. `content` is a dict (sent as JSON) or a string."""
    text = content if isinstance(content, str) else json.dumps(content)
    body: dict[str, Any] = {"choices": [{"message": {"role": "assistant", "content": text}}]}
    if usage is not None:
        body["usage"] = usage
    return body


VALID_EDGE = {"type": "required", "justification": "Needs vectors first.", "confidence": 0.9}


class Recorder:
    """A mock transport that answers with `responder(request)` and remembers every request."""

    def __init__(self, responder: Callable[[httpx.Request], httpx.Response]) -> None:
        self.requests: list[httpx.Request] = []
        self._responder = responder

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._responder(request)

    @property
    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))

    def json_bodies(self) -> list[dict[str, Any]]:
        return [json.loads(request.content) for request in self.requests]


def ok(content: Any = VALID_EDGE, usage: dict[str, Any] | None = None) -> Recorder:
    usage = (
        usage
        if usage is not None
        else {"prompt_tokens": 100, "completion_tokens": 20, "cost": 0.0004}
    )
    return Recorder(lambda request: httpx.Response(200, json=chat_response(content, usage)))

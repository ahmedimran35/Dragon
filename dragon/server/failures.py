"""What to tell the person when a run dies on an exception.

A chat turn that fails used to surface as ``Something went wrong: APIError: Incorrect API
key provided …`` — the provider's words. This module turns the exception into two things: a
short **code** the apps can act on (``key``, ``network``, ``too_long`` …) and one **English
sentence** that says what happened and where to go, which the web app translates with its
own dictionary (the sentence is the key, so the wording here must match
``web/src/i18n/zh-CN.ts``).
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import openai

_TOO_LONG = (
    "context length",
    "context_length",
    "maximum context",
    "too many tokens",
    "token limit",
    "too long",
)


def _first_line(exc: BaseException) -> str:
    text = str(exc).strip() or type(exc).__name__
    return text.splitlines()[0][:200]


def describe_failure(exc: BaseException) -> tuple[str, str]:
    """``(code, sentence)`` for a run that ended in ``exc``."""
    if getattr(exc, "code", None) == "upstream_empty":
        return "provider", "The model provider is having trouble; try again in a moment."
    if isinstance(exc, openai.AuthenticationError | openai.PermissionDeniedError):
        return "key", "The model provider refused the API key. Check it under Connections."
    if isinstance(exc, openai.NotFoundError):
        return "model", "The endpoint does not know this model. Pick another under Connections."
    if isinstance(exc, openai.RateLimitError):
        return "busy", "The model provider is rate-limiting this key; wait a moment and try again."
    if isinstance(
        exc, openai.APITimeoutError | asyncio.TimeoutError | TimeoutError | httpx.TimeoutException
    ):
        return "timeout", "The model took too long to answer. Try again."
    if isinstance(exc, openai.APIConnectionError | httpx.TransportError | ConnectionError):
        return "network", "Could not reach the model provider. Check the connection and try again."
    if isinstance(exc, openai.BadRequestError):
        low = str(exc).lower()
        if any(k in low for k in _TOO_LONG):
            return (
                "too_long",
                "This conversation is too long for the model. Start a new one, or pick a model with a larger context.",
            )
        return "request", f"The model refused the request: {_first_line(exc)}"
    if isinstance(exc, openai.InternalServerError):
        return "provider", "The model provider is having trouble; try again in a moment."
    if isinstance(exc, openai.APIError):
        return "provider", f"The model provider answered with an error: {_first_line(exc)}"
    return "unknown", f"Something went wrong: {type(exc).__name__}: {_first_line(exc)}"


def failure_notice(exc: BaseException, thread_id: str) -> dict[str, Any]:
    """The ``notice`` event for the apps: the sentence, the code, and the raw detail for
    bug reports (collapsed in the apps, never the only thing shown)."""
    code, text = describe_failure(exc)
    notice: dict[str, Any] = {
        "type": "notice",
        "level": "error",
        "code": code,
        "text": text,
        "detail": f"{type(exc).__name__}: {str(exc).strip()[:400]}",
        "thread": thread_id,
    }
    return notice


__all__ = ["describe_failure", "failure_notice"]

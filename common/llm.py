"""
Thin client for the OpenCode Zen inference API (OpenAI-compatible
`/chat/completions` endpoint).

The model/provider/key are all read from Django settings, which in turn
read from environment variables (.env). To switch models or providers,
only the .env file needs to change — this file never needs editing.
"""

import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class LLMConfigurationError(Exception):
    """Raised when the LLM provider is not configured (missing API key)."""


class LLMRequestError(Exception):
    """Raised when the request to the LLM provider fails."""


def is_configured() -> bool:
    return bool(settings.OPENCODE_API_KEY)


def chat_completion(messages, temperature: float = 0.4, max_tokens: int = 700) -> str:
    """
    Send a chat-style completion request to the configured OpenCode Zen model.

    `messages` follows the standard OpenAI chat format:
        [{"role": "system"|"user"|"assistant", "content": "..."}, ...]

    Returns the assistant's reply text. Raises LLMConfigurationError if no
    API key is set, or LLMRequestError if the call fails for any reason.
    """
    if not is_configured():
        raise LLMConfigurationError(
            "OPENCODE_API_KEY is not set. Add it to your .env file to enable "
            "AI-generated explanations and the chat assistant."
        )

    url = f"{settings.OPENCODE_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENCODE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.OPENCODE_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    try:
        response = requests.post(
            url, json=payload, headers=headers, timeout=settings.OPENCODE_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        data = response.json()
        content = (data["choices"][0]["message"].get("content") or "").strip()
        if not content:
            raise LLMRequestError("The LLM provider returned an empty response.")
        return content
    except requests.exceptions.RequestException as exc:
        logger.exception("LLM request failed")
        raise LLMRequestError(f"Could not reach the LLM provider: {exc}") from exc
    except (KeyError, IndexError, ValueError) as exc:
        logger.exception("LLM response could not be parsed")
        raise LLMRequestError(f"Unexpected response from LLM provider: {exc}") from exc


def _build_payload(messages, temperature, max_tokens, stream):
    return {
        "model": settings.OPENCODE_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }


def chat_completion_stream(messages, temperature=0.5, max_tokens=500):
    """
    Generator that yields SSE-formatted dicts from a streaming chat completion.

    Each yielded dict has the structure:
        {"type": "reasoning", "text": "..."}
        {"type": "content", "text": "..."}
        {"type": "done", "finish_reason": "stop"|"length"|null}
        {"type": "error", "text": "..."}
    """
    if not is_configured():
        yield {"type": "error", "text": "OPENCODE_API_KEY is not set."}
        return

    url = f"{settings.OPENCODE_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENCODE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = _build_payload(messages, temperature, max_tokens, stream=True)

    try:
        resp = requests.post(
            url, json=payload, headers=headers,
            stream=True, timeout=settings.OPENCODE_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.exception("LLM stream request failed")
        yield {"type": "error", "text": f"LLM request failed: {exc}"}
        return

    finish_reason = None
    try:
        for line in resp.iter_lines():
            if not line:
                continue
            raw = line.decode("utf-8", errors="replace")
            if raw.startswith("data: "):
                raw = raw[6:]
            if raw.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(raw)
            except json.JSONDecodeError:
                continue

            choices = chunk.get("choices") or []
            if not choices:
                continue
            if choices[0].get("finish_reason"):
                finish_reason = choices[0]["finish_reason"]
            delta = choices[0].get("delta", {})
            if "reasoning_content" in delta and delta["reasoning_content"]:
                yield {"type": "reasoning", "text": delta["reasoning_content"]}
            if "content" in delta and delta["content"]:
                yield {"type": "content", "text": delta["content"]}
    except Exception as exc:
        logger.exception("LLM stream parse error")
        yield {"type": "error", "text": f"Stream parse error: {exc}"}
        return

    yield {"type": "done", "finish_reason": finish_reason}


def stream_response(messages, temperature=0.5, max_tokens=500):
    """
    Django StreamingHttpResponse view helper.
    Yields SSE `data: {...}\n\n` lines consumed by EventSource on the client.
    """
    for event in chat_completion_stream(messages, temperature, max_tokens):
        yield f"data: {json.dumps(event)}\n\n"

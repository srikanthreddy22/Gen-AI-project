import json
import logging
import os
from typing import Any

import httpx
from google import genai
from google.genai import errors, types

logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
_FALLBACK_MODELS = []
_ACTIVE_MODEL = None
_client = None


class GeminiServiceError(RuntimeError):
    pass


class GeminiConfigurationError(GeminiServiceError):
    pass


class GeminiQuotaError(GeminiServiceError):
    pass


class GeminiTimeoutError(GeminiServiceError):
    pass


class GeminiResponseError(GeminiServiceError):
    pass


def _get_client():
    global _client
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise GeminiConfigurationError("GEMINI_API_KEY is not configured")
    if _client is None:
        timeout_ms = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "15")) * 1000
        retry_options = types.HttpRetryOptions(
            attempts=1,
            initial_delay=1.0,
            max_delay=2.0,
            exp_base=2.0,
            jitter=0.2,
            http_status_codes=[408, 500, 502, 503, 504],
        )
        _client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=timeout_ms,
                retry_options=retry_options,
            ),
        )
    return _client


def _build_contents(messages):
    system_instructions = []
    contents = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        if role == "system":
            system_instructions.append(content.strip())
        elif role in {"user", "assistant", "model"}:
            contents.append(types.Content(
                role="model" if role in {"assistant", "model"} else "user",
                parts=[types.Part.from_text(text=content)],
            ))
        else:
            raise ValueError(f"Unsupported Gemini message role: {role}")

    if not contents:
        raise ValueError("At least one user or assistant message is required")
    return "\n\n".join(system_instructions) or None, contents


def generate_content(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.3,
    max_output_tokens: int = 1500,
    response_format: dict[str, Any] | None = None,
    model: str | None = None,
):
    global _ACTIVE_MODEL
    system_instruction, contents = _build_contents(messages)
    if response_format and response_format.get("type") != "json_object":
        raise ValueError("Only JSON object responses are supported")

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        response_mime_type="application/json" if response_format else None,
    )
    client = _get_client()

    candidate_models = []
    if model:
        candidate_models.append(model)
    elif _ACTIVE_MODEL:
        candidate_models.append(_ACTIVE_MODEL)
    else:
        candidate_models.append(MODEL_NAME)

    for fallback in _FALLBACK_MODELS:
        if fallback not in candidate_models:
            candidate_models.append(fallback)

    last_error = None
    response = None

    for target_model in candidate_models:
        try:
            response = client.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )
            _ACTIVE_MODEL = target_model
            break
        except httpx.TimeoutException:
            logger.warning("Gemini request timed out on model %s", target_model)
            raise GeminiTimeoutError("Gemini request timed out") from None
        except httpx.HTTPError as exc:
            logger.error("Gemini network request failed (%s)", type(exc).__name__)
            raise GeminiServiceError("Gemini network request failed") from None
        except errors.APIError as exc:
            status = getattr(exc, "code", None)
            err_msg = str(exc)
            if status == 404 and any(phrase in err_msg.lower() for phrase in ["no longer available", "not found", "does not exist"]):
                logger.warning(
                    "Gemini model '%s' unavailable (404: %s). Trying fallback candidate...",
                    target_model,
                    err_msg[:120],
                )
                last_error = exc
                continue
            if status == 503 and len(candidate_models) > 1 and target_model != candidate_models[-1]:
                logger.warning("Gemini model '%s' returned 503. Trying next candidate...", target_model)
                last_error = exc
                continue
            if status == 429:
                logger.warning("Gemini request rejected due to quota or rate limit")
                raise GeminiQuotaError("Gemini quota or rate limit reached") from None
            if status in {408, 504}:
                logger.warning("Gemini request timed out")
                raise GeminiTimeoutError("Gemini request timed out") from None
            logger.error("Gemini API request failed with status %s", status)
            raise GeminiServiceError(f"Gemini request failed (status {status})") from None

    if response is None:
        if last_error is not None:
            raise GeminiServiceError(f"Gemini request failed: {last_error}") from last_error
        raise GeminiResponseError("No Gemini model responded successfully")

    text = response.text
    if not isinstance(text, str) or not text.strip():
        raise GeminiResponseError("Gemini returned an empty response")
    if response_format:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise GeminiResponseError("Gemini returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise GeminiResponseError("Gemini JSON response must be an object")
    return text


def chat_completion(
    messages,
    model=None,
    temperature=0.3,
    max_tokens=None,
    response_format=None,
):
    if model is not None and model != MODEL_NAME and model not in _FALLBACK_MODELS:
        raise ValueError(f"Only {MODEL_NAME} is configured")
    content = generate_content(
        messages,
        temperature=temperature,
        max_output_tokens=max_tokens or 1500,
        response_format=response_format,
        model=model,
    )
    return {"choices": [{"message": {"content": content}}]}

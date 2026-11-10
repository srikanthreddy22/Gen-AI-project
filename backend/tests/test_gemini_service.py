from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors

from app.services import gemini_service


class FakeModels:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.call = None

    def generate_content(self, **kwargs):
        self.call = kwargs
        if self.error:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, models):
        self.models = models


def test_gemini_uses_flash_model_timeout_and_json_mode(monkeypatch):
    models = FakeModels(response=SimpleNamespace(text='{"questions": []}'))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "12")
    monkeypatch.setattr(gemini_service, "_client", FakeClient(models))

    response = gemini_service.chat_completion(
        [
            {"role": "system", "content": "Follow the system instructions."},
            {"role": "user", "content": "Return a JSON object."},
        ],
        temperature=0.2,
        max_tokens=500,
        response_format={"type": "json_object"},
    )

    assert response == {"choices": [{"message": {"content": '{"questions": []}'}}]}
    assert models.call["model"] == "gemini-2.5-flash"
    assert models.call["config"].response_mime_type == "application/json"
    assert models.call["config"].system_instruction == "Follow the system instructions."
    assert models.call["config"].max_output_tokens == 500
    assert models.call["contents"][0].role == "user"


def test_gemini_requires_an_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(gemini_service, "_client", None)

    with pytest.raises(gemini_service.GeminiConfigurationError):
        gemini_service.generate_content([{"role": "user", "content": "hello"}])


def test_gemini_quota_and_timeout_errors_are_classified(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    quota_client = FakeClient(FakeModels(error=errors.APIError(429, {"error": "quota"})))
    monkeypatch.setattr(gemini_service, "_client", quota_client)

    with pytest.raises(gemini_service.GeminiQuotaError):
        gemini_service.generate_content([{"role": "user", "content": "hello"}])

    timeout_client = FakeClient(FakeModels(error=httpx.ReadTimeout("timeout")))
    monkeypatch.setattr(gemini_service, "_client", timeout_client)
    with pytest.raises(gemini_service.GeminiTimeoutError):
        gemini_service.generate_content([{"role": "user", "content": "hello"}])


@pytest.mark.parametrize("text", ["not-json", "[]"])
def test_gemini_rejects_non_object_json_responses(monkeypatch, text):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        gemini_service,
        "_client",
        FakeClient(FakeModels(response=SimpleNamespace(text=text))),
    )

    with pytest.raises(gemini_service.GeminiResponseError):
        gemini_service.generate_content(
            [{"role": "user", "content": "Return JSON."}],
            response_format={"type": "json_object"},
        )

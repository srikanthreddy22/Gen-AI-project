import pytest
from app.services import embedding_service


class FakeModel:
    def __init__(self, vectors):
        self.vectors = vectors
        self.kwargs = None

    def encode(self, texts, **kwargs):
        self.kwargs = kwargs
        return self.vectors[:len(texts)]


def test_embeddings_use_a_single_normalized_minilm_model(monkeypatch):
    models = []

    def create_model():
        model = FakeModel([[0.6, 0.8], [1.0, 0.0]])
        models.append(model)
        return model

    monkeypatch.setattr(embedding_service, "_model", None)
    monkeypatch.setattr(embedding_service, "_create_model", create_model)

    first = embedding_service.get_embeddings(["first text", "second text"])
    second = embedding_service.get_embeddings(["query text"])

    assert first == [[0.6, 0.8], [1.0, 0.0]]
    assert second == [[0.6, 0.8]]
    assert len(models) == 1
    assert embedding_service.MODEL_NAME == "all-MiniLM-L6-v2"
    assert models[0].kwargs["normalize_embeddings"] is True
    assert models[0].kwargs["convert_to_numpy"] is True


def test_embedding_inputs_and_model_output_are_validated(monkeypatch):
    monkeypatch.setattr(embedding_service, "_model", None)
    monkeypatch.setattr(embedding_service, "_create_model", lambda: FakeModel([[1.0, 0.0]]))

    assert embedding_service.get_embeddings([]) == []
    with pytest.raises(TypeError):
        embedding_service.get_embeddings("not a list")
    with pytest.raises(TypeError):
        embedding_service.get_embeddings(["valid", None])

    monkeypatch.setattr(embedding_service, "_model", FakeModel([[float("nan"), 0.0]]))
    with pytest.raises(embedding_service.EmbeddingServiceError, match="invalid vector"):
        embedding_service.get_embeddings(["text"])


def test_model_loading_failure_is_reported(monkeypatch):
    monkeypatch.setattr(embedding_service, "_model", None)

    def fail_model_load():
        raise OSError("model files unavailable")

    monkeypatch.setattr(embedding_service, "_create_model", fail_model_load)
    with pytest.raises(embedding_service.EmbeddingServiceError, match="Could not load embedding model"):
        embedding_service.get_embeddings(["document chunk"])


def test_gemini_provider_batches_and_validates_vectors(monkeypatch):
    monkeypatch.setattr(embedding_service, "_model", None)
    monkeypatch.setattr(embedding_service, "_create_model", embedding_service._default_create_model)
    monkeypatch.setenv("GEMINI_API_KEY", "real-gemini-key")
    monkeypatch.setenv("ENABLE_LOCAL_EMBEDDINGS", "false")
    monkeypatch.setenv("GEMINI_EMBEDDING_DIMENSION", "4")

    calls = []

    class FakeEmb:
        def __init__(self, values):
            self.values = values

    class FakeResponse:
        def __init__(self, embeddings):
            self.embeddings = embeddings

    class FakeModelsClient:
        def embed_content(self, model, contents, config=None):
            calls.append({"model": model, "contents": contents, "config": config})
            return FakeResponse([FakeEmb([0.1, 0.2, 0.3, 0.4]) for _ in contents])

    class FakeGenAIClient:
        def __init__(self):
            self.models = FakeModelsClient()

    fake_client = FakeGenAIClient()
    monkeypatch.setattr(embedding_service, "_get_gemini_client", lambda api_key: fake_client)

    texts = [f"Text item {i}" for i in range(25)]
    vectors = embedding_service.get_embeddings(texts, task_type="RETRIEVAL_DOCUMENT")

    assert len(vectors) == 25
    assert len(vectors[0]) == 4
    # 25 items batched in chunks of 10 -> 3 batches (10, 10, 5)
    assert len(calls) == 3
    assert len(calls[0]["contents"]) == 10
    assert len(calls[1]["contents"]) == 10
    assert len(calls[2]["contents"]) == 5
    assert calls[0]["config"].task_type == "RETRIEVAL_DOCUMENT"
    assert calls[0]["config"].output_dimensionality == 4

    profile = embedding_service.get_embedding_profile()
    assert profile["provider"] == "gemini"
    assert profile["dimension"] == 4


def test_unconfigured_embeddings_raise_informative_error(monkeypatch):
    monkeypatch.setattr(embedding_service, "_model", None)
    monkeypatch.setattr(embedding_service, "_create_model", embedding_service._default_create_model)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("ENABLE_LOCAL_EMBEDDINGS", "false")

    with pytest.raises(embedding_service.EmbeddingServiceError, match="Embeddings are not configured. Set GEMINI_API_KEY."):
        embedding_service.get_embeddings(["some text"])


def test_placeholder_api_key_is_ignored(monkeypatch):
    monkeypatch.setattr(embedding_service, "_model", None)
    monkeypatch.setattr(embedding_service, "_create_model", embedding_service._default_create_model)
    monkeypatch.setenv("GEMINI_API_KEY", "your_api_key_here")
    monkeypatch.setenv("ENABLE_LOCAL_EMBEDDINGS", "false")

    assert embedding_service.is_valid_gemini_key("your_api_key_here") is False
    assert embedding_service.is_valid_gemini_key("") is False
    assert embedding_service.is_valid_gemini_key(None) is False
    assert embedding_service.is_valid_gemini_key("valid_key") is True

    with pytest.raises(embedding_service.EmbeddingServiceError, match="Embeddings are not configured. Set GEMINI_API_KEY."):
        embedding_service.get_embeddings(["some text"])

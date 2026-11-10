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

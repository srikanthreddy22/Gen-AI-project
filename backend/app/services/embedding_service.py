import logging
import math
import os
import threading
import time
from typing import Any, List, Optional

from flask import current_app, has_app_context
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Default model identifiers
MODEL_NAME = "all-MiniLM-L6-v2"
DEFAULT_GEMINI_MODEL = "gemini-embedding-001"
DEFAULT_GEMINI_DIMENSION = 3072
DEFAULT_LOCAL_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_LOCAL_DEVICE = "cpu"

_model = None
_model_lock = threading.Lock()
_gemini_client = None
_gemini_client_lock = threading.Lock()

EMBEDDING_BATCH_SIZE = max(1, int(os.getenv("EMBEDDING_BATCH_SIZE", "32")))
GEMINI_BATCH_SIZE = 10


class EmbeddingServiceError(RuntimeError):
    pass


def is_valid_gemini_key(api_key: Optional[str]) -> bool:
    if not api_key:
        return False
    stripped = api_key.strip()
    if not stripped or stripped.lower().startswith("your_"):
        return False
    return True


def _get_config_value(key: str, default: Any) -> Any:
    if has_app_context():
        val = current_app.config.get(key)
        if val is not None:
            return val
    return os.getenv(key, default)


def _get_gemini_api_key() -> Optional[str]:
    key = None
    if has_app_context():
        key = current_app.config.get("GEMINI_API_KEY")
    if not key:
        key = os.getenv("GEMINI_API_KEY")
    return key if is_valid_gemini_key(key) else None


def _is_local_enabled() -> bool:
    val = _get_config_value("ENABLE_LOCAL_EMBEDDINGS", "false")
    if isinstance(val, bool):
        return val
    return str(val or "").strip().lower() in {"1", "true", "yes"}


def _create_local_model():
    from sentence_transformers import SentenceTransformer

    model_name = _get_config_value(
        "LOCAL_EMBEDDING_MODEL",
        _get_config_value("SENTENCE_TRANSFORMERS_MODEL", DEFAULT_LOCAL_MODEL),
    )
    device = _get_config_value("LOCAL_EMBEDDING_DEVICE", DEFAULT_LOCAL_DEVICE)
    try:
        return SentenceTransformer(model_name, device=device, local_files_only=True)
    except Exception:
        return SentenceTransformer(model_name, device=device)


_default_create_model = _create_local_model
_create_model = _default_create_model


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                try:
                    started = time.perf_counter()
                    _model = _create_model()
                    logger.info("Loaded Sentence Transformers model in %.3fs", time.perf_counter() - started)
                except Exception as exc:
                    logger.exception("Could not load Sentence Transformers model")
                    raise EmbeddingServiceError("Could not load embedding model") from exc
    return _model


def _get_gemini_client(api_key: str):
    global _gemini_client
    if _gemini_client is None:
        with _gemini_client_lock:
            if _gemini_client is None:
                timeout_sec = int(_get_config_value("GEMINI_TIMEOUT_SECONDS", 30))
                _gemini_client = genai.Client(
                    api_key=api_key,
                    http_options=types.HttpOptions(
                        timeout=timeout_sec * 1000,
                    ),
                )
    return _gemini_client


def get_embedding_profile() -> dict[str, Any]:
    """Returns active embedding profile: {'provider': ..., 'model': ..., 'dimension': ...}"""
    # If a test monkeypatched _create_model or _model directly, honor it as local
    if _model is not None or _create_model is not _default_create_model:
        model = _get_config_value("LOCAL_EMBEDDING_MODEL", MODEL_NAME)
        return {
            "provider": "local",
            "model": model,
            "dimension": 384,
        }

    gemini_key = _get_gemini_api_key()
    if gemini_key:
        model = _get_config_value("GEMINI_EMBEDDING_MODEL", DEFAULT_GEMINI_MODEL)
        dimension = int(_get_config_value("GEMINI_EMBEDDING_DIMENSION", DEFAULT_GEMINI_DIMENSION))
        return {
            "provider": "gemini",
            "model": model,
            "dimension": dimension,
        }

    if _is_local_enabled():
        model = _get_config_value("LOCAL_EMBEDDING_MODEL", DEFAULT_LOCAL_MODEL)
        return {
            "provider": "local",
            "model": model,
            "dimension": 384,
        }

    raise EmbeddingServiceError("Embeddings are not configured. Set GEMINI_API_KEY.")


def _embed_gemini(
    texts: List[str],
    task_type: str = "RETRIEVAL_DOCUMENT",
    model_name: str = DEFAULT_GEMINI_MODEL,
    dimension: int = DEFAULT_GEMINI_DIMENSION,
) -> List[List[float]]:
    api_key = _get_gemini_api_key()
    if not api_key:
        raise EmbeddingServiceError("Embeddings are not configured. Set GEMINI_API_KEY.")

    client = _get_gemini_client(api_key)
    vectors: List[List[float]] = []

    started = time.perf_counter()
    for offset in range(0, len(texts), GEMINI_BATCH_SIZE):
        batch = texts[offset:offset + GEMINI_BATCH_SIZE]
        batch_started = time.perf_counter()
        try:
            config = types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=dimension,
            )
            response = client.models.embed_content(
                model=model_name,
                contents=batch,
                config=config,
            )
        except Exception as exc:
            logger.exception("Gemini embedding generation failed")
            raise EmbeddingServiceError("Gemini embedding generation failed") from exc

        if not response or not response.embeddings or len(response.embeddings) != len(batch):
            raise EmbeddingServiceError("Embedding model returned an unexpected number of vectors")

        for emb in response.embeddings:
            values = getattr(emb, "values", None)
            if values is None:
                raise EmbeddingServiceError("Embedding model returned an empty vector")
            float_vals = [float(v) for v in values]
            if not float_vals or any(not math.isfinite(v) for v in float_vals):
                raise EmbeddingServiceError("Embedding model returned an invalid vector")
            if len(float_vals) != dimension:
                raise EmbeddingServiceError(
                    f"Embedding model returned vector of dimension {len(float_vals)}, expected {dimension}"
                )
            vectors.append(float_vals)

        logger.info(
            "Embedded batch %d-%d of %d texts with Gemini (%s) in %.3fs",
            offset + 1,
            offset + len(batch),
            len(texts),
            model_name,
            time.perf_counter() - batch_started,
        )

    logger.info("Embedded %d texts with Gemini in %.3fs", len(texts), time.perf_counter() - started)
    return vectors


def _embed_local(texts: List[str], model_name: str) -> List[List[float]]:
    try:
        model = _get_model()
        vectors = []
        started = time.perf_counter()
        for offset in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch = texts[offset:offset + EMBEDDING_BATCH_SIZE]
            batch_started = time.perf_counter()
            encoded = model.encode(
                batch,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            batch_vectors = encoded.tolist() if hasattr(encoded, "tolist") else list(encoded)
            if len(batch_vectors) != len(batch):
                raise EmbeddingServiceError("Embedding model returned an unexpected number of vectors")
            vectors.extend(batch_vectors)
            logger.info(
                "Embedded batch %d-%d of %d texts with local model in %.3fs",
                offset + 1,
                offset + len(batch),
                len(texts),
                time.perf_counter() - batch_started,
            )
        logger.info("Embedded %d texts with local model in %.3fs", len(texts), time.perf_counter() - started)
    except EmbeddingServiceError:
        raise
    except Exception as exc:
        logger.exception("Sentence Transformers embedding generation failed")
        raise EmbeddingServiceError("Embedding generation failed") from exc

    if len(vectors) != len(texts):
        raise EmbeddingServiceError("Embedding model returned an unexpected number of vectors")

    normalized = []
    dimension = None
    for vector in vectors:
        values = [float(value) for value in vector]
        if not values or any(not math.isfinite(value) for value in values):
            raise EmbeddingServiceError("Embedding model returned an invalid vector")
        if dimension is None:
            dimension = len(values)
        elif len(values) != dimension:
            raise EmbeddingServiceError("Embedding model returned inconsistent vector dimensions")
        normalized.append(values)
    return normalized


def get_embeddings(
    texts: List[str],
    task_type: str = "RETRIEVAL_DOCUMENT",
    model: Optional[str] = None,
) -> List[List[float]]:
    if not isinstance(texts, list) or any(not isinstance(text, str) for text in texts):
        raise TypeError("Embedding input must be a list of strings")
    if not texts:
        return []

    profile = get_embedding_profile()
    provider = profile["provider"]
    model_name = model or profile["model"]

    if provider == "gemini":
        return _embed_gemini(
            texts,
            task_type=task_type,
            model_name=model_name,
            dimension=profile["dimension"],
        )
    elif provider == "local":
        return _embed_local(texts, model_name=model_name)
    else:
        raise EmbeddingServiceError("Embeddings are not configured. Set GEMINI_API_KEY.")

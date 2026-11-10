import logging
import math
import os
import threading
import time

from flask import current_app, has_app_context

logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv("SENTENCE_TRANSFORMERS_MODEL", "all-MiniLM-L6-v2")
_model = None
_model_lock = threading.Lock()
EMBEDDING_BATCH_SIZE = max(1, int(os.getenv("EMBEDDING_BATCH_SIZE", "32")))


class EmbeddingServiceError(RuntimeError):
    pass


def _create_model():
    from sentence_transformers import SentenceTransformer

    model_name = MODEL_NAME
    if has_app_context():
        model_name = current_app.config.get("SENTENCE_TRANSFORMERS_MODEL", model_name)
    try:
        return SentenceTransformer(model_name, local_files_only=True)
    except Exception:
        return SentenceTransformer(model_name)


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                try:
                    started = time.perf_counter()
                    _model = _create_model()
                    logger.info("Loaded embedding model %s in %.3fs", MODEL_NAME, time.perf_counter() - started)
                except Exception as exc:
                    logger.exception("Could not load Sentence Transformers model %s", MODEL_NAME)
                    raise EmbeddingServiceError(
                        f"Could not load embedding model {MODEL_NAME}"
                    ) from exc
    return _model


def get_embeddings(texts):
    if not isinstance(texts, list) or any(not isinstance(text, str) for text in texts):
        raise TypeError("Embedding input must be a list of strings")
    if not texts:
        return []

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
                "Embedded batch %d-%d of %d texts in %.3fs",
                offset + 1,
                offset + len(batch),
                len(texts),
                time.perf_counter() - batch_started,
            )
        logger.info("Embedded %d texts in %.3fs", len(texts), time.perf_counter() - started)
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

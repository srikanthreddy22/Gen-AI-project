import os
import sys
import json
import shutil
from io import BytesIO
from types import SimpleNamespace

# ensure backend package importable
TEST_ROOT = os.path.dirname(__file__)
BACKEND_ROOT = os.path.abspath(os.path.join(TEST_ROOT, '..'))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

import app.services.rag_service as rag_service
import app.services.vector_store as vector_store
import app.services.openai_service as openai_service
import app.services.generation_service as generation_service
from app import create_app


SAMPLE_PATH = os.path.join(TEST_ROOT, 'sample_multi_topic.txt')


def _fake_embedding(texts):
    # deterministic small embeddings based on text hash
    out = []
    for t in texts:
        h = sum(ord(c) for c in t) % 1000
        # simple 3-d vector
        out.append([((h + i) % 100) / 100.0 for i in range(3)])
    return out


def setup_function():
    # use a test-local DB path to avoid locking issues
    test_db = os.path.join(TEST_ROOT, '.vector_store_test.db')
    vector_store.DB_PATH = test_db
    # re-init DB
    vector_store.init_db()
    # reduce chunk size for testing to produce multiple chunks
    try:
        rag_service.DEFAULT_CHUNK_CHARS = 80
        rag_service.DEFAULT_CHUNK_OVERLAP = 20
    except Exception:
        pass
    # keep original grouping function reference for tests to override threshold
    if not hasattr(rag_service, '_assign_topic_groups_orig'):
        rag_service._assign_topic_groups_orig = rag_service._assign_topic_groups


def teardown_function():
    # cleanup test db
    test_db = os.path.join(TEST_ROOT, '.vector_store_test.db')
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except Exception:
            pass


def test_document_chunking_and_indexing(monkeypatch):
    text = open(SAMPLE_PATH, 'r', encoding='utf-8').read()
    # patch embeddings (patch both modules that reference it)
    monkeypatch.setattr(rag_service, 'get_embeddings', lambda texts, model=None: _fake_embedding(texts))
    monkeypatch.setattr(generation_service, 'get_embeddings', lambda texts, model=None: _fake_embedding(texts))

    doc_id = rag_service.process_document(text, doc_name='sample')
    chunks = vector_store.get_document_chunks(doc_id)
    assert len(chunks) >= 4, 'Expect at least 4 chunks for multi-topic document'
    # ensure chunk metadata present
    for c in chunks:
        assert 'chunk_id' in c and 'chunk_text' in c
        assert 'embedding' in c and isinstance(c['embedding'], list)
        assert 'source_meta' in c


def test_document_indexing_falls_back_when_openai_quota_is_exhausted(monkeypatch):
    class QuotaExhaustedError(Exception):
        code = "credit_balance_exhausted"

    def fail_embeddings(texts, model=None):
        raise QuotaExhaustedError("OpenAI embedding credits exhausted")

    monkeypatch.setattr(rag_service, "get_embeddings", fail_embeddings)
    text = open(SAMPLE_PATH, "r", encoding="utf-8").read()

    doc_id = rag_service.process_document(text, doc_name="sample", force_reindex=True)

    chunks = vector_store.get_document_chunks(doc_id)
    assert chunks
    assert all(
        chunk["embedding"] == rag_service._approx_embedding(chunk["chunk_text"])
        for chunk in chunks
    )


def test_file_upload_succeeds_when_openai_quota_is_exhausted(monkeypatch):
    class QuotaExhaustedError(Exception):
        code = "credit_balance_exhausted"

    def fail_embeddings(texts, model=None):
        raise QuotaExhaustedError("OpenAI embedding credits exhausted")

    monkeypatch.setattr(rag_service, "get_embeddings", fail_embeddings)
    response = create_app().test_client().post(
        "/api/upload/",
        data={"file": (BytesIO(b"Machine learning is a field of artificial intelligence."), "notes.txt")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.get_json()["indexed"] is True
    assert response.get_json()["doc_id"]


def test_flashcards_fall_back_to_local_generation_when_openai_quota_is_exhausted(monkeypatch):
    class QuotaExhaustedError(Exception):
        code = "credit_balance_exhausted"

    monkeypatch.setattr(rag_service, "get_embeddings", lambda texts, model=None: _fake_embedding(texts))
    text = open(SAMPLE_PATH, "r", encoding="utf-8").read()
    doc_id = rag_service.process_document(text, doc_name="sample", force_reindex=True)
    monkeypatch.setattr(
        generation_service,
        "chat_completion",
        lambda *args, **kwargs: (_ for _ in ()).throw(QuotaExhaustedError()),
    )

    response = create_app().test_client().post(
        "/api/flashcards/", json={"doc_id": doc_id, "count": 5}
    )

    assert response.status_code == 200
    assert response.get_json()["generation_method"] == "local-fallback"
    assert response.get_json()["flashcards"]


def test_quiz_falls_back_to_local_generation_when_openai_quota_is_exhausted(monkeypatch):
    class QuotaExhaustedError(Exception):
        code = "credit_balance_exhausted"

    monkeypatch.setattr(rag_service, "get_embeddings", lambda texts, model=None: _fake_embedding(texts))
    text = open(SAMPLE_PATH, "r", encoding="utf-8").read()
    doc_id = rag_service.process_document(text, doc_name="sample", force_reindex=True)
    monkeypatch.setattr(
        generation_service,
        "chat_completion",
        lambda *args, **kwargs: (_ for _ in ()).throw(QuotaExhaustedError()),
    )

    response = create_app().test_client().post(
        "/api/quiz/", json={"doc_id": doc_id, "count": 5}
    )

    assert response.status_code == 200
    assert response.get_json()["generation_method"] == "local-fallback"
    assert response.get_json()["questions"]


def test_topic_grouping_and_diversity(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    text = open(SAMPLE_PATH, 'r', encoding='utf-8').read()
    # count embeddings calls to ensure reuse
    calls = {'count': 0}

    def fake_get_embeddings(texts, model=None):
        calls['count'] += 1
        return _fake_embedding(texts)

    monkeypatch.setattr(rag_service, 'get_embeddings', fake_get_embeddings)
    monkeypatch.setattr(generation_service, 'get_embeddings', fake_get_embeddings)
    # relax grouping threshold for this test so our deterministic embeddings produce multiple groups
    monkeypatch.setattr(rag_service, '_assign_topic_groups', lambda chunks: rag_service._assign_topic_groups_orig(chunks, threshold=0.35))

    doc_id = rag_service.process_document(text, doc_name='sample')
    chunks = vector_store.get_document_chunks(doc_id)
    # ensure topic groups assigned
    topic_groups = set(c.get('source_meta', {}).get('topic_group') for c in chunks)
    topic_groups.discard(None)
    assert len(topic_groups) >= 2, 'Expect multiple topic groups'

    # test retrieve_relevant diversity-aware selection
    selected = rag_service.retrieve_relevant(doc_id, 'neural networks', top_k=5, candidate_k=20)
    assert len(selected) <= 5
    sel_groups = set(c.get('topic_group') for c in selected)
    assert len(sel_groups) >= 2, 'Selected chunks should come from multiple topic groups when possible'

    # embeddings should have been produced only once during process_document
    assert calls['count'] == 1


def test_redundancy_removal(monkeypatch):
    # create a document with repeated paragraphs
    repeated = 'Topic X\n\nThis is repeated.\n\n' * 10
    monkeypatch.setattr(rag_service, 'get_embeddings', lambda texts, model=None: _fake_embedding(texts))
    monkeypatch.setattr(generation_service, 'get_embeddings', lambda texts, model=None: _fake_embedding(texts))
    doc_id = rag_service.process_document(repeated, doc_name='repeated')
    selected = rag_service.retrieve_relevant(doc_id, 'repeated', top_k=5, candidate_k=20)
    # ensure duplicates removed
    texts = [c['chunk_text'] for c in selected]
    assert len(texts) == len(set(t[:200] for t in texts))


def test_generation_pipeline_with_mocked_openai(monkeypatch):
    # Ensure generation_service uses context and validation
    text = open(SAMPLE_PATH, 'r', encoding='utf-8').read()
    # patch embeddings for generation pipeline
    monkeypatch.setattr(rag_service, 'get_embeddings', lambda texts, model=None: _fake_embedding(texts))
    monkeypatch.setattr(generation_service, 'get_embeddings', lambda texts, model=None: _fake_embedding(texts))

    # Mock chat_completion to return JSON with duplicates and check validation filters
    def fake_chat(messages, model=None, temperature=0.0, max_tokens=None):
        # return duplicate flashcards and malformed extra fields
        resp = {
            'choices': [
                {'message': {
                    'content': json.dumps({
                        'flashcards': [
                            {'id': 'fc1', 'question': 'What is ML?', 'answer': 'Machine learning is ...', 'source_chunk_ids': ['c1'], 'topic': 'ML'},
                            {'id': 'fc2', 'question': 'What is ML?', 'answer': 'Machine learning is ...', 'source_chunk_ids': ['c1'], 'topic': 'ML'},
                        ]
                    })
                }}
            ]
        }
        return resp

    # patch chat_completion for generation_service as it imports it directly
    monkeypatch.setattr(generation_service, 'chat_completion', fake_chat)
    cards = generation_service.rag_generate_flashcards(text, count=5)
    # duplicates should be removed by validation
    qs = [c['question'] for c in cards]
    assert len(qs) == len(set(qs))

    # Now test quiz generation with proper structure
    def fake_chat_quiz(messages, model=None, temperature=0.0, max_tokens=None):
        return {
            'choices': [
                {'message': {
                    'content': json.dumps({
                        'questions': [
                            {
                                'id': 'q1',
                                'question': 'What is a neural network?',
                                'options': ['A set of layers', 'A pizza', 'A car', 'An animal'],
                                'correct_answer': 'A set of layers',
                                'explanation': 'Supported by the context',
                                'source_chunk_ids': ['c2'],
                                'topic': 'Neural Networks'
                            }
                        ]
                    })
                }}
            ]
        }

    monkeypatch.setattr(generation_service, 'chat_completion', fake_chat_quiz)
    questions = generation_service.rag_generate_quiz(text, count=3)
    assert len(questions) <= 3
    for q in questions:
        assert 'options' in q and len(q['options']) == 4
        assert len(set(q['options'])) == 4
        assert q['correct_answer'] in q['options']

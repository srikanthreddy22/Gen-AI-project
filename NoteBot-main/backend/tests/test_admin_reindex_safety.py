import os
import sys
import json
import copy

TEST_ROOT = os.path.dirname(__file__)
BACKEND_ROOT = os.path.abspath(os.path.join(TEST_ROOT, '..'))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app import create_app
from app.services import rag_service, vector_store


def setup_module():
    os.environ['ADMIN_API_KEY'] = 'test-admin-key'


def teardown_module():
    os.environ.pop('ADMIN_API_KEY', None)


def _chunk_snapshot(doc_id):
    chunks = vector_store.get_document_chunks(doc_id)
    # canonicalize
    return [(c['chunk_id'], c['chunk_index'], (c.get('chunk_text') or '')[:200], bool(c.get('embedding')), c.get('source_meta', {})) for c in chunks]


def test_admin_routes_require_auth():
    app = create_app()
    client = app.test_client()
    # no header
    r = client.post('/api/admin/reindex', json={'text': 'blah'})
    assert r.status_code == 401
    r = client.get('/api/admin/inspect_index', query_string={'doc_id': 'nope'})
    assert r.status_code == 401
    r = client.post('/api/admin/inspect_retrieval', json={'doc_id': 'x', 'query': 'q'})
    assert r.status_code == 401
    # wrong header
    r = client.post('/api/admin/reindex', json={'text': 'blah'}, headers={'X-Admin-Key': 'wrong'})
    assert r.status_code == 401


def test_reindex_embedding_failure_preserves_old_index(monkeypatch):
    app = create_app()
    client = app.test_client()
    # ensure deterministic embedding for initial index
    monkeypatch.setattr(rag_service, 'get_embeddings', lambda texts, model=None: [[0.1, 0.2, 0.3] for _ in texts])
    text = 'Topic A\n\nContent A.\n\nTopic B\n\nContent B.'
    doc_id = rag_service.process_document(text, doc_name='safety-doc', force_reindex=True)
    assert doc_id
    old_snapshot = _chunk_snapshot(doc_id)

    # now simulate embedding failure
    def bad_emb(texts, model=None):
        raise RuntimeError('embedding backend down')

    monkeypatch.setattr(rag_service, 'get_embeddings', bad_emb)
    r = client.post('/api/admin/reindex', json={'doc_id': doc_id, 'text': text}, headers={'X-Admin-Key': 'test-admin-key'})
    assert r.status_code == 500
    # ensure old index unchanged
    assert _chunk_snapshot(doc_id) == old_snapshot


def test_chunk_storage_failure_preserves_old_index(monkeypatch):
    app = create_app()
    client = app.test_client()
    # prepare initial index
    monkeypatch.setattr(rag_service, 'get_embeddings', lambda texts, model=None: [[0.2, 0.2, 0.2] for _ in texts])
    text = 'X\n\nx1\n\nY\n\ny1'
    doc_id = rag_service.process_document(text, doc_name='safety2', force_reindex=True)
    old_snapshot = _chunk_snapshot(doc_id)

    # make write to temp DB fail
    def fail_write(db_path, d_id, d_name, chunks):
        raise RuntimeError('disk full')

    monkeypatch.setattr(vector_store, 'add_document_chunks_to_dbpath', fail_write)
    r = client.post('/api/admin/reindex', json={'doc_id': doc_id, 'text': text}, headers={'X-Admin-Key': 'test-admin-key'})
    assert r.status_code == 500
    # ensure old index unchanged
    assert _chunk_snapshot(doc_id) == old_snapshot


def test_topic_grouping_failure_does_not_corrupt(monkeypatch):
    app = create_app()
    client = app.test_client()
    # baseline embeddings
    monkeypatch.setattr(rag_service, 'get_embeddings', lambda texts, model=None: [[0.3, 0.3, 0.3] for _ in texts])
    text = 'T1\n\nAlpha\n\nT2\n\nBeta'
    doc_id = rag_service.process_document(text, doc_name='safety3', force_reindex=True)
    old_snapshot = _chunk_snapshot(doc_id)

    # now make grouping fail during prepare
    def bad_group(chunks, threshold=0.78):
        raise RuntimeError('group fail')

    monkeypatch.setattr(rag_service, '_assign_topic_groups', bad_group)
    # embedding generation should still work (we mocked get_embeddings)
    r = client.post('/api/admin/reindex', json={'doc_id': doc_id, 'text': text}, headers={'X-Admin-Key': 'test-admin-key'})
    # reindex should succeed even if grouping fails (grouping is best-effort)
    assert r.status_code == 200
    # ensure new index exists and has chunks
    new_snapshot = _chunk_snapshot(doc_id)
    assert len(new_snapshot) >= 1


def test_retry_after_failed_reindex(monkeypatch):
    app = create_app()
    client = app.test_client()
    monkeypatch.setattr(rag_service, 'get_embeddings', lambda texts, model=None: [[0.4, 0.4, 0.4] for _ in texts])
    text = 'Retry\n\none\n\nRetry\n\ntwo'
    doc_id = rag_service.process_document(text, doc_name='safety4', force_reindex=True)
    old_snapshot = _chunk_snapshot(doc_id)

    # first attempt: make temp write fail
    def fail_write(db_path, d_id, d_name, chunks):
        raise RuntimeError('temp write failed')

    monkeypatch.setattr(vector_store, 'add_document_chunks_to_dbpath', fail_write)
    r1 = client.post('/api/admin/reindex', json={'doc_id': doc_id, 'text': text}, headers={'X-Admin-Key': 'test-admin-key'})
    assert r1.status_code == 500
    assert _chunk_snapshot(doc_id) == old_snapshot

    # now allow successful write
    monkeypatch.setattr(vector_store, 'add_document_chunks_to_dbpath', lambda db_path, d_id, d_name, chunks: vector_store.add_document_chunks_to_dbpath.__wrapped__(db_path, d_id, d_name, chunks) if hasattr(vector_store.add_document_chunks_to_dbpath, '__wrapped__') else vector_store.init_db_at_path(db_path) or vector_store.add_document_chunks_to_dbpath.__call__(db_path, d_id, d_name, chunks))
    # The above is defensive; simpler approach: reset by reloading function from source
    import importlib
    import app.services.vector_store as vs_mod
    importlib.reload(vs_mod)
    # ensure vector_store reference updated
    from app.services import vector_store as vs

    r2 = client.post('/api/admin/reindex', json={'doc_id': doc_id, 'text': text}, headers={'X-Admin-Key': 'test-admin-key'})
    assert r2.status_code == 200
    new_snapshot = _chunk_snapshot(doc_id)
    assert new_snapshot != old_snapshot


def test_no_duplicate_chunks_after_reindex(monkeypatch):
    app = create_app()
    client = app.test_client()
    monkeypatch.setattr(rag_service, 'get_embeddings', lambda texts, model=None: [[0.5, 0.5, 0.5] for _ in texts])
    text = 'Unique\n\none\n\nUnique\n\none2'
    doc_id = rag_service.process_document(text, doc_name='safety5', force_reindex=True)

    r = client.post('/api/admin/reindex', json={'doc_id': doc_id, 'text': text}, headers={'X-Admin-Key': 'test-admin-key'})
    assert r.status_code == 200
    chunks = vector_store.get_document_chunks(doc_id)
    ids = [c['chunk_id'] for c in chunks]
    assert len(ids) == len(set(ids))
    idxs = [c['chunk_index'] for c in chunks]
    assert len(idxs) == len(set(idxs))


def test_admin_endpoints_do_not_leak_secrets(monkeypatch):
    app = create_app()
    client = app.test_client()
    os.environ['OPENAI_API_KEY'] = 'openai-secret'
    os.environ['ADMIN_API_KEY'] = 'test-admin-key'

    # create a doc
    monkeypatch.setattr(rag_service, 'get_embeddings', lambda texts, model=None: [[0.6, 0.6, 0.6] for _ in texts])
    text = 'Leak\n\ncheck\n\nLeak2'
    doc_id = rag_service.process_document(text, doc_name='leakdoc', force_reindex=True)

    # inspect_index
    r = client.get(f'/api/admin/inspect_index?doc_id={doc_id}', headers={'X-Admin-Key': 'test-admin-key'})
    assert r.status_code == 200
    body = json.dumps(r.get_json())
    assert 'test-admin-key' not in body
    assert 'openai-secret' not in body

    # inspect_retrieval
    r = client.post('/api/admin/inspect_retrieval', json={'doc_id': doc_id, 'query': 'Leak'}, headers={'X-Admin-Key': 'test-admin-key'})
    assert r.status_code == 200
    body = json.dumps(r.get_json())
    assert 'test-admin-key' not in body
    assert 'openai-secret' not in body
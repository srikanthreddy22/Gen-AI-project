import os
import sys

TEST_ROOT = os.path.dirname(__file__)
BACKEND_ROOT = os.path.abspath(os.path.join(TEST_ROOT, '..'))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

import json
from app import create_app
from app.services import rag_service, vector_store


def setup_module():
    os.environ['ADMIN_API_KEY'] = 'test-admin-key'
    os.environ['OPENAI_API_KEY'] = 'sk-test'


def teardown_module():
    os.environ.pop('ADMIN_API_KEY', None)
    os.environ.pop('OPENAI_API_KEY', None)


def snapshot_chunks(doc_id):
    return [(c['chunk_id'], c['chunk_index'], c['chunk_text']) for c in vector_store.get_document_chunks(doc_id)]


def test_embedding_failure_preserves_old_index(monkeypatch):
    app = create_app()
    client = app.test_client()
    text = 'A topic\n\nContent A.\n\nAnother section B\n\nContent B.'

    # ensure stable embeddings for initial index
    monkeypatch.setattr(rag_service, 'get_embeddings', lambda texts, model=None: [[0.1, 0.2] for _ in texts])
    doc_id = rag_service.process_document(text, doc_name='doc1', force_reindex=True)
    assert doc_id
    before = snapshot_chunks(doc_id)

    # now simulate embedding failure during reindex
    monkeypatch.setattr(rag_service, 'get_embeddings', lambda texts, model=None: (_ for _ in ()).throw(Exception('emb fail')))
    r = client.post('/api/admin/reindex', json={'doc_id': doc_id, 'text': text}, headers={'X-Admin-Key': 'test-admin-key'})
    assert r.status_code == 500

    after = snapshot_chunks(doc_id)
    assert before == after


def test_chunk_storage_failure_cleanup(monkeypatch):
    app = create_app()
    client = app.test_client()
    text = 'X\n\nContent X.'

    # stable embeddings
    monkeypatch.setattr(rag_service, 'get_embeddings', lambda texts, model=None: [[0.3, 0.4] for _ in texts])
    doc_id = rag_service.process_document(text, doc_name='doc2', force_reindex=True)
    before = snapshot_chunks(doc_id)

    # now simulate failure when writing temp DB
    def fail_add(db_path, d_id, d_name, chunks):
        raise Exception('disk write error')

    monkeypatch.setattr(vector_store, 'add_document_chunks_to_dbpath', fail_add)

    r = client.post('/api/admin/reindex', json={'doc_id': doc_id, 'text': text}, headers={'X-Admin-Key': 'test-admin-key'})
    assert r.status_code == 500

    after = snapshot_chunks(doc_id)
    assert before == after


def test_topic_grouping_failure_nonfatal(monkeypatch):
    app = create_app()
    client = app.test_client()
    text = 'T1\n\nalpha\n\nT2\n\nbeta'

    # stable embeddings
    monkeypatch.setattr(rag_service, 'get_embeddings', lambda texts, model=None: [[0.5, 0.6] for _ in texts])
    doc_id = rag_service.process_document(text, doc_name='doc3', force_reindex=True)
    before = snapshot_chunks(doc_id)

    # make grouping fail but ensure prepare_document_chunks handles it
    monkeypatch.setattr(rag_service, '_assign_topic_groups', lambda chunks, threshold=0.78: (_ for _ in ()).throw(Exception('group fail')))

    r = client.post('/api/admin/reindex', json={'doc_id': doc_id, 'text': text}, headers={'X-Admin-Key': 'test-admin-key'})
    # grouping is best-effort; reindex should still succeed
    assert r.status_code == 200

    after = snapshot_chunks(doc_id)
    # chunk count should be >=1 and consistent (no duplicates)
    assert len(after) >= 1
    ids = [c[0] for c in after]
    assert len(ids) == len(set(ids))


def test_reindex_retry_after_failure(monkeypatch):
    app = create_app()
    client = app.test_client()
    text = 'Retry topic\n\ncontent'

    # initial good embeddings
    monkeypatch.setattr(rag_service, 'get_embeddings', lambda texts, model=None: [[0.7, 0.8] for _ in texts])
    doc_id = rag_service.process_document(text, doc_name='doc4', force_reindex=True)
    before = snapshot_chunks(doc_id)

    # first attempt fails
    monkeypatch.setattr(rag_service, 'get_embeddings', lambda texts, model=None: (_ for _ in ()).throw(Exception('transient')))
    r = client.post('/api/admin/reindex', json={'doc_id': doc_id, 'text': text}, headers={'X-Admin-Key': 'test-admin-key'})
    assert r.status_code == 500
    assert snapshot_chunks(doc_id) == before

    # second attempt succeeds
    monkeypatch.setattr(rag_service, 'get_embeddings', lambda texts, model=None: [[0.9, 1.0] for _ in texts])
    r2 = client.post('/api/admin/reindex', json={'doc_id': doc_id, 'text': text}, headers={'X-Admin-Key': 'test-admin-key'})
    assert r2.status_code == 200

    after = snapshot_chunks(doc_id)
    assert len(after) >= 1
    ids = [c[0] for c in after]
    assert len(ids) == len(set(ids))


def test_unauthorized_access_all_routes():
    app = create_app()
    client = app.test_client()
    # no key
    r = client.post('/api/admin/reindex', json={})
    assert r.status_code == 401
    r = client.get('/api/admin/inspect_index?doc_id=missing')
    assert r.status_code == 401
    r = client.post('/api/admin/inspect_retrieval', json={'doc_id': 'x', 'query': 'y'})
    assert r.status_code == 401

    # invalid key
    r = client.post('/api/admin/reindex', json={}, headers={'X-Admin-Key': 'bad'})
    assert r.status_code == 401


def test_no_secrets_in_responses(monkeypatch):
    app = create_app()
    client = app.test_client()
    text = 'S\n\nSecret test'
    monkeypatch.setattr(rag_service, 'get_embeddings', lambda texts, model=None: [[0.2, 0.2] for _ in texts])
    doc_id = rag_service.process_document(text, doc_name='doc5', force_reindex=True)

    # inspect index
    r = client.get(f'/api/admin/inspect_index?doc_id={doc_id}', headers={'X-Admin-Key': 'test-admin-key'})
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'sk-test' not in body
    assert 'test-admin-key' not in body

    # inspect retrieval
    r2 = client.post('/api/admin/inspect_retrieval', json={'doc_id': doc_id, 'query': 'S'}, headers={'X-Admin-Key': 'test-admin-key'})
    assert r2.status_code == 200
    body2 = r2.get_data(as_text=True)
    assert 'sk-test' not in body2
    assert 'test-admin-key' not in body2


def test_db_consistency_after_success(monkeypatch):
    app = create_app()
    client = app.test_client()
    text = 'Consistent\n\nOne\n\nTwo\n\nThree'
    monkeypatch.setattr(rag_service, 'get_embeddings', lambda texts, model=None: [[0.11, 0.12] for _ in texts])
    doc_id = rag_service.process_document(text, doc_name='doc6', force_reindex=True)

    # reindex successfully
    r = client.post('/api/admin/reindex', json={'doc_id': doc_id, 'text': text}, headers={'X-Admin-Key': 'test-admin-key'})
    assert r.status_code == 200

    chunks = vector_store.get_document_chunks(doc_id)
    ids = [c['chunk_id'] for c in chunks]
    assert len(ids) == len(set(ids))
    # ensure chunk_index unique per doc
    idxs = [c['chunk_index'] for c in chunks]
    assert len(idxs) == len(set(idxs))
    # ensure embeddings exist
    assert all(c.get('embedding') for c in chunks)
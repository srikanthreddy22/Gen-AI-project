import os
import sys
import json

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


def test_admin_protection():
    app = create_app()
    client = app.test_client()
    # missing key
    r = client.post('/api/admin/reindex', json={})
    assert r.status_code == 401
    # wrong key
    r = client.post('/api/admin/reindex', json={}, headers={'X-Admin-Key': 'wrong'})
    assert r.status_code == 401


def test_reindex_and_inspect(monkeypatch, tmp_path):
    app = create_app()
    client = app.test_client()
    # prepare a simple text
    text = 'Topic A\n\nA content about A.\n\nTopic B\n\nB content about B.'
    # mock embeddings to deterministic values
    monkeypatch.setattr(rag_service, 'get_embeddings', lambda texts, model=None: [[0.1,0.2,0.3] for _ in texts])

    # process document to create initial index
    doc_id = rag_service.process_document(text, doc_name='testdoc', force_reindex=True)
    assert doc_id

    # inspect index without admin key -> 401
    r = client.get(f'/api/admin/inspect_index?doc_id={doc_id}')
    assert r.status_code == 401

    # with correct key
    r = client.get(f'/api/admin/inspect_index?doc_id={doc_id}', headers={'X-Admin-Key': 'test-admin-key'})
    assert r.status_code == 200
    data = r.get_json()
    assert data['document_id'] == doc_id
    assert data['total_chunks'] >= 1
    assert 'chunks' in data

    # test reindex: provide text and doc_id
    r = client.post('/api/admin/reindex', json={'doc_id': doc_id, 'text': text}, headers={'X-Admin-Key': 'test-admin-key'})
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('success') is True
    assert 'chunks_created' in data

    # test retrieval inspection
    r = client.post('/api/admin/inspect_retrieval', json={'doc_id': doc_id, 'query': 'Topic A', 'top_k': 2}, headers={'X-Admin-Key': 'test-admin-key'})
    assert r.status_code == 200
    data = r.get_json()
    assert data['document_id'] == doc_id
    assert data['query'] == 'Topic A'
    assert 'candidates' in data and 'selected' in data
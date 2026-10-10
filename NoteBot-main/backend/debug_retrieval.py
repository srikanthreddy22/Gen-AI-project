from app.services import rag_service, vector_store, generation_service
import os
TEST_ROOT = os.path.join(os.path.dirname(__file__), 'tests')
SAMPLE = os.path.join(TEST_ROOT, 'sample_multi_topic.txt')
text = open(SAMPLE,'r',encoding='utf-8').read()
# test-like setup
vector_store.DB_PATH = os.path.join(TEST_ROOT, '.vector_store_test.db')
vector_store.init_db()
rag_service.DEFAULT_CHUNK_CHARS = 80
rag_service.DEFAULT_CHUNK_OVERLAP = 20

def _fake_embedding(texts, model=None):
    out=[]
    for t in texts:
        h = sum(ord(c) for c in t) % 1000
        out.append([((h + i) % 100)/100.0 for i in range(3)])
    return out

rag_service.get_embeddings = _fake_embedding
generation_service.get_embeddings = _fake_embedding
# ensure original preserved
if not hasattr(rag_service, '_assign_topic_groups_orig'):
    rag_service._assign_topic_groups_orig = rag_service._assign_topic_groups
# relax threshold
rag_service._assign_topic_groups = lambda chunks: rag_service._assign_topic_groups_orig(chunks, threshold=0.35)

doc_id = rag_service.process_document(text, doc_name='sample')
all_chunks = vector_store.get_document_chunks(doc_id)
print('total_chunks', len(all_chunks))
print('doc topic groups:', set((c.get('source_meta') or {}).get('topic_group') for c in all_chunks))

selected = rag_service.retrieve_relevant(doc_id, 'neural networks', top_k=5, candidate_k=20, debug=True)
print('selected count', len(selected))
for s in selected:
    print('sel:', s.get('chunk_index'), s.get('topic_group'), s.get('score'))

candidates = []
q_emb = rag_service.get_embeddings(['neural networks'])[0]
for score, ch in vector_store.similarity_search(doc_id, q_emb, top_k=20, min_score=0.0):
    candidates.append((score, (ch.get('chunk_index'), (ch.get('source_meta') or {}).get('topic_group'))))
print('candidates:')
for c in candidates:
    print(c)

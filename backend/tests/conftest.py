import atexit
import os
import shutil
import tempfile
import uuid

import pytest


_test_uploads = tempfile.mkdtemp(prefix="notebot-test-uploads-")
atexit.register(shutil.rmtree, _test_uploads, ignore_errors=True)
_test_chroma_root = tempfile.mkdtemp(prefix="notebot-test-chroma-")
atexit.register(shutil.rmtree, _test_chroma_root, ignore_errors=True)

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["NOTEBOT_AUTO_CREATE_SCHEMA"] = "true"
os.environ["UPLOAD_FOLDER"] = _test_uploads


@pytest.fixture(autouse=True)
def isolate_chroma_store(monkeypatch):
    monkeypatch.setenv("CHROMA_PERSIST_DIRECTORY", os.path.join(_test_chroma_root, uuid.uuid4().hex))
    monkeypatch.setenv("NOTEBOT_DISABLE_LEGACY_VECTOR_MIGRATION", "true")

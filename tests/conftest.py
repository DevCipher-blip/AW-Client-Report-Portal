import os
import tempfile

import pytest

os.environ["RAILWAY_DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

import app as portal_app


@pytest.fixture
def client():
    db = portal_app.get_db()
    db.executescript("DELETE FROM reports; DELETE FROM clients;")
    db.commit()
    db.close()
    return portal_app.app.test_client()

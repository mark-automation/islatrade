"""Isolate every test run from the live islatrade.db.

Sets ISLATRADE_DB to a per-process scratch file BEFORE main is imported;
main.py reads that env var at module load, so all schema/migration/seed
writes land on the copy. Prod DB is never touched by tests.
"""
import os
import tempfile
from pathlib import Path

_TMPDB = Path(tempfile.gettempdir()) / f"islatrade-test-{os.getpid()}.db"
os.environ["ISLATRADE_DB"] = str(_TMPDB)
os.environ["ISLATRADE_RL_LIMIT"] = "1000"  # tests share one client IP; don't trip the limiter

from fastapi.testclient import TestClient  # noqa: E402 (after env set)
import pytest  # noqa: E402

from main import app, q  # noqa: E402

DEMO_EMAIL = "demo@islatrade.ph"
DEMO_PW = "islatrade"
ADMIN_EMAIL = "admin@islatrade.ph"
ADMIN_PW = "admin123"


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture()
def anon():
    """Fresh cookie-less client: for unauthenticated checks that must not
    inherit whatever session the shared `client` picked up earlier."""
    return TestClient(app)


def login(client, email=DEMO_EMAIL, pw=DEMO_PW):
    """Log a supplier in on this client (cookies persist per TestClient)."""
    return client.post("/login", data={"email": email, "pw": pw}, follow_redirects=False)


def unique_email(prefix="buyer"):
    import uuid
    return f"{prefix}-{uuid.uuid4().hex[:8]}@test.ph"


def first_product():
    return q("SELECT * FROM products ORDER BY id LIMIT 1", one=True)

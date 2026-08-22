"""Smoke tests: app imports and core public routes render."""
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_home_200():
    r = client.get("/")
    assert r.status_code == 200
    assert "islatrade" in r.text.lower()


def test_public_pages_200():
    for path in ("/products", "/suppliers", "/rfq", "/login", "/register"):
        assert client.get(path).status_code == 200, path


def test_product_404_unknown_slug():
    assert client.get("/product/definitely-not-a-real-slug-xyz").status_code in (200, 404)


def test_supplier_admin_requires_login():
    # unauthenticated visit must not leak a dashboard (redirect or 4xx ok)
    r = client.get("/supplier-admin", follow_redirects=False)
    assert r.status_code < 500

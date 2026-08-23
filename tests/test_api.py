"""JSON API, SEO endpoints, health."""
import xml.etree.ElementTree as ET


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and isinstance(body["ts"], float)


def test_api_products_shape_and_filters(client):
    rows = client.get("/api/products").json()
    assert 0 < len(rows) <= 50
    for row in rows:
        assert {"id", "name", "slug", "price_min", "price_max", "unit", "moq",
                "cat", "supplier"} <= set(row)

    hit = client.get("/api/products", params={"q_": "PCB"}).json()
    assert hit and all("pcb" in r["name"].lower() for r in hit)

    food = client.get("/api/products", params={"cat": "food"}).json()
    assert food and all(r["cat"] == "food" for r in food)

    assert len(client.get("/api/products", params={"limit": 2}).json()) == 2


def test_api_rfqs_reflects_new_rfq(client):
    from tests.conftest import unique_email
    email = unique_email("api")
    client.post("/rfq", data={"name": "API Buyer", "email": email}, follow_redirects=False)
    # F-1: rfq PII now requires an admin session
    assert client.get("/api/rfqs").status_code == 401
    client.post("/login", data={"email": "admin@islatrade.ph", "pw": "admin123"})
    rfqs = client.get("/api/rfqs").json()
    assert any(r["email"] == email for r in rfqs)


def test_robots_blocks_private_areas(client):
    txt = client.get("/robots.txt").text
    for private in ("/supplier-admin", "/login", "/register", "/logout"):
        assert f"Disallow: {private}" in txt
    assert "Sitemap:" in txt


def test_sitemap_is_valid_xml_with_product_urls(client):
    r = client.get("/sitemap.xml")
    assert r.status_code == 200 and "xml" in r.headers["content-type"]
    root = ET.fromstring(r.text)
    locs = [e.text for e in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    assert "https://islatrade.ph/products" in locs
    assert any("/product/" in u for u in locs)


def test_static_assets_served(client):
    assert client.get("/static/styles.css").status_code == 200

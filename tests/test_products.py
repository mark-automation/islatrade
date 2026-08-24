"""Supplier product management: create, edit, delete, ownership guard."""
from main import q
from tests.conftest import login


def test_new_product_requires_login(anon):
    r = anon.post("/supplier-admin/products/new", data={"name": "X"},
                  follow_redirects=False)
    assert r.status_code == 302 and "/login" in r.headers["location"]


def test_product_create_edit_delete_lifecycle(client):
    login(client)  # demo supplier

    # create
    r = client.post("/supplier-admin/products/new", data={
        "name": "Heartbeat Test Widget", "category_id": "1",
        "price_min": "10", "price_max": "20", "unit": "per pc", "moq": "5",
        "lead_days": "7", "descr": "Created by the automated test suite.",
    }, follow_redirects=False)
    assert r.status_code == 302
    prod = q("SELECT * FROM products WHERE name='Heartbeat Test Widget'", one=True)
    assert prod and prod["image_url"]  # auto-filled from category or placeholder

    # visible via public search + supplier dashboard.
    # (v2 paginates /products at 24/page ordered by featured/orders — a brand-new
    # zero-order item lands below the seeded catalog, so discoverability = search)
    assert "Heartbeat Test Widget" in client.get("/products", params={"q_": "Heartbeat"}).text
    assert "Heartbeat Test Widget" in client.get("/supplier-admin").text

    # edit
    r = client.post(f"/supplier-admin/products/{prod['id']}/edit", data={
        "name": "Heartbeat Test Widget v2", "price_min": "12", "price_max": "24",
        "unit": "per pc", "moq": "5", "lead_days": "7", "descr": "edited",
        "image_url": "",
    }, follow_redirects=False)
    assert r.status_code == 302
    row = q("SELECT * FROM products WHERE id=?", (prod["id"],), one=True)
    assert row["name"] == "Heartbeat Test Widget v2" and row["price_min"] == 12

    # ownership guard: another supplier's product must survive a delete attempt
    other = q("SELECT id FROM products WHERE supplier_id != ? LIMIT 1",
              (prod["supplier_id"],), one=True)
    client.post(f"/supplier-admin/products/{other['id']}/delete", follow_redirects=False)
    assert q("SELECT id FROM products WHERE id=?", (other["id"],), one=True)

    # delete own -> gone
    client.post(f"/supplier-admin/products/{prod['id']}/delete", follow_redirects=False)
    assert not q("SELECT id FROM products WHERE id=?", (prod["id"],), one=True)


def test_edit_requires_name(client):
    login(client)
    mine = q("SELECT id FROM products WHERE supplier_id=(SELECT id FROM suppliers WHERE email='demo@islatrade.ph') LIMIT 1", one=True)
    if not mine:
        return
    r = client.post(f"/supplier-admin/products/{mine['id']}/edit", data={"name": ""},
                    follow_redirects=False)
    assert r.status_code == 302  # bounced to login/dashboard, no change applied

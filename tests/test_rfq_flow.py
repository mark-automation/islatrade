"""RFQ pipeline end-to-end: submit -> notification -> quote -> track -> messages."""
from main import q
from tests.conftest import first_product, login, unique_email


def test_rfq_form_renders(client):
    assert client.get("/rfq").status_code == 200
    p = first_product()
    r = client.get(f"/rfq?product={p['id']}")
    assert r.status_code == 200 and p["name"] in r.text


def test_rfq_requires_name_and_email(client):
    r = client.post("/rfq", data={"name": "", "email": ""}, follow_redirects=False)
    assert r.status_code == 302 and "err=1" in r.headers["location"]


def test_full_rfq_to_quote_flow(client):
    buyer = unique_email()
    p = first_product()

    # 1. buyer submits RFQ against a product -> supplier gets a notification
    r = client.post("/rfq", data={
        "name": "Test Buyer", "email": buyer, "phone": "+63 917 000 0000",
        "company": "Buyer Corp", "qty": "100", "message": "Need quote pls",
        "product": str(p["id"]), "category": "0",
    }, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/rfq/sent"

    rfq = q("SELECT * FROM rfqs WHERE email=?", (buyer,), one=True)
    assert rfq and rfq["product_id"] == p["id"]
    notif = q("SELECT * FROM notifications WHERE rfq_id=? AND supplier_id=?",
              (rfq["id"], p["supplier_id"]), one=True)
    assert notif and "Test Buyer" in notif["text"]

    # 2. supplier logs in, sees the RFQ in the dashboard inbox, quotes it
    # (demo account is stamped onto the first seeded supplier, which owns first_product)
    login(client)
    dash = client.get("/supplier-admin")
    assert dash.status_code == 200 and "New RFQ from Test Buyer" in dash.text

    r = client.post(f"/supplier-admin/rfq/{rfq['id']}/quote",
                    data={"price": "1234.5", "lead_days": "10", "message": "Here you go"},
                    follow_redirects=False)
    assert r.status_code == 302
    quote = q("SELECT * FROM quotes WHERE rfq_id=?", (rfq["id"],), one=True)
    assert quote and quote["price"] == 1234.5

    # 3. buyer tracks by email and sees the quote
    track = client.get("/rfq/tracking", params={"email": buyer})
    assert track.status_code == 200 and "1234.5" in track.text

    # 4. two-way messaging: buyer posts, supplier replies, both sides see both texts
    client.post("/rfq/tracking/message",
                data={"rfq_id": rfq["id"], "email": buyer, "text": "Can you do 1200?"},
                follow_redirects=False)
    client.post(f"/supplier-admin/rfq/{rfq['id']}/message",
                data={"text": "Best we can do is 1210."}, follow_redirects=False)
    msgs = q("SELECT * FROM messages WHERE rfq_id=? ORDER BY created", (rfq["id"],))
    senders = [m["sender"] for m in msgs]
    assert senders == ["buyer", "supplier"]
    track2 = client.get("/rfq/tracking", params={"email": buyer})
    assert "1200" in track2.text and "1210" in track2.text


def test_category_rfq_notifies_all_suppliers_in_category(client):
    from main import CATEGORIES
    cat = q("SELECT * FROM categories WHERE slug=?", (CATEGORIES[1][1],), one=True)  # furniture
    buyer = unique_email()
    n_before = q("SELECT COUNT(*) n FROM notifications", one=True)["n"]
    r = client.post("/rfq", data={"name": "Cat Buyer", "email": buyer,
                                  "category": str(cat["id"])}, follow_redirects=False)
    assert r.status_code == 302
    rfq = q("SELECT * FROM rfqs WHERE email=?", (buyer,), one=True)
    hits = q("SELECT COUNT(*) n FROM notifications WHERE rfq_id=?", (rfq["id"],), one=True)["n"]
    suppliers_in_cat = q("SELECT COUNT(DISTINCT supplier_id) n FROM products WHERE category_id=?",
                         (cat["id"],), one=True)["n"]
    assert hits == suppliers_in_cat > 0
    assert q("SELECT COUNT(*) n FROM notifications", one=True)["n"] >= n_before + hits


def test_buyer_message_requires_all_fields(client):
    r = client.post("/rfq/tracking/message", data={"rfq_id": "0", "email": "", "text": ""},
                    follow_redirects=False)
    assert r.status_code == 302  # silently bounced back to tracking page


def test_tracking_without_email_is_empty_page(client):
    r = client.get("/rfq/tracking")
    assert r.status_code == 200

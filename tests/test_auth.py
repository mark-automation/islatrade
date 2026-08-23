"""Auth flows: register validation, login, sessions, admin gate."""
from tests.conftest import ADMIN_EMAIL, ADMIN_PW, DEMO_EMAIL, DEMO_PW, login, unique_email


def test_register_rejects_missing_fields(client):
    r = client.post("/register", data={"company": "", "email": "", "pw": ""})
    assert r.status_code == 400
    assert "required" in r.text.lower()


def test_register_rejects_short_password(client):
    r = client.post("/register", data={"company": "Acme", "email": unique_email(), "pw": "123"})
    assert r.status_code == 400
    assert "6+" in r.text


def test_register_rejects_duplicate_email(client):
    r = client.post("/register", data={"company": "Dup", "email": DEMO_EMAIL, "pw": "secret7"})
    assert r.status_code == 400
    assert "already registered" in r.text.lower()


def test_register_success_creates_session_and_dashboard(client):
    email = unique_email("sup")
    r = client.post("/register", data={"company": "Test Goods Co", "email": email, "pw": "hunter22"},
                    follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/supplier-admin"
    assert client.cookies.get("it_sess")  # session cookie actually set
    dash = client.get("/supplier-admin")  # cookie persisted on client
    assert dash.status_code == 200
    assert "Test Goods Co" in dash.text


def test_login_wrong_password_401(client):
    r = client.post("/login", data={"email": DEMO_EMAIL, "pw": "wrong-pass"})
    assert r.status_code == 401
    assert "invalid" in r.text.lower()


def test_login_unknown_email_401(client):
    assert client.post("/login", data={"email": "ghost@test.ph", "pw": "whatever1"}).status_code == 401


def test_login_demo_supplier_redirects_to_dashboard(client):
    r = login(client)
    assert r.status_code == 302 and r.headers["location"] == "/supplier-admin"


def test_logout_clears_session(client, anon):
    login(client)
    r = client.get("/logout", follow_redirects=False)
    assert r.status_code == 302
    r2 = anon.get("/supplier-admin", follow_redirects=False)
    assert r2.status_code == 302 and "/login" in r2.headers["location"]


def test_admin_panel_requires_admin(anon, client):
    r = anon.get("/admin-panel", follow_redirects=False)  # anonymous
    assert r.status_code == 302
    login(client)  # demo supplier: not an admin
    r2 = client.get("/admin-panel", follow_redirects=False)
    assert r2.status_code == 302


def test_admin_panel_renders_for_admin(client):
    login(client, ADMIN_EMAIL, ADMIN_PW)
    r = client.get("/admin-panel")
    assert r.status_code == 200
    assert "RFQs" in r.text or "rfqs" in r.text  # stats block present

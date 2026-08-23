"""IslaTrade — The Philippines' B2B Marketplace.

Alibaba-model, PH-first: verified suppliers, product listings, RFQ pipeline.
FastAPI + SQLite + Jinja2. Single process, zero build chain.
Run:  uvicorn main:app --host 127.0.0.1 --port 8500
"""
import os
import sqlite3
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE = Path(__file__).parent
# ISLATRADE_DB lets the test suite redirect all reads/writes to a scratch DB
# (set by tests/conftest.py before import). Unset in prod -> live islatrade.db.
DB = Path(os.environ.get("ISLATRADE_DB") or BASE / "islatrade.db")

app = FastAPI(title="IslaTrade")
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
tpl = Jinja2Templates(directory=str(BASE / "templates"))


# ---------- DB ----------
def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


SCHEMA = """
CREATE TABLE IF NOT EXISTS categories(
  id INTEGER PRIMARY KEY, name TEXT, slug TEXT UNIQUE, icon TEXT, blurb TEXT);
CREATE TABLE IF NOT EXISTS suppliers(
  id INTEGER PRIMARY KEY, name TEXT, slug TEXT UNIQUE, region TEXT, city TEXT,
  industry TEXT, about TEXT, verified INTEGER DEFAULT 1, rating REAL DEFAULT 4.5,
  years INTEGER DEFAULT 3, response_rate INTEGER DEFAULT 90);
CREATE TABLE IF NOT EXISTS products(
  id INTEGER PRIMARY KEY, supplier_id INTEGER REFERENCES suppliers(id),
  category_id INTEGER REFERENCES categories(id), name TEXT, slug TEXT UNIQUE,
  descr TEXT, price_min REAL, price_max REAL, unit TEXT, moq INTEGER,
  lead_days INTEGER, rating REAL DEFAULT 4.6, orders INTEGER DEFAULT 0,
  featured INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS rfqs(
  id INTEGER PRIMARY KEY, product_id INTEGER, category_id INTEGER,
  name TEXT, email TEXT, phone TEXT, company TEXT, qty TEXT, message TEXT,
  created REAL);
CREATE TABLE IF NOT EXISTS sessions(
  token TEXT PRIMARY KEY, supplier_id INTEGER REFERENCES suppliers(id),
  created REAL);
CREATE TABLE IF NOT EXISTS quotes(
  id INTEGER PRIMARY KEY, rfq_id INTEGER REFERENCES rfqs(id),
  supplier_id INTEGER REFERENCES suppliers(id), price REAL,
  lead_days INTEGER, message TEXT, created REAL);
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY, rfq_id INTEGER, sender TEXT,
  supplier_id INTEGER, email TEXT, text TEXT, created REAL);
CREATE TABLE IF NOT EXISTS notifications(
  id INTEGER PRIMARY KEY, supplier_id INTEGER REFERENCES suppliers(id),
  rfq_id INTEGER, text TEXT, read INTEGER DEFAULT 0, created REAL);
CREATE TABLE IF NOT EXISTS reviews(
  id INTEGER PRIMARY KEY, product_id INTEGER REFERENCES products(id),
  author TEXT, email TEXT, rating INTEGER, text TEXT, created REAL);
"""

MIGRATIONS = [
    ("suppliers", "ALTER TABLE suppliers ADD COLUMN email TEXT"),
    ("suppliers", "ALTER TABLE suppliers ADD COLUMN pw_hash TEXT"),
    ("suppliers", "ALTER TABLE suppliers ADD COLUMN is_admin INTEGER DEFAULT 0"),
    ("products", "ALTER TABLE products ADD COLUMN image_url TEXT"),
]


def init_db():
    with db() as con:
        con.executescript(SCHEMA)
        for table, m in MIGRATIONS:
            cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
            if m.split()[3] not in cols:
                try:
                    con.execute(m)
                except Exception:
                    pass
        # backfill product images from category art (idempotent)
        con.execute("""UPDATE products SET image_url=COALESCE(
            '/static/img/cat-'||(SELECT slug FROM categories WHERE id=category_id)||'.svg',
            '/static/img/placeholder.svg')
            WHERE image_url IS NULL OR image_url=''""")


import hashlib
import hmac
import secrets
import time as _t


def hash_pw(pw: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), b"islatrade-salt", 120_000).hex()


def current_supplier(request: Request):
    tok = request.cookies.get("it_sess")
    if not tok:
        return None
    return q("SELECT s.* FROM sessions x JOIN suppliers s ON s.id=x.supplier_id WHERE x.token=? AND x.created>?",
             (tok, _t.time() - 30 * 86400), one=True)


def login_supplier(email: str, pw: str):
    s = q("SELECT * FROM suppliers WHERE email=?", (email.lower().strip(),), one=True)
    if not s or not s["pw_hash"]:
        return None, None
    if not hmac.compare_digest(hash_pw(pw), s["pw_hash"]):
        return None, None
    tok = secrets.token_hex(16)
    with db() as con:
        con.execute("INSERT INTO sessions(token,supplier_id,created) VALUES(?,?,?)",
                    (tok, s["id"], _t.time()))
    return s, tok


# ---------- seed ----------
CATEGORIES = [
    ("Electronics & Components", "electronics", "🔌", "PCBs, modules, cables, consumer electronics assembly"),
    ("Furniture & Fixtures", "furniture", "🪑", "Rattan, acacia, bamboo — world-class PH craftsmanship"),
    ("Food & Agriculture", "food", "🥥", "Coconut products, mangoes, seafood, processed foods"),
    ("Textiles & Garments", "textiles", "🧵", "Apparel, abaca fabrics, home textiles, made-to-order"),
    ("Construction & Materials", "construction", "🏗️", "Cement, steel, lumber, fittings, interior finishes"),
    ("Machinery & Industrial", "machinery", "⚙️", "Packaging machines, CNC, agricultural equipment"),
    ("Health & Wellness", "health", "💊", "Supplements, herbal extracts, PPE, medical devices"),
    ("Packaging & Printing", "packaging", "📦", "Corrugated boxes, labels, eco-packaging, custom prints"),
]

SUPPLIERS = [
    ("Manila Micro Circuits Corp", "Metro Manila", "Quezon City", "Electronics & Components", 4.8, 12, 97),
    ("Cebu Rattan Works", "Central Visayas", "Cebu City", "Furniture & Fixtures", 4.9, 18, 95),
    ("Davao Coco Producers Coop", "Davao Region", "Davao City", "Food & Agriculture", 4.7, 9, 92),
    ("Abaca Textile Mills", "Bicol", "Legazpi", "Textiles & Garments", 4.6, 14, 89),
    ("Hardrock Aggregates PH", "Central Luzon", "Angeles", "Construction & Materials", 4.5, 8, 91),
    ("Laguna Precision Machining", "CALABARZON", "Santa Rosa", "Machinery & Industrial", 4.8, 15, 96),
    ("WellSource Naturals", "Metro Manila", "Makati", "Health & Wellness", 4.7, 6, 94),
    ("PackRight Industries", "Metro Manila", "Valenzuela", "Packaging & Printing", 4.6, 11, 93),
    ("Iloilo Seafood Exporters", "Western Visayas", "Iloilo", "Food & Agriculture", 4.8, 16, 90),
    ("Pampanga Furniture Guild", "Central Luzon", "San Fernando", "Furniture & Fixtures", 4.7, 20, 88),
    ("CDO Agri-Machines", "Northern Mindanao", "Cagayan de Oro", "Machinery & Industrial", 4.5, 7, 87),
    ("Batangas Steel Fab", "CALABARZON", "Batangas City", "Construction & Materials", 4.6, 13, 92),
]

# (name, cat_slug, supplier_idx, pmin, pmax, unit, moq, lead, featured)
PRODUCTS = [
    ("Custom PCB Assembly (SMT/THT)", "electronics", 0, 180, 2400, "per board", 50, 14, 1),
    ("Bluetooth Audio Modules", "electronics", 0, 95, 480, "per 10pcs", 100, 10, 0),
    ("Wire Harness & Cable Assemblies", "electronics", 0, 40, 350, "per set", 200, 12, 0),
    ("Handwoven Rattan Lounge Chair", "furniture", 1, 2800, 4500, "per pc", 20, 21, 1),
    ("Acacia Dining Table (Solid Wood)", "furniture", 1, 12000, 28000, "per pc", 10, 30, 0),
    ("Bamboo Pendant Lamps", "furniture", 9, 650, 1400, "per pc", 30, 18, 1),
    ("Office Desk Sets (Engineered Wood)", "furniture", 9, 3200, 7500, "per set", 15, 20, 0),
    ("Virgin Coconut Oil (VCO) Drums", "food", 2, 8500, 12000, "per 200L drum", 20, 15, 1),
    ("Coconut Charcoal Briquettes", "food", 2, 22, 34, "per kg", 1000, 12, 0),
    ("Carabao Mango Fresh Export Grade", "food", 8, 65, 110, "per kg", 500, 7, 0),
    ("Frozen Tuna Loins (Sashimi Grade)", "food", 8, 280, 420, "per kg", 300, 14, 1),
    ("Dried Mango Slices Premium", "food", 2, 340, 520, "per 5kg carton", 100, 10, 0),
    ("Abaca Fabric Rolls (Handloom)", "textiles", 3, 480, 900, "per roll", 25, 18, 0),
    ("Organic Cotton T-Shirts (Blank)", "textiles", 3, 110, 210, "per dozen", 200, 15, 1),
    ("Barong Tagalog (Piña-Silk Blend)", "textiles", 3, 1800, 5200, "per pc", 50, 25, 1),
    ("Home Textile Sets (Woven Cotton)", "textiles", 3, 950, 2200, "per set", 50, 16, 0),
    ("Ready-Mix Concrete (C40)", "construction", 4, 4200, 4800, "per m³", 25, 3, 0),
    ("Structural Steel Beams (W12)", "construction", 11, 58000, 72000, "per ton", 5, 10, 0),
    ("Kiln-Dried Lumber (Mahogany)", "construction", 4, 18000, 26000, "per m³", 8, 12, 0),
    ("Interior Finish Panels (Bamboo)", "construction", 11, 1250, 2800, "per 20pcs", 20, 15, 1),
    ("CNC Machined Parts (Aluminum)", "machinery", 5, 350, 5000, "per batch", 10, 12, 1),
    ("Automatic Filling Machines", "machinery", 5, 380000, 850000, "per unit", 1, 45, 0),
    ("Rice Milling Equipment", "machinery", 10, 240000, 620000, "per set", 1, 40, 1),
    ("Post-Harvest Dryers (Biomass)", "machinery", 10, 95000, 180000, "per unit", 2, 30, 0),
    ("Herbal Extract Capsules (Private Label)", "health", 6, 8, 25, "per bottle", 500, 20, 1),
    ("Moringa Powder (Food Grade)", "health", 6, 480, 750, "per 25kg bag", 50, 14, 0),
    ("Nitrile Gloves (Medical Grade)", "health", 6, 380, 520, "per case", 100, 10, 0),
    ("Corrugated Boxes (Custom Print)", "packaging", 7, 18, 65, "per 10pcs", 500, 8, 1),
    ("Eco Mailers (Kraft, Biodegradable)", "packaging", 7, 12, 30, "per 25pcs", 1000, 7, 0),
    ("Flexible Packaging Film Rolls", "packaging", 7, 2400, 6800, "per roll", 20, 12, 0),
    ("Custom Label Printing (Rolls)", "packaging", 7, 850, 2400, "per 1k labels", 10, 9, 0),
    ("Gift Boxes (Rigid, Magnetic Close)", "packaging", 7, 45, 160, "per pc", 200, 11, 0),
]


def seed():
    with db() as con:
        if con.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]:
            return
        for name, slug, icon, blurb in CATEGORIES:
            con.execute("INSERT INTO categories(name,slug,icon,blurb) VALUES(?,?,?,?)",
                        (name, slug, icon, blurb))
        for i, (name, region, city, industry, rating, years, rr) in enumerate(SUPPLIERS):
            con.execute(
                "INSERT INTO suppliers(name,slug,region,city,industry,about,verified,rating,years,response_rate)"
                " VALUES(?,?,?,?,?,?,1,?,?,?)",
                (name, name.lower().replace(" ", "-").replace("&", "and") + f"-{i+1}", region, city,
                 industry,
                 f"{name} is a {industry.lower()} supplier based in {city}, {region}. "
                 f"Export-ready with {years}+ years serving domestic and international buyers.",
                 rating, years, rr))
        for j, (name, cat, sidx, pmin, pmax, unit, moq, lead, feat) in enumerate(PRODUCTS):
            sup = con.execute("SELECT id FROM suppliers WHERE slug=?",
                              (SUPPLIERS[sidx][0].lower().replace(" ", "-").replace("&", "and") + f"-{sidx+1}",)).fetchone()
            catrow = con.execute("SELECT id FROM categories WHERE slug=?", (cat,)).fetchone()
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") + f"-{j+1}"
            desc = (f"{name} supplied by {SUPPLIERS[sidx][0]} ({SUPPLIERS[sidx][1]}). "
                    f"Quality-inspected, export documentation available, OEM/ODM welcome. "
                    f"Lead time {lead} days from confirmed order. Samples available on request.")
            con.execute(
                "INSERT INTO products(supplier_id,category_id,name,slug,descr,price_min,price_max,"
                "unit,moq,lead_days,rating,orders,featured,image_url) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (sup["id"], catrow["id"], name, slug, desc, pmin, pmax, unit, moq, lead,
                 round(4.3 + (j % 7) * 0.1, 1), 40 + (j * 37) % 900, feat,
                 f"/static/img/cat-{cat}.svg"))


import re  # noqa: E402  (used by seed)

init_db()
seed()


def ensure_demo():
    with db() as con:
        has = con.execute("SELECT id FROM suppliers WHERE email=?", ("demo@islatrade.ph",)).fetchone()
        if not has:
            con.execute("UPDATE suppliers SET email=?, pw_hash=? WHERE id=(SELECT MIN(id) FROM suppliers)",
                        ("demo@islatrade.ph", hash_pw("islatrade")))


ensure_demo()


def ensure_site_admin():
    with db() as con:
        has = con.execute("SELECT id FROM suppliers WHERE email=?", ("admin@islatrade.ph",)).fetchone()
        if not has:
            con.execute(
                "INSERT INTO suppliers(name,slug,region,city,industry,about,verified,rating,years,"
                "response_rate,email,pw_hash,is_admin) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1)",
                ("IslaTrade Admin", "isla-admin", "Metro Manila", "Makati", "Platform",
                 "Platform operator account (hidden from directory).", 0, 5.0, 0, 100,
                 "admin@islatrade.ph", hash_pw("admin123")))


ensure_site_admin()


# ---------- helpers ----------
def q(sql, args=(), one=False):
    with db() as con:
        rows = con.execute(sql, args).fetchall()
        return (rows[0] if rows else None) if one else rows


def ago(ts):
    try:
        d = max(0, int(time.time() - float(ts)))
    except Exception:
        return ""
    if d < 60: return f"{d}s ago"
    if d < 3600: return f"{d // 60}m ago"
    if d < 86400: return f"{d // 3600}h ago"
    return f"{d // 86400}d ago"


tpl.env.filters["ago"] = ago


def resp(request, template, status_code=200, **ctx):
    try:
        ctx.setdefault("me", current_supplier(request))
    except Exception:
        ctx.setdefault("me", None)
    try:
        import fx
        ctx.setdefault("usdphp", fx.get_usdphp())
    except Exception:
        ctx.setdefault("usdphp", None)
    return tpl.TemplateResponse(request, template, ctx, status_code=status_code)


# ---------- pages ----------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    cats = q("SELECT * FROM categories ORDER BY id")
    featured = q("""SELECT p.*, s.name sname, s.region, c.slug cslug, c.icon cicon
                    FROM products p JOIN suppliers s ON s.id=p.supplier_id
                    JOIN categories c ON c.id=p.category_id WHERE p.featured=1 LIMIT 8""")
    top = q("""SELECT s.*, COUNT(p.id) np FROM suppliers s
               LEFT JOIN products p ON p.supplier_id=s.id
               WHERE COALESCE(s.is_admin,0)=0
               GROUP BY s.id ORDER BY s.rating DESC LIMIT 4""")
    stats = {"suppliers": q("SELECT COUNT(*) n FROM suppliers WHERE COALESCE(is_admin,0)=0", one=True)["n"],
             "products": q("SELECT COUNT(*) n FROM products", one=True)["n"],
             "regions": q("SELECT COUNT(DISTINCT region) n FROM suppliers", one=True)["n"]}
    return resp(request, "index.html", cats=cats, featured=featured, top=top, stats=stats)


@app.get("/products", response_class=HTMLResponse)
def products(request: Request, q_: str = "", cat: str = "", region: str = ""):
    sql = """SELECT p.*, s.name sname, s.slug sslug, s.region, c.name cname, c.icon cicon
             FROM products p JOIN suppliers s ON s.id=p.supplier_id
             JOIN categories c ON c.id=p.category_id WHERE 1=1"""
    args = []
    if q_:
        sql += " AND (p.name LIKE ? OR p.descr LIKE ? OR s.name LIKE ?)"
        args += [f"%{q_}%"] * 3
    if cat:
        sql += " AND c.slug=?"
        args.append(cat)
    if region:
        sql += " AND s.region=?"
        args.append(region)
    rows = q(sql + " ORDER BY p.featured DESC, p.orders DESC", args)
    cats = q("SELECT * FROM categories ORDER BY id")
    regions = q("SELECT DISTINCT region FROM suppliers ORDER BY region")
    return resp(request, "products.html", rows=rows, cats=cats, regions=regions,
                q=q_, cat=cat, region=region)


@app.get("/product/{slug}", response_class=HTMLResponse)
def product(request: Request, slug: str):
    p = q("""SELECT p.*, s.name sname, s.slug sslug, s.region, s.city, s.rating srating,
             s.years, s.response_rate, s.verified sverified, c.name cname, c.slug cslug, c.icon cicon
             FROM products p JOIN suppliers s ON s.id=p.supplier_id
             JOIN categories c ON c.id=p.category_id WHERE p.slug=?""", (slug,), one=True)
    if not p:
        return resp(request, "404.html", 404)
    related = q("""SELECT p.*, s.name sname FROM products p JOIN suppliers s ON s.id=p.supplier_id
                   WHERE p.category_id=? AND p.id!=? LIMIT 4""", (p["category_id"], p["id"]))
    reviews = q("""SELECT * FROM reviews WHERE product_id=? ORDER BY created DESC LIMIT 20""",
                (p["id"],))
    ravg = q("SELECT AVG(rating) a, COUNT(*) n FROM reviews WHERE product_id=?",
             (p["id"],), one=True)
    assured = bool(p["sverified"] and p["response_rate"] >= 88 and p["years"] >= 5)
    return resp(request, "product.html", p=p, related=related, reviews=reviews,
                ravg=ravg["a"], rcount=ravg["n"], assured=assured)


@app.post("/product/{slug}/review")
def add_review(request: Request, slug: str, author: str = Form(""),
               email: str = Form(""), rating: int = Form(5), text: str = Form("")):
    p = q("SELECT id FROM products WHERE slug=?", (slug,), one=True)
    if not p or not author or not text:
        return RedirectResponse(f"/product/{slug}", status_code=302)
    with db() as con:
        con.execute("INSERT INTO reviews(product_id,author,email,rating,text,created)"
                    " VALUES(?,?,?,?,?,?)",
                    (p["id"], author[:60], email[:80], max(1, min(5, rating)), text[:600],
                     time.time()))
    return RedirectResponse(f"/product/{slug}#reviews", status_code=302)


@app.get("/suppliers", response_class=HTMLResponse)
def suppliers(request: Request):
    rows = q("""SELECT s.*, COUNT(p.id) np FROM suppliers s
                 LEFT JOIN products p ON p.supplier_id=s.id
                 WHERE COALESCE(s.is_admin,0)=0
                 GROUP BY s.id ORDER BY s.verified DESC, s.rating DESC""")
    return resp(request, "suppliers.html", rows=rows)


@app.get("/supplier/{slug}", response_class=HTMLResponse)
def supplier(request: Request, slug: str):
    s = q("SELECT * FROM suppliers WHERE slug=?", (slug,), one=True)
    if not s or s["is_admin"]:
        return resp(request, "404.html", 404)
    prods = q("SELECT * FROM products WHERE supplier_id=? ORDER BY featured DESC", (s["id"],))
    return resp(request, "supplier.html", s=s, prods=prods)


@app.get("/rfq", response_class=HTMLResponse)
def rfq_form(request: Request, product: int = 0):
    p = q("""SELECT p.name, p.slug, s.name sname FROM products p
             JOIN suppliers s ON s.id=p.supplier_id WHERE p.id=?""", (product,), one=True) if product else None
    cats = q("SELECT * FROM categories ORDER BY id")
    return resp(request, "rfq.html", p=p, cats=cats)


@app.post("/rfq")
def rfq_post(request: Request, name: str = Form(""), email: str = Form(""),
             phone: str = Form(""), company: str = Form(""), qty: str = Form(""),
             message: str = Form(""), product: int = Form(0), category: int = Form(0)):
    if not rate_ok(request.client.host if request.client else "anon"):
        return HTMLResponse("Slow down — try again in a minute.", status_code=429)
    if not name or not email:
        return RedirectResponse("/rfq?err=1", status_code=302)
    pname = None
    if product:
        prow = q("SELECT name, supplier_id FROM products WHERE id=?", (product,), one=True)
        if prow:
            pname = prow["name"]
    targets = set()
    if product and prow:
        targets.add(prow["supplier_id"])
    if category:
        for r in q("SELECT DISTINCT supplier_id FROM products WHERE category_id=?", (category,)):
            targets.add(r["supplier_id"])
    label = "New RFQ from " + name + (f" ({company})" if company else "") + \
            (f" re: {pname}" if pname else "")
    rid = None
    with db() as con:
        cur = con.execute("INSERT INTO rfqs(product_id,category_id,name,email,phone,company,qty,message,created)"
                          " VALUES(?,?,?,?,?,?,?,?,?)",
                          (product or None, category or None, name, email, phone, company, qty, message, time.time()))
        rid = cur.lastrowid
        for t in sorted(x for x in targets if x):
            con.execute("INSERT INTO notifications(supplier_id,rfq_id,text,created) VALUES(?,?,?,?)",
                        (t, rid, label, time.time()))
    return RedirectResponse("/rfq/sent", status_code=302)


@app.get("/rfq/sent", response_class=HTMLResponse)
def rfq_sent(request: Request):
    return resp(request, "rfq_sent.html")


# ---------- JSON API ----------
# ---------- auth ----------
@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return resp(request, "login.html")


@app.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return resp(request, "register.html")


@app.post("/register")
def register(request: Request, company: str = Form(""), email: str = Form(""),
             pw: str = Form(""), region: str = Form("Metro Manila"), city: str = Form("")):
    if not rate_ok(request.client.host if request.client else "anon"):
        return HTMLResponse("Slow down — try again in a minute.", status_code=429)
    if not company or not email or len(pw) < 6:
        return resp(request, "register.html", 400, err="Company, email and a password of 6+ chars are required")
    email = email.lower().strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return resp(request, "register.html", 400, err="Enter a valid email address (e.g. you@company.com)")
    if q("SELECT id FROM suppliers WHERE email=?", (email,), one=True):
        return resp(request, "register.html", 400, err="That email is already registered")
    slug = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-") + f"-{secrets.token_hex(3)}"
    with db() as con:
        cur = con.execute(
            "INSERT INTO suppliers(name,slug,region,city,industry,about,verified,rating,years,response_rate,email,pw_hash)"
            " VALUES(?,?,?,?,?,?,0,4.5,0,80,?,?)",
            (company, slug, region or "Metro Manila", city or "", "", f"{company} — new IslaTrade supplier.", email, hash_pw(pw)))
        sid = cur.lastrowid
        tok = secrets.token_hex(16)
        con.execute("INSERT INTO sessions(token,supplier_id,created) VALUES(?,?,?)", (tok, sid, _t.time()))
    r = RedirectResponse("/supplier-admin", status_code=302)
    r.set_cookie("it_sess", tok, httponly=True, samesite="lax", secure=bool(os.environ.get("RENDER")))
    return r


@app.post("/login")
def login(request: Request, email: str = Form(""), pw: str = Form("")):
    if not rate_ok(request.client.host if request.client else "anon"):
        return HTMLResponse("Slow down — try again in a minute.", status_code=429)
    s, tok = login_supplier(email, pw)
    if not s:
        return resp(request, "login.html", 401, err="Invalid email or password")
    r = RedirectResponse("/supplier-admin", status_code=302)
    r.set_cookie("it_sess", tok, httponly=True, samesite="lax", secure=bool(os.environ.get("RENDER")))
    return r


@app.get("/logout")
def logout(request: Request):
    tok = request.cookies.get("it_sess")
    if tok:
        with db() as con:
            con.execute("DELETE FROM sessions WHERE token=?", (tok,))
    r = RedirectResponse("/", status_code=302)
    r.delete_cookie("it_sess")
    return r


@app.get("/supplier-admin", response_class=HTMLResponse)
def supplier_admin(request: Request):
    me = current_supplier(request)
    if not me:
        return RedirectResponse("/login", status_code=302)
    cats = q("SELECT * FROM categories ORDER BY id")
    my_products = q("SELECT * FROM products WHERE supplier_id=? ORDER BY id DESC", (me["id"],))
    inbox = q("""SELECT r.*, p.name pname FROM rfqs r
                 LEFT JOIN products p ON p.id=r.product_id
                 WHERE p.supplier_id=? OR (r.category_id IN
                   (SELECT category_id FROM products WHERE supplier_id=?))
                 ORDER BY r.created DESC LIMIT 50""", (me["id"], me["id"]))
    ids = [r["id"] for r in inbox]
    msgs = []
    if ids:
        marks = ",".join("?" * len(ids))
        msgs = q(f"SELECT * FROM messages WHERE rfq_id IN ({marks}) ORDER BY created", tuple(ids))
        quotes = q(f"SELECT * FROM quotes WHERE rfq_id IN ({marks}) ORDER BY created", tuple(ids))
    else:
        quotes = []
    notifs = q("SELECT * FROM notifications WHERE supplier_id=? ORDER BY id DESC LIMIT 30", (me["id"],))
    unread = q("SELECT COUNT(*) n FROM notifications WHERE supplier_id=? AND read=0",
               (me["id"],), one=True)["n"]
    return resp(request, "admin.html", me=me, prods=my_products, inbox=inbox, msgs=msgs,
                notifs=notifs, unread=unread, cats=cats, quotes=quotes)


@app.post("/supplier-admin/notifications/read")
def notifications_read(request: Request):
    me = current_supplier(request)
    if not me:
        return RedirectResponse("/login", status_code=302)
    with db() as con:
        con.execute("UPDATE notifications SET read=1 WHERE supplier_id=?", (me["id"],))
    return RedirectResponse("/supplier-admin", status_code=302)


@app.post("/supplier-admin/products/new")
def new_product(request: Request, name: str = Form(""), category_id: int = Form(0),
                price_min: float = Form(0), price_max: float = Form(0), unit: str = Form("per pc"),
                moq: int = Form(1), lead_days: int = Form(14), descr: str = Form(""),
                image_url: str = Form("")):
    me = current_supplier(request)
    if not me or not name:
        return RedirectResponse("/login", status_code=302)
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") + f"-{secrets.token_hex(3)}"
    img = image_url.strip()
    if not img:
        catrow = q("SELECT slug FROM categories WHERE id=?", (category_id,), one=True) if category_id else None
        img = f"/static/img/cat-{catrow['slug']}.svg" if catrow else "/static/img/placeholder.svg"
    with db() as con:
        con.execute("""INSERT INTO products(supplier_id,category_id,name,slug,descr,price_min,
                       price_max,unit,moq,lead_days,image_url) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (me["id"], category_id or None, name, slug, descr or f"{name} by {me['name']}.",
                     price_min, price_max, unit, moq, lead_days, img))
    return RedirectResponse("/supplier-admin", status_code=302)


@app.post("/supplier-admin/products/{pid}/edit")
def edit_product(request: Request, pid: int, name: str = Form(""),
                 price_min: float = Form(0), price_max: float = Form(0),
                 unit: str = Form("per pc"), moq: int = Form(1),
                 lead_days: int = Form(14), descr: str = Form(""),
                 image_url: str = Form("")):
    me = current_supplier(request)
    if not me or not name:
        return RedirectResponse("/login", status_code=302)
    with db() as con:
        con.execute("""UPDATE products SET name=?, descr=?, price_min=?, price_max=?,
                       unit=?, moq=?, lead_days=?, image_url=CASE
                       WHEN ?!='' THEN ? ELSE image_url END WHERE id=? AND supplier_id=?""",
                    (name, descr, price_min, price_max, unit, moq, lead_days,
                     image_url.strip(), image_url.strip(), pid, me["id"]))
    return RedirectResponse("/supplier-admin", status_code=302)


@app.post("/supplier-admin/products/{pid}/delete")
def delete_product(request: Request, pid: int):
    me = current_supplier(request)
    if not me:
        return RedirectResponse("/login", status_code=302)
    with db() as con:
        con.execute("DELETE FROM products WHERE id=? AND supplier_id=?", (pid, me["id"]))
    return RedirectResponse("/supplier-admin", status_code=302)


@app.post("/supplier-admin/rfq/{rfq_id}/quote")
def post_quote(request: Request, rfq_id: int, price: float = Form(0),
               lead_days: int = Form(14), message: str = Form("")):
    me = current_supplier(request)
    if not me:
        return RedirectResponse("/login", status_code=302)
    with db() as con:
        con.execute("""INSERT INTO quotes(rfq_id,supplier_id,price,lead_days,message,created)
                       VALUES(?,?,?,?,?,?)""",
                    (rfq_id, me["id"], price, lead_days, message, _t.time()))
    return RedirectResponse("/supplier-admin", status_code=302)


@app.get("/rfq/tracking", response_class=HTMLResponse)
def rfq_tracking(request: Request, email: str = ""):
    rfqs, quotes, msgs = [], [], []
    if email:
        em = email.lower().strip()
        rfqs = q("SELECT * FROM rfqs WHERE LOWER(email)=? ORDER BY created DESC", (em,))
        ids = [r["id"] for r in rfqs]
        if ids:
            marks = ",".join("?" * len(ids))
            quotes = q(f"SELECT q.*, s.name sname FROM quotes q "
                       f"JOIN suppliers s ON s.id=q.supplier_id WHERE q.rfq_id IN ({marks})",
                       tuple(ids))
            # thread = buyer's own messages PLUS supplier replies on the buyer's RFQs
            # (supplier rows carry supplier_id, not email -> must match by rfq_id)
            msgs = q(f"SELECT * FROM messages WHERE LOWER(email)=? OR rfq_id IN ({marks}) "
                     f"ORDER BY created", (em, *ids))
    return resp(request, "rfq_track.html", email=email, rfqs=rfqs, quotes=quotes, msgs=msgs)


@app.post("/rfq/tracking/message")
def buyer_message(request: Request, rfq_id: int = Form(0), email: str = Form(""), text: str = Form("")):
    if not (rfq_id and email and text):
        return RedirectResponse(f"/rfq/tracking?email={email}", status_code=302)
    with db() as con:
        con.execute("INSERT INTO messages(rfq_id,sender,email,text,created) VALUES(?,?,?,?,?)",
                    (rfq_id, "buyer", email.lower(), text, _t.time()))
    return RedirectResponse(f"/rfq/tracking?email={email}", status_code=302)


@app.post("/supplier-admin/rfq/{rfq_id}/message")
def supplier_message(request: Request, rfq_id: int, text: str = Form("")):
    me = current_supplier(request)
    if not me or not text:
        return RedirectResponse("/supplier-admin", status_code=302)
    with db() as con:
        con.execute("INSERT INTO messages(rfq_id,sender,supplier_id,text,created) VALUES(?,?,?,?,?)",
                    (rfq_id, "supplier", me["id"], text, _t.time()))
    return RedirectResponse("/supplier-admin", status_code=302)


@app.get("/admin-panel", response_class=HTMLResponse)
def admin_panel(request: Request):
    me = current_supplier(request)
    if not me or not me["is_admin"]:
        return RedirectResponse("/login", status_code=302)
    stats = {
        "suppliers": q("SELECT COUNT(*) n FROM suppliers WHERE COALESCE(is_admin,0)=0", one=True)["n"],
        "products": q("SELECT COUNT(*) n FROM products", one=True)["n"],
        "rfqs": q("SELECT COUNT(*) n FROM rfqs", one=True)["n"],
        "quotes": q("SELECT COUNT(*) n FROM quotes", one=True)["n"],
        "msgs": q("SELECT COUNT(*) n FROM messages", one=True)["n"],
        "reviews": q("SELECT COUNT(*) n FROM reviews", one=True)["n"],
    }
    all_rfqs = q("""SELECT r.*, p.name pname, s.name sname, 
                    (SELECT COUNT(*) FROM quotes qq WHERE qq.rfq_id=r.id) nq
                    FROM rfqs r LEFT JOIN products p ON p.id=r.product_id
                    LEFT JOIN suppliers s ON s.id=p.supplier_id
                    ORDER BY r.created DESC LIMIT 100""")
    all_suppliers = q("""SELECT s.*, COUNT(p.id) np FROM suppliers s
                         LEFT JOIN products p ON p.supplier_id=s.id
                         WHERE COALESCE(s.is_admin,0)=0
                         GROUP BY s.id ORDER BY s.rating DESC""")
    return resp(request, "admin_panel.html", me=me, stats=stats,
                all_rfqs=all_rfqs, all_suppliers=all_suppliers)


@app.get("/api/products")
def api_products(q_: str = "", cat: str = "", limit: int = 50):
    sql = """SELECT p.id,p.name,p.slug,p.price_min,p.price_max,p.unit,p.moq,c.slug cat,
             s.name supplier FROM products p JOIN suppliers s ON s.id=p.supplier_id
             JOIN categories c ON c.id=p.category_id WHERE 1=1"""
    args: list = []
    if q_:
        sql += " AND p.name LIKE ?"
        args.append(f"%{q_}%")
    if cat:
        sql += " AND c.slug=?"
        args.append(cat)
    sql += " LIMIT ?"
    args.append(limit)
    return [dict(r) for r in q(sql, args)]


@app.get("/api/rfqs")
def api_rfqs(request: Request):
    me = current_supplier(request)
    if not me or not me["is_admin"]:
        return JSONResponse({"error": "admin session required"}, status_code=401)
    return [dict(r) for r in q("SELECT * FROM rfqs ORDER BY created DESC LIMIT 100")]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8500")),
                proxy_headers=True, forwarded_allow_ips=os.environ.get("IT_TRUST_PROXY", "*"))


# ---------- light rate limit (POST endpoints) ----------
_RL: dict = {}
RL_LIMIT = int(os.environ.get("ISLATRADE_RL_LIMIT", "10"))
RL_WINDOW = 60


def rate_ok(ip: str) -> bool:
    now = time.time()
    hits = [t for t in _RL.get(ip, []) if now - t < RL_WINDOW]
    if len(hits) >= RL_LIMIT:
        _RL[ip] = hits
        return False
    hits.append(now)
    _RL[ip] = hits
    return True


@app.get("/robots.txt")
def robots():
    return HTMLResponse(
        "User-agent: *\n"
        "Disallow: /supplier-admin\n"
        "Disallow: /login\n"
        "Disallow: /register\n"
        "Disallow: /logout\n"
        "Sitemap: https://islatrade.ph/sitemap.xml"
    )


@app.get("/sitemap.xml")
def sitemap():
    base = "https://islatrade.ph"
    urls = ["", "/products", "/suppliers", "/rfq"]
    for c in q("SELECT slug FROM categories"):
        urls.append(f"/products?cat={c['slug']}")
    for p in q("SELECT slug FROM products"):
        urls.append(f"/product/{p['slug']}")
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + \
        "".join(f"<url><loc>{base}{u}</loc></url>" for u in urls) + "</urlset>"
    return HTMLResponse(body, media_type="application/xml")


@app.get("/health")
def health():
    return {"ok": True, "ts": time.time()}

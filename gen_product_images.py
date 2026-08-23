"""Generate deterministic SVG product photos (3 gallery shots per product)
into static/img/p/ and set products.image_url. Idempotent — safe to rerun."""
import hashlib
import os
import sqlite3
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(ROOT, "islatrade.db")
OUT = os.path.join(ROOT, "static", "img", "p")
os.makedirs(OUT, exist_ok=True)

PALETTE = {
    "electronics": ("#1f3a93", "#4a69bd"),
    "furniture": ("#7a5230", "#a47148"),
    "food": ("#0e6655", "#16a085"),
    "health": ("#148f77", "#45b39d"),
    "textiles": ("#6c3483", "#9b59b6"),
    "construction": ("#566573", "#85929e"),
    "machinery": ("#1b2631", "#2e4053"),
    "packaging": ("#b9770e", "#f39c12"),
}


def label(name, limit=36):
    name = name.strip()
    return escape(name if len(name) <= limit else name[:limit - 1].rstrip() + "…")


def circles(slug):
    h = hashlib.md5(slug.encode()).digest()
    return [(80 + h[0] * 2.4, 90 + h[1] * 1.6, 120 + h[2]),
            (620 + h[3] * 0.8, 420 + h[4] * 1.2, 150 + h[5]),
            (360 + h[6], 560 + h[7] * 0.3, 100 + h[8])]


def shot_main(name, icon, c1, c2, slug):
    cs = "".join(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r}" fill="#fff" opacity="0.10"/>'
                 for cx, cy, r in circles(slug))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient></defs>
<rect width="800" height="600" fill="url(#g)"/>{cs}
<text x="400" y="320" font-size="180" text-anchor="middle">{icon}</text>
<text x="400" y="450" font-size="34" fill="#ffffff" fill-opacity="0.95" text-anchor="middle"
 font-family="'Segoe UI',Arial,sans-serif" font-weight="600">{label(name)}</text>
</svg>"""


def shot_detail(name, icon, c1, c2, slug):
    cs = "".join(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r}" fill="{c2}" opacity="0.14"/>'
                 for cx, cy, r in circles(slug + "-d"))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">
<rect width="800" height="600" fill="#f6f8fb"/>{cs}
<g stroke="#d7e0ea" stroke-width="1">{"".join(f'<line x1="{x}" y1="0" x2="{x}" y2="600"/>' for x in range(100, 800, 140))}</g>
<g transform="rotate(-8 400 280)"><text x="400" y="330" font-size="240" text-anchor="middle">{icon}</text></g>
<rect x="60" y="480" width="430" height="56" rx="10" fill="#ffffff" opacity="0.92"/>
<text x="84" y="516" font-size="26" fill="#33415c" text-anchor="start"
 font-family="'Segoe UI',Arial,sans-serif" font-weight="600">{label(name)}</text>
</svg>"""


def shot_dark(name, icon, c1, c2, slug):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">
<rect width="800" height="600" fill="#0f172a"/>
<circle cx="400" cy="270" r="185" fill="none" stroke="{c2}" stroke-width="5" opacity="0.85"/>
<circle cx="400" cy="270" r="205" fill="{c1}" opacity="0.35"/>
<text x="400" y="330" font-size="170" text-anchor="middle">{icon}</text>
<text x="400" y="520" font-size="28" fill="#cbd5e1" text-anchor="middle"
 font-family="'Segoe UI',Arial,sans-serif" font-weight="600">{label(name)}</text>
<text x="40" y="52" font-size="22" fill="#ffffff" fill-opacity="0.55" font-family="'Segoe UI',Arial,sans-serif">IslaTrade</text>
</svg>"""


con = sqlite3.connect(DB)
rows = con.execute(
    "SELECT p.slug, p.name, COALESCE(c.icon,'📦'), COALESCE(c.slug,'packaging') "
    "FROM products p LEFT JOIN categories c ON c.id=p.category_id").fetchall()
for slug, name, icon, cslug in rows:
    c1, c2 = PALETTE.get(cslug, PALETTE["packaging"])
    for suffix, fn in (("", shot_main), ("-2", shot_detail), ("-3", shot_dark)):
        with open(os.path.join(OUT, f"{slug}{suffix}.svg"), "w", encoding="utf-8") as f:
            f.write(fn(name, icon, c1, c2, slug))
    con.execute("UPDATE products SET image_url=? WHERE slug=?", (f"/static/img/p/{slug}.svg", slug))
con.commit()
con.close()
print(f"PRODUCT IMAGES: {len(rows)} products x 3 shots -> {OUT}")

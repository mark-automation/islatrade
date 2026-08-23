"""Mirror IslaTrade server pages -> static site for GitHub Pages."""
import os
import re
import shutil
import subprocess
import urllib.request

BASE = "http://127.0.0.1:8500"
OUT = r"C:\Users\jorda\islatrade\site"
os.makedirs(OUT, exist_ok=True)


def fetch(path):
    with urllib.request.urlopen(BASE + path, timeout=15) as r:
        return r.read().decode("utf-8")


def save(rel, html):
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(html)


def rel_prefix(depth):
    return "./" if depth == 0 else "../" * depth


def rewrite(html, depth):
    pre = rel_prefix(depth)
    html = re.sub(r'(href|src|action)="(/(?!/))', lambda m: m.group(1) + '="' + pre, html)
    # strip query strings from internal links (static pages are prebuilt)
    html = re.sub(r'href="(\./|\.\./)*products\?[^"]*"', 'href="' + pre + 'products/index.html"', html)
    html = html.replace('action="/rfq/tracking/message"', 'action="#"')
    return html


def put(rel, path, extra=""):
    depth = rel.count("/")
    save(rel, rewrite(fetch(path), depth) + extra)


# --- core pages ---
put("index.html", "/")
put("products/index.html", "/products")
put("suppliers/index.html", "/suppliers")
put("rfq/index.html", "/rfq")

# categories
import sqlite3
con = sqlite3.connect(r"C:\Users\jorda\islatrade\islatrade.db")
con.row_factory = sqlite3.Row
cats = con.execute("SELECT slug FROM categories").fetchall()
for c in cats:
    put(f"products/cat-{c['slug']}/index.html", f"/products?cat={c['slug']}")

# products
prods = con.execute("SELECT slug FROM products").fetchall()
for p in prods:
    put(f"product/{p['slug']}/index.html", f"/product/{p['slug']}")

# suppliers (skip platform admin account)
sups = con.execute("SELECT slug FROM suppliers WHERE COALESCE(is_admin,0)=0").fetchall()
for s in sups:
    put(f"supplier/{s['slug']}/index.html", f"/supplier/{s['slug']}")

# assets
shutil.copytree(r"C:\Users\jorda\islatrade\static", os.path.join(OUT, "static"), dirs_exist_ok=True)

# .nojekyll
open(os.path.join(OUT, ".nojekyll"), "w").close()

# client-side search injection into products page
ppath = os.path.join(OUT, "products", "index.html")
html = open(ppath, encoding="utf-8").read()
search_js = """
<script>
document.addEventListener('DOMContentLoaded',function(){
 var inp=document.querySelector('.filters input[name=q_]');
 if(!inp)return;
 var cards=document.querySelectorAll('.grid.g3 > a.card');
 inp.removeAttribute('name');
 inp.addEventListener('input',function(){
  var v=inp.value.toLowerCase();
  cards.forEach(function(c){c.style.display=c.textContent.toLowerCase().includes(v)?'':'none';});
 });
});
</script>
"""
open(ppath, "w", encoding="utf-8").write(html + search_js)

n = sum(len(fs) for _, _, fs in os.walk(OUT))
print("STATIC SITE BUILT:", n, "files at", OUT)

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


DEMO_NOTE = """
<script>
document.querySelectorAll('form[method=post]').forEach(function(f){
 f.addEventListener('submit',function(e){
  e.preventDefault();
  var t=document.getElementById('mirror-note');
  if(!t){t=document.createElement('div');t.id='mirror-note';
   t.style.cssText='position:fixed;left:50%;bottom:18px;transform:translateX(-50%);background:#0f172a;color:#fff;padding:10px 16px;border-radius:8px;font:14px system-ui;z-index:9999;box-shadow:0 6px 18px rgba(0,0,0,.35)';
   document.body.appendChild(t);}
  t.textContent='Preview mirror \\u2014 sign-ups, RFQs and reviews run on the live IslaTrade app.';
  clearTimeout(t._h);t._h=setTimeout(function(){t.remove()},3500);
 });
});
</script>
"""


def rewrite(html, depth):
    pre = rel_prefix(depth)
    html = re.sub(r'(href|src|action)="(/(?!/))', lambda m: m.group(1) + '="' + pre, html)
    # category filter links -> prebuilt category pages (before generic query strip)
    html = re.sub(r'href="(?:\./|\.\./)*products\?cat=([a-z0-9_-]+)[^"]*"',
                  lambda m: 'href="' + pre + 'products/cat-' + m.group(1) + '/index.html"', html)
    # strip remaining query strings from internal links (static pages are prebuilt)
    html = re.sub(r'href="(?:\./|\.\./)*(products|rfq)\?[^"]*"',
                  lambda m: 'href="' + pre + m.group(1) + '/index.html"', html)
    html = html.replace('action="/rfq/tracking/message"', 'action="#"')
    # static mirror has no backend: neutralize every POST form so submits
    # never navigate into a 405/404, and tell the visitor why
    n_post = len(re.findall(r'method="post"', html))
    if n_post:
        html = re.sub(r'method="post"\s+action="[^"]*"', 'method="post" action="#" onsubmit="return false"', html)
        html = html.replace("</body>", DEMO_NOTE + "</body>")
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

# auth + post-rfq confirmation pages (nav links to these on every page)
put("login/index.html", "/login")
put("register/index.html", "/register")
put("rfq/sent/index.html", "/rfq/sent")
put("rfq/tracking/index.html", "/rfq/tracking")

# robots.txt + sitemap.xml with Pages-appropriate absolute URLs
PAGES_BASE = "https://mark-automation.github.io/islatrade"
save("robots.txt",
     "User-agent: *\n"
     "Disallow: /islatrade/supplier-admin\n"
     "Disallow: /islatrade/logout\n"
     f"Sitemap: {PAGES_BASE}/sitemap.xml\n")
urls = ["", "/products/", "/suppliers/", "/rfq/", "/login/", "/register/",
        "/rfq/sent/"]
for c in cats:
    urls.append(f"/products/cat-{c['slug']}/")
for p in prods:
    urls.append(f"/product/{p['slug']}/")
for s in sups:
    urls.append(f"/supplier/{s['slug']}/")
sitemap_body = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                + "".join(f"<url><loc>{PAGES_BASE}{u}</loc></url>" for u in urls)
                + "</urlset>")
save("sitemap.xml", sitemap_body)

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

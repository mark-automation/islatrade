"""Mirror IslaTrade server pages -> static site for GitHub Pages."""
import os
import re
import shutil
import sqlite3
import time
import http.cookiejar
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8500"
OUT = r"C:\Users\jorda\islatrade\site"
PAGES_BASE = "https://mark-automation.github.io/islatrade"
PAGES_ROOT = "/islatrade"  # site base path on GitHub Pages (project site)
os.makedirs(OUT, exist_ok=True)


def fetch(path):
    with urllib.request.urlopen(BASE + path, timeout=15) as r:
        return r.read().decode("utf-8")


def save(rel, text):
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


def rel_prefix(depth):
    # ABSOLUTE site-base prefix ("/islatrade/"). GitHub Pages serves
    # extensionless URLs WITHOUT a trailing slash (/islatrade/products), so
    # ../-style relative links resolve against the HOST ROOT and 404 en masse.
    # Base-prefixed absolute paths are correct regardless of URL shape.
    return PAGES_ROOT + "/"


DEMO_NOTE = """
<script>
document.querySelectorAll('form[method=post]').forEach(function(f){
 f.addEventListener('submit',function(e){
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

AUTH_SHIM = """
<script>
(function(){
 var R=null;try{R=localStorage.getItem('it_role')}catch(e){}
 function pre(){var a=document.querySelector('header nav a');if(!a)return './';
  var h=a.getAttribute('href');return h.slice(0,h.lastIndexOf('/')+1)||'./'}
 var nav=document.querySelector('header nav');
 if(R&&nav){
  nav.querySelectorAll('a[href*="register"],a[href*="login"]').forEach(function(a){a.remove()});
  var p=pre(),d=document.createElement('a'),lo=document.createElement('a');
  d.href=p+(R==='admin'?'admin-panel/':'supplier-admin/');
  d.innerHTML='<b>'+(R==='admin'?'Admin panel':'Dashboard')+'</b>';
  lo.href='#it-logout';lo.textContent='Logout';nav.appendChild(d);nav.appendChild(lo);}
 document.addEventListener('click',function(e){
  if(e.target.closest('a[href="#it-logout"]')){e.preventDefault();
   try{localStorage.removeItem('it_role')}catch(x){}
   location.href=pre();}
 });
 var em=document.querySelector('input[name=email]');
 if(em&&document.querySelector('input[name=pw]')&&em.closest('form')){
  em.closest('form').addEventListener('submit',function(ev){
   ev.preventDefault();
   var v=(em.value||'').trim().toLowerCase(),
       pw=em.closest('form').querySelector('input[name=pw]').value||'',go=null;
   if(v==='demo@islatrade.ph'&&pw==='islatrade'){go='supplier-admin/';R='supplier'}
   else if(v==='admin@islatrade.ph'&&pw==='admin123'){go='admin-panel/';R='admin'}
   if(go){try{localStorage.setItem('it_role',R)}catch(x){};location.href=pre()+go;return}
   var f=em.closest('form'),t=f.querySelector('.it-err');
   if(!t){t=document.createElement('p');t.className='it-err';
    t.style.cssText='color:#c0392b;font-size:13px;margin-top:10px';f.appendChild(t)}
   t.textContent='Preview mirror \\u2014 use the demo account shown below.';
  });}
 var rf=document.querySelector('input[name=company]');
 if(rf&&rf.closest('form')){rf.closest('form').addEventListener('submit',function(ev){
  ev.preventDefault();try{localStorage.setItem('it_role','supplier')}catch(x){}
  location.href=pre()+'supplier-admin/';});}
})();
</script>
"""


def rewrite(html, depth):
    pre = rel_prefix(depth)
    html = re.sub(r'(href|src|action)="(/(?!/))', lambda m: m.group(1) + '="' + pre, html)
    # category filter links -> prebuilt category pages (before generic query strip)
    html = re.sub(r'href="(?:\./|\.\./)*products\?cat=([a-z0-9_-]+)[^"]*"',
                  lambda m: 'href="' + pre + 'products/cat-' + m.group(1) + '/"', html)
    # strip remaining query strings from internal links (static pages are prebuilt)
    html = re.sub(r'href="(?:\./|\.\./)*(products|rfq)\?[^"]*"',
                  lambda m: 'href="' + pre + m.group(1) + '/"', html)
    html = html.replace('action="/rfq/tracking/message"', 'action="#"')
    # static mirror has no backend: neutralize every POST form so submits
    # never navigate into a 405/404, and tell the visitor why
    n_post = len(re.findall(r'method="post"\s+action="[^"]*"', html))
    if n_post:
        html = re.sub(r'method="post"\s+action="[^"]*"', 'method="post" action="#"', html)
        html = html.replace("</body>", DEMO_NOTE + "</body>")
    # /logout needs a server session to kill — hand it to the client-side shim
    html = re.sub(r'href="[^"]*logout[^"]*"', 'href="#it-logout"', html)
    return html.replace("</body>", AUTH_SHIM + "</body>")


def put(rel, path):
    save(rel, rewrite(fetch(path), rel.count("/")))


def snapshot(rel, path, email, pw):
    """Fetch an authenticated page via a real login session."""
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    data = urllib.parse.urlencode({"email": email, "pw": pw}).encode()
    op.open(BASE + "/login", data=data, timeout=15).read()
    save(rel, rewrite(op.open(BASE + path, timeout=15).read().decode("utf-8"), rel.count("/")))


# --- core pages ---
put("index.html", "/")
put("products/index.html", "/products")
put("suppliers/index.html", "/suppliers")
put("rfq/index.html", "/rfq")

# categories
con = sqlite3.connect(r"C:\Users\jorda\islatrade\islatrade.db")
con.row_factory = sqlite3.Row
cats = con.execute("SELECT slug FROM categories").fetchall()
for c in cats:
    put(f"products/cat-{c['slug']}/index.html", f"/products?cat={c['slug']}")

# products (exclude admin/dogfood QA suppliers so test data never hits the public mirror)
excl_ids = [r["id"] for r in con.execute(
    "SELECT id FROM suppliers WHERE COALESCE(is_admin,0)=1 OR slug LIKE 'dogfood%'")] or [-1]
ph = ",".join("?" * len(excl_ids))
prods = con.execute(
    f"SELECT slug FROM products WHERE COALESCE(supplier_id,-1) NOT IN ({ph})",
    excl_ids).fetchall()
for p in prods:
    put(f"product/{p['slug']}/index.html", f"/product/{p['slug']}")

# suppliers (skip platform admin account + dogfood QA records)
sups = con.execute(
    "SELECT slug FROM suppliers "
    "WHERE COALESCE(is_admin,0)=0 AND slug NOT LIKE 'dogfood%'").fetchall()
for s in sups:
    put(f"supplier/{s['slug']}/index.html", f"/supplier/{s['slug']}")

# auth + post-rfq confirmation pages (nav links to these on every page)
put("login/index.html", "/login")
put("register/index.html", "/register")
put("rfq/sent/index.html", "/rfq/sent")
put("rfq/tracking/index.html", "/rfq/tracking")

# logged-in dashboard snapshots (demo credentials are public on the login page;
# forms inside are neutralized to '#' with the preview note)
snapshot("supplier-admin/index.html", "/supplier-admin", "demo@islatrade.ph", "islatrade")
time.sleep(1.5)  # stay under the auth rate limit
snapshot("admin-panel/index.html", "/admin-panel", "admin@islatrade.ph", "admin123")

# robots.txt + sitemap.xml with Pages-appropriate absolute URLs
save("robots.txt",
     "User-agent: *\n"
     "Disallow: /islatrade/supplier-admin\n"
     "Disallow: /islatrade/admin-panel\n"
     "Disallow: /islatrade/login\n"
     "Disallow: /islatrade/register\n"
     "Disallow: /islatrade/logout\n"
     f"Sitemap: {PAGES_BASE}/sitemap.xml\n")
urls = ["/", "/products/", "/suppliers/", "/rfq/"]
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

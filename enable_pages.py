"""Make islatrade repo public, then enable Pages."""
import re
import urllib.request
import json

creds = open(r"C:\Users\jorda\.git-credentials", encoding="utf-8").read()
token = re.search(r"majkeroro:([^@]+)@github\.com", creds).group(1)
H = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}

req = urllib.request.Request(
    "https://api.github.com/repos/mark-automation/islatrade",
    data=b'{"private":false}',
    headers={**H, "Content-Type": "application/json"}, method="PATCH")
with urllib.request.urlopen(req, timeout=30) as r:
    d = json.loads(r.read())
    print("visibility:", "private" if d.get("private") else "public")

req2 = urllib.request.Request(
    "https://api.github.com/repos/mark-automation/islatrade/pages",
    data=json.dumps({"source": {"branch": "main", "path": "/"}}).encode(),
    headers={**H, "Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(req2, timeout=30) as r2:
        print("pages enabled:", r2.status)
except urllib.error.HTTPError as e:
    print("enable:", e.code, e.read().decode()[:200])

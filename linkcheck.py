import re, subprocess, sys
from collections import deque
from urllib.parse import urljoin

BASE = "https://mark-automation.github.io/islatrade/"

def fetch(url):
    try:
        p = subprocess.run(
            ["curl", "-4", "-s", "--max-time", "12", "-L", "-w", "\n@@%{http_code}@@%{url_effective}@@", url],
            capture_output=True, text=True, timeout=15)
        out = p.stdout
        m = re.search(r"\n@@(\d+)@@([^@]+)@@$", out)
        if not m:
            return ("ERR", url, "")
        return (int(m.group(1)), url, m.group(2))
    except Exception as e:
        return ("ERR", url, str(e))

seen, bad, ok = set(), [], []
q = deque([BASE])
while q:
    url = q.popleft()
    if url in seen:
        continue
    seen.add(url)
    code, req, final = fetch(url)
    if code != 200:
        bad.append((code, req, final))
        continue
    body = subprocess.run(["curl", "-4", "-s", "--max-time", "12", "-L", url],
                          capture_output=True, text=True, timeout=15).stdout
    ok.append((code, req, final))
    for m in re.findall(r'(?:href|src)="([^"#]+)"', body):
        if m.startswith(("mailto:", "tel:", "data:", "javascript:")):
            continue
        if m.startswith("http") and "mark-automation.github.io/islatrade" not in m:
            continue
        nxt = ("https://mark-automation.github.io" + m) if m.startswith("/") else urljoin(url, m)
        if nxt.startswith(BASE) and nxt not in seen:
            q.append(nxt)

print(f"PAGES OK ({len(ok)}):")
for c, u, f in sorted(ok, key=lambda x: x[1]):
    redir = " (-> " + f[len('https://mark-automation.github.io'):] + ")" if f.rstrip('/') != u.rstrip('/') else ""
    print(f"  {c} {u[len('https://mark-automation.github.io'):]}{redir}")
print(f"\nBROKEN ({len(bad)}):")
for c, u, f in sorted(bad, key=lambda x: str(x[0])):
    print(f"  {c} {u}")

"""Keyless FX rates for IslaTrade (USD base). Vendored from den/tools/islatrade/fx_rates.py.

ECB/Frankfurter primary, open.er-api.com fallback; 6h in-memory + file cache.
"""
import json
import time
import urllib.request
from pathlib import Path

CACHE_FILE = Path(__file__).parent / "fx-cache.json"
TTL_SECONDS = 6 * 3600
SOURCES = [
    "https://api.frankfurter.app/latest?from={base}&to={to}",
    "https://open.er-api.com/v6/latest/{base}",
]
_MEM: dict | None = None
_MEM_AT = 0.0


def _http_get(url: str, timeout: float = 10.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "islatrade-fx/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def fetch_rates(base: str = "USD", targets=("PHP",)):
    errs = []
    for tpl in SOURCES:
        url = tpl.format(base=base, to=",".join(targets))
        try:
            raw = _http_get(url)
            rates = None
            if str(raw.get("result")) == "success" and raw.get("rates"):
                rates = {k.upper(): float(v) for k, v in raw["rates"].items()}
            elif raw.get("rates"):
                rates = {k.upper(): float(v) for k, v in raw["rates"].items()}
            if not rates or any(t not in rates for t in targets):
                raise ValueError("bad shape")
            return {"base": base.upper(), "rates": {t: rates[t] for t in targets},
                    "as_of": raw.get("date") or raw.get("time_last_update_utc", ""),
                    "source": url.split("/")[2], "fetched": time.time()}
        except Exception as e:  # noqa: BLE001
            errs.append(f"{url.split('/')[2]}: {e}")
    raise RuntimeError("; ".join(errs))


def get_usdphp() -> float | None:
    """USD->PHP rate with 6h memory cache; falls back to file cache; else None."""
    global _MEM, _MEM_AT
    if _MEM and time.time() - _MEM_AT < TTL_SECONDS:
        return _MEM["rates"]["PHP"]
    try:
        _MEM = fetch_rates("USD", ["PHP"])
        _MEM_AT = time.time()
        try:
            CACHE_FILE.write_text(json.dumps(_MEM))
        except Exception:
            pass
        return _MEM["rates"]["PHP"]
    except Exception:
        try:
            c = json.loads(CACHE_FILE.read_text())
            return c["rates"]["PHP"]
        except Exception:
            return None

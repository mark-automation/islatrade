# IslaTrade v2 — Architecture & Roadmap

Written 2026-08-23 after review verdict: "backend premature, cartoon visuals,
no real capability." This document is the contract for fixing all three.

## Current state (honest audit)

- FastAPI + stdlib sqlite3, server-rendered Jinja2, one process, port 8500.
- Supplier side works: auth, product CRUD, RFQ inbox, quotes, messaging, reviews,
  admin panel. 33 pytest cases green.
- **Missing**: buyer accounts, quote acceptance, orders, transactions.
- **Fragile**: SQLite journal defaults (SQLITE_BUSY under concurrency),
  in-memory rate limiter (resets on restart), no pagination, no full-text search,
  no cache/compression headers.
- **Looks**: all product/category imagery is procedurally generated SVG
  (gradient circles + text). Reads as cartoons, not a marketplace.

## Target architecture

```
Browser ── FastAPI (uvicorn)
            ├─ Jinja2 SSR pages (public, buyer, supplier, site-admin)
            ├─ JSON API (/api/*, guarded)
            └─ SQLite (WAL mode, indexed, FTS5)
                 ├─ entities: suppliers, buyers, products, categories
                 ├─ trade:    rfqs, quotes, messages, orders, notifications
                 └─ ops:      sessions, rate_limits, reviews
Static mirror (GitHub Pages) = marketing preview only, regenerated via gen_static.py
```

Stack stays deliberately boring: one process, stdlib sqlite3, hand-written CSS.
Free-tier constraint stands ($0 run cost). Postgres migration trigger documented
in DEPLOY.md (>50 concurrent writers or multi-host deploy).

## Phases

### P0 — Traffic floor (robustness)
- [x] `PRAGMA journal_mode=WAL`, `busy_timeout=5000`, foreign_keys in `db()`
- [x] Indexes: products(category_id), rfqs(product_id), rfqs(category_id),
      messages(rfq_id), notifications(supplier_id,read), sessions(supplier_id)
- [x] Rate limiting moved to `rate_limits` table (sliding window, survives
      restarts, periodic cleanup)
- [x] `/products` pagination (?page=, 24/page) + FTS5 search over
      products.name/descr with LIKE fallback
- [x] GZipMiddleware + static asset cache headers

### P1 — Trust & correctness
- [x] RFQ tracking tokens: `rfqs.token`; tracking page requires email+token
      pair (fixes anonymous-thread-read hole); token surfaced to buyer at
      submission + on every notification link

### P2 — Real capability: close the loop
- [x] `buyers` table + pbkdf2 auth (`it_buyer` cookie), buyer register/login
- [x] Buyer dashboard: my RFQs, threads, quotes side-by-side
- [x] Accept quote -> `orders` table (status: placed → producing → shipped →
      delivered), supplier notified, both dashboards show order state
- [x] Legacy anonymous RFQs still trackable via email+token (no data loss)

### P3 — Look like a marketplace, not a cartoon
- [x] Real photography via Wikimedia Commons API (CC/PD licensed, per-product
      keyword search, downloaded to static/img/p/, attribution in CREDITS.md);
      SVG art kept only as automatic fallback when no photo found
- [x] Category cards get real photos; hero stays photographic
- [x] Mobile pass: every page type screenshotted at 390px, defects fixed

## Non-goals (v2)
Payments/escrow (blocked on Dan: GCash/Maya account decision), multi-image
uploads to S3 (local disk fine at this scale), websockets.

## Verification bar
Every phase lands with: pytest additions covering the new behavior, full suite
green, curl/TestClient evidence, screenshots for visual changes.

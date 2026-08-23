# IslaTrade — The Philippines' B2B Marketplace

Alibaba-model sourcing platform, PH-first: verified Filipino suppliers, product
listings with ₱ pricing and MOQs, RFQ → quote → messaging loop, reviews, and
Trade-Assured badges.

## Stack

FastAPI + SQLite + Jinja2. One process, no build chain. Deploys anywhere.

## Run locally

```bash
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8500
```

First boot auto-creates the DB and seeds 8 industries, 12 verified suppliers,
32 products. Demo supplier login: `demo@islatrade.ph` / `islatrade`.

## Deploy (pick one)

### Render
1. New → Web Service → connect repo
2. Build: `pip install -r requirements.txt`
3. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add persistent disk mounted at `/app/data` (optional — SQLite lives in ./)

### Fly.io
```bash
fly launch --no-deploy   # detects Dockerfile
fly volumes create islatrade_data --size 1
fly deploy
```

### Railway
Connect repo → Railway auto-detects Dockerfile → deploy.

## Post-deploy checklist

- [ ] Domain + HTTPS (Caddy or platform TLS)
- [ ] Point sitemap base URL (`main.py` → sitemap()) at the live domain
- [ ] Rotate demo supplier credentials
- [ ] SQLite → Postgres migration when write volume grows
- [ ] Email notifications (SMTP creds) for RFQ/quote alerts

## Routes

| Page | Path |
|---|---|
| Home | `/` |
| Product search + filters | `/products?q_=&cat=&region=` |
| Product detail + reviews | `/product/{slug}` |
| Suppliers | `/suppliers`, `/supplier/{slug}` |
| RFQ flow | `/rfq`, `/rfq/sent`, `/rfq/tracking?email=` |
| Supplier login/dashboard | `/login`, `/supplier-admin` |
| JSON API | `/api/products`, `/api/rfqs` |
| SEO | `/sitemap.xml`, `/robots.txt` |
| Health | `/health` |

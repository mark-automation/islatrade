# IslaTrade — Deploy

FastAPI + SQLite, zero build chain. Health endpoint: `/health`.

## Recommended (free): Render
1. Push this repo to GitHub (done: mark-automation/islatrade).
2. render.com > New > Blueprint > connect repo (uses render.yaml, free plan).
   - Or manually: Runtime=Python, Build=`pip install -r requirements.txt`,
     Start=`uvicorn main:app --host 0.0.0.0 --port $PORT`, Health=/health.
3. Free tier gives https://islatrade.onrender.com. Caveats: spins down after
   15min idle (~30s cold start) and disk is EPHEMERAL — DB resets on redeploys.

## Data persistence (when needed)
- Render paid disk ($0.25/GB/mo) mounted at /data, set DB path, OR
- Turso free tier (libSQL, SQLite wire-compatible) — needs small driver change.

## Docker (any VPS/Fly/Railway)
    docker build -t islatrade . && docker run -p 8500:8500 -v $PWD/data:/app islatrade

## Local
    python main.py   # binds 0.0.0.0:$PORT (default 8500)

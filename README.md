# SENG2021

## Local development

Backend:

```bash
cd backend
make dev
```

If `make dev` reports that port `8000` is already in use, stop the existing backend process first and then rerun it. Websocket support comes from the synced backend dev environment, so make sure `backend/.venv` has been refreshed with `uv sync --group dev` after dependency changes.

Voice transcript parsing now uses Groq hosted structured extraction. Set `GROQ_API_KEY` before starting the backend if you want finalized transcripts to update the draft:

```bash
cd backend
GROQ_API_KEY=your_key_here make dev
```

You can also place the key in either `backend/.env`, `backend/.env.local`, `.env`, or `.env.local`:

```bash
GROQ_API_KEY=your_key_here
```

If you add or change the key after the backend is already running, restart `make dev` so the new value is picked up.

Optional backend parser settings:

```bash
GROQ_MODEL=openai/gpt-oss-20b
GROQ_TIMEOUT_SECONDS=20
GROQ_BASE_URL=https://api.groq.com/openai/v1
```

If `GROQ_API_KEY` is unset, websocket sessions still work, but transcript parsing becomes warning-only and the draft will not auto-update from speech.

Frontend:

```bash
bun dev
```

`BUN_PUBLIC_BACKEND_URL` is optional. If it is unset, the frontend derives the backend URL from the current browser hostname and uses port `8000`.

If you want to override it explicitly:

```bash
BUN_PUBLIC_BACKEND_URL=http://localhost:8000 bun dev
```

## Current MVP flow

The current frontend and API expose a draft-order MVP. Users can create, edit, view, and delete
orders while they remain in `DRAFT` status. Submission/finalization plus downstream invoice and
despatch generation are planned for the next sprint and are not part of the current runtime flow.

## Deployment

### Backend on Render

Deploy the `backend` directory as a Render Web Service.

- App root: `backend`
- Instance type: `Free`
- Health check path: `/v1/health`
- Build command: `pip install -r requirements.txt`
- Start command: `PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Backend runtime file:

- `backend/requirements.txt`

Required Render backend environment variables:

```bash
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
GROQ_API_KEY=your_groq_api_key
ALLOWED_ORIGINS=https://your-render-frontend.onrender.com
```

Optional backend parser settings:

```bash
GROQ_MODEL=openai/gpt-oss-20b
GROQ_TIMEOUT_SECONDS=20
GROQ_BASE_URL=https://api.groq.com/openai/v1
```

`ALLOWED_ORIGINS` is a comma-separated allowlist for exact origins. If it is unset, the backend only keeps localhost dev origins enabled, so set it to your Render static site origin before going live.

Render free web services spin down after 15 minutes of inactivity. Expect the first HTTP request or websocket reconnect after the service goes idle to take longer while the backend wakes up.

### Frontend on Render Static Site

Deploy the repo root as a Render Static Site.

- Build command: `bun install --frozen-lockfile && bun run build`
- Publish directory: `dist`

Set this Render frontend environment variable:

```bash
BUN_PUBLIC_BACKEND_URL=https://your-render-backend.onrender.com
```

`BUN_PUBLIC_BACKEND_URL` is the deployed backend origin. The frontend will derive the websocket endpoint from it automatically, so `https://...` becomes `wss://.../v1/order/draft/ws`.

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

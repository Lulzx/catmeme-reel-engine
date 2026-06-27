# Cat Reel Studio — web UI

A Vite + React + [HeroUI](https://heroui.com/) front-end for the cat-meme reel
engine. Four sections:

- **Gallery** — every rendered reel, played in a lightbox
- **Library** — the described clip catalog, searchable + filterable
- **Stories** — view a narrative beat-by-beat, edit its JSON, and render it with
  a **live streaming log**
- **Match** — the emotion → clip matcher as an interactive playground

It talks to the FastAPI backend in [`../engine/server.py`](../engine/server.py).

## Run (production)

From the repo root:

```bash
pip install -r requirements.txt      # fastapi, uvicorn, pillow
cd web && npm install && npm run build
cd .. && python3 engine/server.py    # -> http://localhost:8000
```

The backend serves this app's built files **and** the API + media from one port.

## Develop (hot reload)

```bash
python3 engine/server.py             # API on :8000
cd web && npm run dev                # UI on :5173, proxies /api + /media to :8000
```

## Stack

- HeroUI v3 (`@heroui/react`) + Tailwind CSS v4 (`@tailwindcss/vite`)
- framer-motion for the lightbox transitions
- Server-Sent Events for the live render console

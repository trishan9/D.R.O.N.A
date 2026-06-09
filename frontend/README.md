# D.R.O.N.A. Frontend

Next.js 14 (App Router) dashboard for the **D.R.O.N.A.** bias-aware academic
advising system. It talks to the FastAPI backend in [`drona/api/`](../drona/api)
over REST and WebSocket — the advising request path stays **local-only** (Ollama).

## Features

- **Streaming chat** — questions stream node-by-node over `WS /ws/advise`
  (bias check → retrieve → generate → verify → format), then render the answer.
- **Profile builder** — session-scoped, no PII, nothing persisted. Year, interests,
  skills (with self-rated levels), completed modules, aspirations, geography.
- **Multiple pathways** — every answer surfaces several evidence-backed options
  (anti-anchoring by design), each with Softwarica-module matches, Nepal vs. global
  evidence, and confidence.
- **Citation drill-down** — open the exact excerpts each claim is grounded in,
  colour-coded by data tier (Nepal / regional / international / synthetic).
- **Pathway comparison** — head-to-head table across the same dimensions.
- **Anti-bias gamification**
  - Evidence **diversity meter** (recharts donut over tiers)
  - Exploration **badges** that reward breadth and evidence-checking, not fast commitment
  - **Skill map** — a graph of what you have vs. what pathways grow (not a ladder)
  - **Counter-recommendation panel** — the option you'd likely overlook (anti-confirmation)
  - **Reversibility tags** — each next step marked easily-undone vs. big-commitment
    (anti loss-aversion)
- **Bias flags** — transparent display of which cognitive biases the backend
  detected in your question and how the answer countered them.

## Stack

Next.js 14 · React 18 · TypeScript · Tailwind CSS · shadcn/ui (new-york) ·
Radix primitives · lucide-react · recharts.

## Run

```bash
# 1. Start the backend (from the repo root)
pip install -e ".[backend]"
python scripts/run_api.py            # serves http://localhost:8000

# 2. Start the frontend
cd frontend
cp .env.example .env.local           # set NEXT_PUBLIC_DRONA_API_URL if not :8000
npm install
npm run dev                          # http://localhost:3000
```

The header shows a live backend health indicator. If the backend is offline the
chat surfaces a clear message with the command to start it.

## Scripts

| Command | Purpose |
|---|---|
| `npm run dev` | Dev server (hot reload) |
| `npm run build` | Production build |
| `npm run start` | Serve the production build |
| `npm run lint` | Next.js ESLint |
| `npm run typecheck` | `tsc --noEmit` |

## Configuration

`NEXT_PUBLIC_DRONA_API_URL` (default `http://localhost:8000`) — base URL of the
FastAPI backend. The WebSocket URL is derived from it automatically.

## Notes

- The TypeScript contracts in [`lib/types.ts`](./lib/types.ts) mirror the Pydantic
  contracts in `drona/contracts/__init__.py` and `drona/api/schemas.py`. Keep them
  in sync if the backend changes.
- All anti-bias logic (diversity score, badges, counter-recommendation selection,
  reversibility classification) lives in [`lib/gamification.ts`](./lib/gamification.ts)
  as pure functions.

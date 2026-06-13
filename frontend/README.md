# D.R.O.N.A. Frontend

A **multi-page Next.js 14 (App Router)** web platform for the **D.R.O.N.A.**
bias-aware, locally-grounded robotic advising system — effectively a web version
of the robot itself. It talks to the FastAPI backend in [`drona/api/`](../drona/api)
over REST + WebSocket (advising stays **local-only**, Ollama), and to the live
ROS2 graph over **rosbridge** for the robot page.

## Pages (sidebar navigation)

| Route | Page | What it does |
|---|---|---|
| `/` | **Dashboard** | Overview: system status, your progress, quick actions, recent questions |
| `/advisor` | **Advisor** | The core AI — profile-aware streaming chat over `WS /ws/advise` |
| `/pathways` | **Pathways** | Explore / compare evidence-backed pathways + citation drill-down + counter-recommendation |
| `/skills` | **Skills & Interests** | Curriculum skill map, self-assessed skills, interest alignment, step reversibility |
| `/analytics` | **Analytics** | Live session metrics + C1–C4 charts (tier mix, gesture jerk live; retrieval/bias reference) |
| `/robot` | **Robot Control** | In-browser 6-DOF gesture twin + telemetry + session FSM + engagement, with **live ROS2** mode |
| `/profile` | **Profile** | Session-scoped academic profile + device-local identity + question history (no PII) |
| `/achievements` | **Achievements** | Anti-bias exploration badges, diversity, habits |
| `/preferences` | **Preferences** | Theme (light/dark/system), advising defaults, backend + rosbridge URLs, data reset |
| `/about` | **About** | Architecture, research contributions, tech stack, ethics |

## Highlights

- **Robot twin** — `lib/robot.ts` is a 1:1 port of `drona/interaction/demonstration.py`
  (joint limits, rest pose, and the exact gesture keyframes), so the animated arm
  plays the *same* motions as the ROS2 policy. Live mode connects to rosbridge,
  mirrors `/drona/joint_states`, and calls the `/drona/execute_gesture` service.
- **Anti-bias UX** — multiple pathways by default, a counter-recommendation that
  challenges your stated interest, reversibility tags, an evidence-diversity meter,
  and exploration badges that reward breadth over fast commitment.
- **Theming** — DataCamp-style modern-minimal design system with full light/dark
  support (`next-themes`), an emerald brand accent, and the Nepal-first data-tier
  palette preserved for provenance.
- **Privacy** — everything (profile, history, prefs) is device-local
  (`localStorage`); the only thing sent is the PII-free `AdviseRequest`.

## Stack

Next.js 14 · React 18 · TypeScript · Tailwind CSS · shadcn/ui (new-york) ·
Radix primitives · next-themes · lucide-react · recharts.

## Run

```bash
# 1. Backend (from repo root)
pip install -e ".[backend]"
python scripts/run_api.py            # http://localhost:8000

# 2. Frontend
cd frontend
npm install
npm run dev                          # http://localhost:3000

# 3. (optional) live robot — inside WSL2, see docs/wsl_setup.md §9
ros2 launch drona_bringup drona_system.launch.py rosbridge:=true
```

The top bar shows a live backend health indicator; the Advisor surfaces a clear
message (with the start command) if the backend is offline.

## Scripts

| Command | Purpose |
|---|---|
| `npm run dev` | Dev server (hot reload) |
| `npm run build` | Production build |
| `npm run start` | Serve the production build |
| `npm run lint` | Next.js ESLint |
| `npm run typecheck` | `tsc --noEmit` |

## Architecture notes

- **Routing** — all pages live under the `app/(app)/` route group, which shares one
  layout (`components/layout/app-shell.tsx`: fixed sidebar + sticky topbar).
- **State** — `lib/store.tsx` is a React context persisted to `localStorage`; the
  Advisor's response flows to Pathways / Skills / Achievements / Analytics.
- **Contracts** — `lib/types.ts` mirrors the Pydantic contracts in
  `drona/contracts/` + `drona/api/schemas.py`. Keep in sync if the backend changes.
- **Pure logic** — anti-bias scoring (`lib/gamification.ts`), analytics
  (`lib/analytics.ts`), and robot kinematics (`lib/robot.ts`) are dependency-free
  and unit-reasonable.

## Configuration

`NEXT_PUBLIC_DRONA_API_URL` (default `http://localhost:8000`) sets the backend base
URL at build time. It can be overridden at runtime per-device on the **Preferences**
page; the WebSocket URL is derived automatically. The rosbridge URL (default
`ws://localhost:9090`) is also set on Preferences / Robot Control.

# Optigo

**One App, Every Route, Optimized for You**

A multimodal journey-planning platform (app + web) that finds the most optimal route between two points based on *your* constraints — time, cost, or distance — instead of defaulting to one fixed suggestion. Launching first in **Navi Mumbai**.

Built as a Final PBL-Mini Project.

---

## The Problem

Getting around a city today means juggling separate apps — one for cabs, one for metro, one for buses, one for maps — and manually comparing them yourself. There's no single system that says: *"Given your priorities, here are all your real options, ranked."*

## The Idea

Optigo treats a city's transport network like a graph — stations, bus stops, auto stands, and taxi hubs are **nodes**; routes between them are **edges**. The engine scans this graph and surfaces multiple viable paths, each scored on time, cost, and distance.

**Positioning:** *Google Maps + Chalo + Splitwise of urban mobility — one app that finds, compares, books, and tracks every way to get where you're going.*

---

## Repo Structure

```
optigo/
├── backend/          FastAPI + NetworkX routing engine — see backend/README.md
├── frontend/          Next.js web client (in progress)
├── .gitignore
└── README.md          you are here
```

---

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (TypeScript, Tailwind) — React Native planned later |
| Backend | FastAPI (Python) |
| Database | Supabase (Postgres + PostGIS) |
| Routing engine | NetworkX (Dijkstra) |
| Maps | Mapbox |
| Hosting | Vercel (frontend) + Render (backend) |

---

## Current Status

**Backend — live and functional.** Real Navi Mumbai transit data (23 stations, 23 routes across three lines: the Vashi–Panvel Harbour rail corridor, the Uran-Ulwe branch via Sagar Sangam junction cut off at Kharkopar, and the Belapur–Pendhar Metro Line 1) is stored in Supabase and served through a working `/route` and `/compare` API. See [`backend/README.md`](backend/README.md) for full setup and endpoint docs.

**Frontend — not yet built.** Currently default `create-next-app` boilerplate, no UI wired to the backend.

**Fare/time data — estimated**, not yet sourced from official Central Railway or Navi Mumbai Metro fare charts. Flagged for verification before any public demo.

---

## Full Feature Set (Vision)

| # | Feature | Description |
|---|---|---|
| 1 | Unified Ticketing | Book across rail, metro, bus, and auto/cab providers in one place |
| 2 | Multi-Factor Comparison | Compare routes by time, fuel/fiscal cost, and emissions |
| 3 | Graph-Based Route Engine | Node-edge model connecting all transit hubs in an area |
| 4 | Offline Ticket Wallet | Store trip tickets offline, like Google Wallet |
| 5 | Emergency Location Sharing | Share live location with trusted contacts during a trip |
| 6 | AI Trip Assistant | Suggests and adjusts your plan on the fly |
| 7 | 3D Space Mapping | Indoor maps for malls, parking lots, parks |
| 8 | Local Travel Guides | Hire vetted local guides (85/15 revenue split) |
| 9 | Accessibility & Equity Pricing | Discounted fares for PWD, women, elderly |
| 10 | Advance Journey Planning | Web-first trip planning tools |
| 11 | Live Transit Radar | Real-time map view of moving vehicles |
| 12 | Public Vehicle Status | Live delays/crowding/ETAs, consolidated |

The current build covers the foundation for #2 and #3. Everything else is roadmap, planned for after the initial submission.

### Architecture notes for later phases
- **Plan Mode vs. Live Mode**: Feature #10 (Advance Planning) is a web-first, "before you leave" experience; most of the rest (#3, #11, #12) are real-time, on-the-go tools. Structuring the product around these two modes could make both UX and engineering cleaner.
- **Shared Live Data Engine**: Features #11 (Radar) and #12 (Status) depend on the same live-location/schedule feeds, just presented differently — worth building as one backend with two frontends.
- **Data partnerships are a dependency, not just a UI feature**: live radar/status for buses, autos, and cabs needs GPS feeds from operators or crowdsourced data, unlike rail data which has more established public feeds.
- Checked for a public API/MCP for live Mumbai local train status (m-Indicator, Where is my Train, NTES, RailRadar) — none currently expose one publicly. Revisit if that changes.

---

## Timeline

- **Sep 11, 2026** — showable web demo
- **Oct 9, 2026** — final submission

## License

Not yet decided.

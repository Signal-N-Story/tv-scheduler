# ARIZE TV Scheduler

Automated workout card scheduling and display system for 180 Fitness Club.

## Overview

The TV Scheduler extends the ARIZE Plan2Card system to automate multi-day scheduling of workout cards to 3 gym TVs. Coaches upload once per week, cards auto-rotate at midnight, and a dashboard provides full visibility and emergency override capability.

## Architecture

```
PushPress CSV → Plan2Card (render) → TV Scheduler (store + serve) → Fire TV displays
```

### TV Configuration

| TV | Board Type | Device | Default Version |
|----|-----------|--------|----------------|
| TV1 | MAINBOARD_FRONT | Fire TV | Rx |
| TV2 | MODBOARD_FRONT | Fire TV | Mod |
| TV3 | MAINBOARD_BACK | Fire Stick | Mirrors TV1 |

### 4-Layer Fallback Chain

1. **SQLite DB** (primary source of truth)
2. **JSON Snapshot** (written on every DB write)
3. **Static HTML Cache** (file-based fallback)
4. **Branded Splash Screen** (always shows something)

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, SQLite
- **Frontend**: HTML/CSS/JS (dashboard), Jinja2 templates
- **Display**: Auto-refreshing full-screen HTML pages for Fire TV browsers
- **Timezone**: America/Chicago (CST/CDT)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize the database
python -m src.models.database

# Run the server
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### Schedule Management (Session Auth)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/schedule` | Push approved cards to schedule (1-31 days) |
| GET | `/api/schedule` | Get full schedule (paginated) |
| GET | `/api/schedule/{date}` | Get cards for a specific date |
| PUT | `/api/schedule/{date}/{board}` | Edit a future scheduled card |
| DELETE | `/api/schedule/{date}` | Remove a scheduled day |
| POST | `/api/schedule/override` | Emergency override — instant card swap |
| GET | `/api/schedule/status` | Current live status on each TV |
| GET | `/api/schedule/audit` | Audit log of all changes |

### TV Display (No Auth)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/tv/mainboard` | Serves today's main board card full-screen |
| GET | `/tv/modboard` | Serves today's mod board card full-screen |
| GET | `/tv/status` | JSON health check for TV connectivity |

### Dashboard

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/dashboard` | Full management dashboard UI |

## Project Structure

```
tv-scheduler/
├── src/
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Configuration & constants
│   ├── models/
│   │   ├── database.py         # SQLite setup & connection
│   │   └── schemas.py          # Pydantic models
│   ├── routes/
│   │   ├── schedule.py         # /api/schedule/* endpoints
│   │   ├── tv_display.py       # /tv/* endpoints
│   │   └── dashboard.py        # /dashboard endpoint
│   ├── services/
│   │   ├── scheduler.py        # Schedule CRUD & business logic
│   │   ├── fallback.py         # 4-layer fallback chain
│   │   ├── audit.py            # Audit logging
│   │   └── swap.py             # Midnight card swap service
│   ├── templates/              # Jinja2 HTML templates
│   └── static/                 # CSS, JS, images
├── tests/
├── cache/                      # Static HTML cache (Layer 3)
├── docs/                       # Additional documentation
├── requirements.txt
├── .env.example
└── README.md
```

## Build Plan

| Phase | Scope | Est. Hours |
|-------|-------|-----------|
| Phase 1 | Backend Core — SQLite, schedule endpoints, TV display, JSON snapshots | ~3h |
| Phase 2 | Schedule UI — Calendar view, upload flow, preview | ~2h |
| Phase 3 | Dashboard — Status monitoring, audit log, health checks | ~3h |
| Phase 4 | Hardening — Fallback chain, error handling, self-healing | ~2h |

## License

Proprietary — 180 Fitness Club / Qualify.AI
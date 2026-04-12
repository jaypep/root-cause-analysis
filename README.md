# Root Cause Analysis 🌱

A self-hosted garden management dashboard designed for a 10" touchscreen display, accessible from any browser on the same local network. Built with FastAPI and vanilla JavaScript — no build step, no external services, no API keys required.

## Features

- **Dashboard** — At-a-glance stats (plants, open tasks, seeds, total harvested value). Live weather, 7-day rainfall chart, and upcoming tasks. Sync planting tasks with one tap.
- **Garden Layout** — Organise zones, beds (square-foot grid), and containers. Place and track individual plants by bed position or container. Full edit support across all records.
- **Seed Inventory** — Track seed stock with viability calculations by lot year and crop type. Viability badges (green / amber / red) give at-a-glance status. Filter to low-viability seeds. Source tracking via a managed seed sources list.
- **Planting Calendar** — Auto-generates sow indoors, sow outdoors, and transplant tasks for both spring and fall seasons based on your frost dates and seed inventory. Succession sowing supported with configurable interval and count per crop. First frost used as a hard viability cutoff — tasks are not generated for crops that can't complete before frost.
- **Task Management** — Manual and auto-generated tasks (water, fertilize, harvest, sow indoors/outdoors, transplant, pest control) with due dates and completion history. Rainfall-triggered watering tasks sync automatically. Transplant tasks are only created after you manually mark sow indoors as done.
- **Recurring Schedules** — Per-plant recurring tasks (water, fertilize, prune, spray, other) with configurable interval. Tasks generate automatically on page load and roll forward when marked done.
- **Harvest Log** — Track harvests by crop, weight (oz/lb), and organic market price. Computed value displayed on the dashboard and in the Garden ROI tab.
- **Expenses** — Log garden costs by category (seeds, soil, lumber, infrastructure, tools, etc.) with a category breakdown panel.
- **Garden ROI** — Total harvested value, total invested, and net savings. Accessible under Settings → Garden ROI.
- **Crop Catalog** — Loaded from `seed_crops.json` on startup. Editable in Manage Garden → Crops. New entries in the JSON are picked up on restart without wiping data.
- **Weather Integration** — Live current conditions, wind speed/gusts/direction via NWS. 7-day rainfall history via Open-Meteo. Displayed on the dashboard with a bar chart.
- **Garden Journal** — Dated log entries with optional title and tags. Editable after creation.
- **Help Page** — Built-in usage guide accessible from the header.
- **Light/Dark Theme** — Persistent preference, OS default respected. Shared header, navigation, and base styles centralised in `theme.js`.

## Pages

| Page | URL | Purpose |
|---|---|---|
| Dashboard | `/` | Stats, weather, upcoming tasks |
| Tasks | `/tasks` | Full task list, manual add, sync |
| Seeds | `/seeds` | Seed inventory, viability, sync |
| Plants | `/plants` | Plant list with zone/bed/container placement |
| Manage Garden | `/manage` | Zones, Beds, Containers, Crops, Schedules, Journal, Harvest, Expenses, Seed Sources |
| Settings | `/settings` | Garden config, frost dates, Garden ROI |
| Help | `/help` | Usage guide |

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic |
| Database | SQLite (file-based, no setup required) |
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| Deployment | Docker, Docker Compose |

## Weather Data Sources

All free, no API keys required:

| Source | Used for |
|---|---|
| [National Weather Service](https://www.weather.gov/documentation/services-web-api) | Current conditions, wind (ICAO station) |
| [Open-Meteo](https://open-meteo.com/) | 7-day rainfall history, 10-year frost date analysis |
| [phzmapi.org](https://phzmapi.org/) | USDA plant hardiness zone lookup |
| [Nominatim](https://nominatim.org/) (OpenStreetMap) | Reverse geocoding for zone/frost auto-detect |

## Getting Started

### With Docker (recommended)

```bash
docker compose up
```

### Without Docker

```bash
python -m venv venv
venv\Scripts\Activate.ps1   # Windows
source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
uvicorn main:app --reload
```

The app will be available at `http://localhost:8000`.

## Configuration

Open **Settings** in the app to configure:

| Setting | Description | Default |
|---|---|---|
| Weather Station | ICAO airport code for current conditions | `KROG` |
| Latitude / Longitude | Used for zone lookup, frost dates, and precipitation | `36.3726, -94.1069` |
| Frost Dates | Last spring frost / first fall frost — manual entry or auto-detected from 10-year historical data | — |
| Growing Zone | USDA hardiness zone — manual entry or auto-detected via lat/lon | — |
| Garden Year | Current growing season | — |

## Crop Catalog & Planting Calendar

The crop catalog lives in `seed_crops.json` in the project root. This file is committed to git and is your source of truth for default crop data. Crops can also be added and edited directly in Manage Garden → Crops.

### How it works

On every startup, the app reads `seed_crops.json` and inserts any crops that don't already exist in the database (matched on name + variety). Existing records are never overwritten, so user edits are preserved. Adding new crops to the JSON and restarting is all that's needed — no DB wipe required.

### Crop fields

| Field | Description | Example |
|---|---|---|
| `name` | Crop name | `"Tomato"` |
| `variety` | Variety name, or `null` for generic | `"Cherokee Purple"` |
| `days_to_harvest` | Days from sow/transplant to harvest | `80` |
| `weeks_to_transplant` | Weeks spent indoors before going outside. `0` = direct sow | `7` |
| `direct_sow_weeks` | Weeks relative to last spring frost. Negative = before frost, positive = after | `-4` |
| `succession_weeks` | Weeks between successive sowings. `null` = sow once | `2` |
| `succession_count` | Total number of sowings in the succession | `4` |
| `notes` | Optional notes | `null` |

### Planting date logic

All dates are calculated relative to your configured frost dates:

```
Spring — transplant crop (weeks_to_transplant > 0)
  sow_indoors = last_spring_frost - weeks_to_transplant
  transplant  = last_spring_frost  (only created after sow_indoors is marked done)

Spring — direct sow crop (weeks_to_transplant = 0)
  sow_outdoors = last_spring_frost + direct_sow_weeks

Fall — frost-tolerant crops only (direct_sow_weeks < 0, weeks_to_transplant = 0)
  sow_outdoors = first_fall_frost - days_to_harvest

Viability cutoff: any task where sow_date + days_to_harvest > first_fall_frost is skipped.
Succession tasks stop at the first sowing that would push harvest past first frost.
```

### Seed viability defaults

Viability is calculated from the `seed_lot` (integer year) field on each seed entry. Defaults by crop name keyword:

| Years | Crops |
|---|---|
| 1 yr | Onion, leek, chive |
| 2 yr | Pepper, parsnip, corn |
| 3 yr | Bean, pea |
| 4 yr | Tomato, basil, beet, carrot, broccoli, cabbage, kale, chard, spinach |
| 5+ yr | Cucumber, melon, squash, lettuce |

Badges: 🟢 viable · 🟡 within 1 year of expiry · 🔴 expired · ⬜ no lot year recorded

## Database Schema

SQLite, single file (`root-cause-analysis.db`), never committed to git. Schema migrations run automatically on startup — no manual `ALTER TABLE` needed.

| Table | Purpose |
|---|---|
| `zones` | Named garden areas |
| `beds` | Raised beds with row × col grid, linked to a zone |
| `containers` | Pots, planters, grow bags — linked to a zone and/or free-text location |
| `crops` | Crop catalog |
| `plants` | Individual plants placed in a bed square or container |
| `seeds` | Seed inventory — quantity, lot year, source, viability |
| `seed_sources` | Managed list of seed companies / saved seed sources |
| `waterings` | Watering log entries |
| `schedules` | Per-plant recurring task schedules with next-due tracking |
| `tasks` | All tasks — manual and auto-generated |
| `harvests` | Harvest log — crop, weight, price per lb, computed value |
| `expenses` | Garden expense log with category breakdown |
| `journal` | Dated log entries with optional title and tags |
| `settings` | Key/value app configuration |

## API

Full REST API under `/api/`. Interactive docs at `http://localhost:8000/docs`.

| Resource | Endpoints |
|---|---|
| Zones | `GET POST PUT DELETE /api/zones` |
| Beds | `GET POST PUT DELETE /api/beds` · `GET /api/beds/{id}/grid` |
| Containers | `GET POST PUT DELETE /api/containers` |
| Crops | `GET POST PUT DELETE /api/crops` · `POST /api/crops/bulk` |
| Plants | `GET POST PUT DELETE /api/plants` |
| Seeds | `GET POST PUT DELETE /api/seeds` · `GET /api/seeds/plan` |
| Seed Sources | `GET POST DELETE /api/seed-sources` |
| Tasks | `GET POST DELETE /api/tasks` · `PATCH /api/tasks/{id}/done` · `POST /api/tasks/sync` · `POST /api/tasks/seed-plan-sync` · `POST /api/tasks/schedule-sync` |
| Schedules | `GET POST PUT DELETE /api/schedules` |
| Harvests | `GET POST DELETE /api/harvests` |
| Expenses | `GET POST DELETE /api/expenses` |
| Journal | `GET POST PUT DELETE /api/journal` |
| Waterings | `GET POST /api/waterings` |
| Weather | `GET /api/weather` |
| Growing Zone | `GET /api/growing-zone` |
| Frost Dates | `GET /api/frost-dates` |
| Settings | `GET PUT /api/settings` |

## Project Structure

```
root-cause-analysis/
├── main.py              # FastAPI app — all routes, schema, migrations
├── seed_crops.json      # Crop catalog — committed to git, auto-loaded on startup
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .gitignore           # root-cause-analysis.db excluded
└── static/
    ├── index.html       # Dashboard — weather, tasks, stats
    ├── plants.html      # Plant list and placement
    ├── manage.html      # Manage Garden — zones, beds, containers, crops, schedules, journal, harvest, expenses, seed sources
    ├── seeds.html       # Seed inventory and planting calendar sync
    ├── tasks.html       # Task list and management
    ├── settings.html    # Config, frost dates, growing zone, Garden ROI
    ├── help.html        # Usage guide
    └── theme.js         # Shared CSS, header, clock, theme toggle
```

## License

MIT

# Root Cause Analysis 🌱

A self-hosted garden management dashboard designed for a 10" touchscreen display, accessible from any browser on the same local network. Built with FastAPI and vanilla JavaScript — no build step, no external services, no API keys required.

## Features

- **Garden Layout** — Organise zones, beds (square-foot grid), and containers. Place and track individual plants by bed position or container. Containers can be assigned to a zone.
- **Seed Inventory** — Track seed stock with viability calculations by lot year and crop type. Viability badges (green / amber / red) give at-a-glance status. Filter to low-viability seeds.
- **Planting Calendar** — Auto-generates sow indoors, sow outdoors, and transplant tasks for both spring and fall seasons based on your frost dates and seed inventory. Supports succession sowing with configurable interval and count per crop.
- **Crop Catalog** — Static crop reference loaded from `seed_crops.json` on startup. New crops added to the file are picked up automatically on next restart without wiping data.
- **Task Management** — Manual and auto-generated tasks (water, fertilize, harvest, sow indoors/outdoors, transplant, pest control) with due dates and completion history. Rainfall-triggered watering tasks sync automatically.
- **Weather Integration** — Live current conditions, wind speed/gusts/direction via NWS. 7-day rainfall history via Open-Meteo. Displayed on the dashboard with a bar chart.
- **Garden Journal** — Dated log entries with tags.
- **Light/Dark Theme** — Persistent preference, OS default respected. Shared header, navigation, and base styles are centralised in `theme.js`.

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

<<<<<<< HEAD
| Setting | Description | Default |
|---|---|---|
| Weather Station | ICAO airport code for current conditions | `KROG` |
| Latitude / Longitude | Used for zone lookup, frost dates, and precipitation | `36.3726, -94.1069` |
| Frost Dates | Last spring frost / first fall frost — manual entry or auto-detected from 10-year historical data | — |
| Growing Zone | USDA hardiness zone — manual entry or auto-detected via lat/lon | — |
| Garden Year | Current growing season | — |
| Spring / Fall Windows | Season date ranges used by the planting calendar | — |

## Crop Catalog & Planting Calendar

The crop catalog lives in `seed_crops.json` in the project root. This file is committed to git and is your source of truth for all crop data.

### How it works

On every startup, the app reads `seed_crops.json` and inserts any crops that don't already exist in the database (matched on name + variety). Existing records are never overwritten, so user edits and planted data are preserved. Adding new crops to the JSON and restarting is all that's needed — no DB wipe required.

### Crop fields

| Field | Description | Example |
|---|---|---|
| `name` | Crop name | `"Tomato"` |
| `variety` | Variety name, or `null` for generic | `"Cherokee Purple"` |
| `days_to_harvest` | Days from sow/transplant to harvest | `80` |
| `weeks_to_transplant` | Weeks spent indoors before going outside. `0` = direct sow | `7` |
| `succession_weeks` | Weeks between successive sowings. `null` = sow once | `2` |
| `succession_count` | Total number of sowings in the succession. `null` = 1 | `4` |
| `notes` | Optional notes | `null` |

### Example entries

```json
[
  {
    "name": "Tomato", "variety": "Cherokee Purple",
    "days_to_harvest": 80, "weeks_to_transplant": 7,
    "succession_weeks": null, "succession_count": null
  },
  {
    "name": "Lettuce", "variety": "Buttercrunch",
    "days_to_harvest": 55, "weeks_to_transplant": 0,
    "succession_weeks": 2, "succession_count": 4
  }
]
```

### Planting date calculations

All dates are calculated relative to your configured frost dates:

```
Spring
  sow_outdoors = last_spring_frost - days_to_harvest
  sow_indoors  = sow_outdoors - (weeks_to_transplant × 7)
  transplant   = last_spring_frost

Fall
  sow_outdoors = first_fall_frost - days_to_harvest
  (same pattern)

Succession (e.g. lettuce, 2 weeks × 4)
  Sow #1 = base sow date
  Sow #2 = base + 2 weeks
  Sow #3 = base + 4 weeks
  Sow #4 = base + 6 weeks
```

Tasks are named `Sow indoors: Lettuce — Buttercrunch (Spring) #1` etc. Dates that have already passed are auto-closed. Re-syncing is safe — existing tasks are updated, not duplicated.

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

SQLite, single file (`root-cause-analysis.db`), never committed to git. Schema migrations run automatically on startup — no manual `ALTER TABLE` needed when the schema changes.

| Table | Purpose |
|---|---|
| `zones` | Named garden areas |
| `beds` | Raised beds with row × col grid, linked to a zone |
| `containers` | Pots, planters, grow bags — linked to a zone and/or free-text location |
| `crops` | Crop catalog (loaded from `seed_crops.json`) |
| `plants` | Individual plants placed in a bed square or container |
| `seeds` | Seed inventory — quantity, lot year, source, viability |
| `waterings` | Watering log entries |
| `schedules` | Per-plant watering schedules with next-due tracking |
| `tasks` | All tasks — manual and auto-generated |
| `journal` | Dated log entries with tags |
| `settings` | Key/value app configuration |
=======
| Setting | Description |
|---|---|
| Weather Station | ICAO airport code for current conditions |
| Latitude / Longitude | Used for zone lookup, frost dates, and precipitation | 
| Frost Dates | Last spring frost / first fall frost (manual or auto-detected) |
| Growing Zone | USDA hardiness zone (manual or auto-detected) |
| Garden Year | Current growing season year |
>>>>>>> f56ce99531897beac04b6a99907fe2fd2c125f65

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
| Tasks | `GET POST DELETE /api/tasks` · `PATCH /api/tasks/{id}/done` · `POST /api/tasks/sync` · `POST /api/tasks/seed-plan-sync` |
| Journal | `GET POST PUT DELETE /api/journal` |
| Waterings | `GET POST /api/waterings` |
| Schedules | `GET POST PUT DELETE /api/schedules` |
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
    ├── manage.html      # Garden layout — zones, beds, containers, plants
    ├── seeds.html       # Seed inventory and planting calendar sync
    ├── tasks.html       # Task list and management
    ├── settings.html    # Weather station, frost dates, growing zone
    └── theme.js         # Shared CSS, header, clock, theme toggle
```

## License

MIT

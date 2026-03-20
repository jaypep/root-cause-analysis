# Garden Manager

A full-stack garden management application for tracking crops, seeds, planting schedules, tasks, and real-time weather — built with FastAPI and vanilla JavaScript.

## Features

- **Garden Layout** — Organize garden zones, beds (square-foot grid), and containers. Place and track individual plants by location.
- **Seed Inventory** — Track seed stock with viability calculations, lot years, source, and quantity. Generate spring/fall planting calendars.
- **Task Management** — Create and manage tasks (water, fertilize, harvest, sow indoors/outdoors, transplant, pest control) with due dates and completion history. Tasks auto-sync with weather data.
- **Weather Integration** — Live current conditions via the National Weather Service. 7-day rainfall history and forecast via Open-Meteo. Automatic frost date detection (10-year historical analysis) and USDA growing zone lookup.
- **Garden Journal** — Log dated entries with tags.
- **Light/Dark Theme** — Persistent theme preference with a shared header and navigation across all pages.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic |
| Database | SQLite (file-based, no setup required) |
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| Deployment | Docker, Docker Compose |

## Weather Data Sources

All free, no API keys required:

- [National Weather Service](https://www.weather.gov/documentation/services-web-api) — current observations (ICAO station code)
- [Open-Meteo](https://open-meteo.com/) — precipitation history and forecast
- [phzmapi.org](https://phzmapi.org/) — USDA plant hardiness zone lookup by lat/lon
- [Nominatim](https://nominatim.org/) (OpenStreetMap) — reverse geocoding

## Getting Started

### With Docker (recommended)

```bash
docker compose up
```

The app will be available at `http://localhost:8000`.

### Without Docker

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Configuration

Open **Settings** in the app to configure:

| Setting | Description | Default |
|---|---|---|
| Weather Station | ICAO airport code for current conditions | `KROG` |
| Latitude / Longitude | Used for zone lookup, frost dates, and precipitation | `36.3726, -94.1069` |
| Frost Dates | Last spring frost / first fall frost (manual or auto-detected) | — |
| Growing Zone | USDA hardiness zone (manual or auto-detected) | — |
| Garden Year | Current growing season year | — |

## API

The backend exposes a REST API under `/api/`:

| Resource | Endpoints |
|---|---|
| Zones | `GET/POST/PUT/DELETE /api/zones` |
| Beds | `GET/POST/PUT/DELETE /api/beds`, `GET /api/beds/{id}/grid` |
| Containers | `GET/POST/PUT/DELETE /api/containers` |
| Crops | `GET/POST/PUT/DELETE /api/crops`, `POST /api/crops/bulk` |
| Plants | `GET/POST/PUT/DELETE /api/plants` |
| Seeds | `GET/POST/PUT/DELETE /api/seeds`, `GET /api/seeds/plan` |
| Tasks | `GET/POST/DELETE /api/tasks`, `POST /api/tasks/{id}/done`, `POST /api/tasks/sync` |
| Journal | `GET/POST/PUT/DELETE /api/journal` |
| Waterings | `GET/POST /api/waterings` |
| Schedules | `GET/POST/PUT/DELETE /api/schedules` |
| Weather | `GET /api/weather` |
| Growing Zone | `GET /api/growing-zone` |
| Frost Dates | `GET /api/frost-dates` |
| Settings | `GET/PUT /api/settings` |

Interactive API docs are available at `http://localhost:8000/docs`.

## Project Structure

```
root-cause-analysis/
├── main.py              # FastAPI app — all routes and database logic
├── requirements.txt     # Python dependencies
├── Dockerfile
├── docker-compose.yml
└── static/
    ├── index.html       # Dashboard (weather, tasks, stats)
    ├── manage.html      # Garden layout (zones, beds, containers, plants)
    ├── seeds.html       # Seed inventory and planting calendar
    ├── tasks.html       # Task list and management
    ├── settings.html    # App configuration
    └── theme.js         # Shared header, clock, and theme system
```

## License

MIT

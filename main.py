from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, model_validator
from typing import Optional
import sqlite3
import os
import urllib.request
import json
from datetime import datetime

app = FastAPI(title="Root Cause Analysis")

DB_PATH = os.getenv("DB_PATH", "root-cause-analysis.db")

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS zones (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT NOT NULL,
            notes    TEXT,
            created  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS beds (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            zone_id  INTEGER REFERENCES zones(id) ON DELETE SET NULL,
            name     TEXT NOT NULL,
            rows     INTEGER NOT NULL,
            cols     INTEGER NOT NULL,
            notes    TEXT,
            created  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS containers (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            type          TEXT,
            size_gallons  REAL,
            notes         TEXT,
            created       TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS crops (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            name             TEXT NOT NULL,
            variety          TEXT,
            days_to_harvest  INTEGER,
            notes            TEXT,
            created          TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS plants (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            crop_id       INTEGER REFERENCES crops(id) ON DELETE RESTRICT,
            name          TEXT NOT NULL,
            variety       TEXT,
            bed_id        INTEGER REFERENCES beds(id) ON DELETE SET NULL,
            row           INTEGER,
            col           INTEGER,
            container_id  INTEGER REFERENCES containers(id) ON DELETE SET NULL,
            planted       TEXT,
            notes         TEXT,
            created       TEXT DEFAULT (datetime('now')),
            UNIQUE (bed_id, row, col)
        );

        CREATE TABLE IF NOT EXISTS waterings (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id  INTEGER REFERENCES plants(id) ON DELETE CASCADE,
            watered   TEXT DEFAULT (datetime('now')),
            notes     TEXT
        );

        CREATE TABLE IF NOT EXISTS schedules (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id       INTEGER UNIQUE REFERENCES plants(id) ON DELETE CASCADE,
            interval_days  INTEGER NOT NULL,
            last_watered   TEXT,
            next_due       TEXT
        );

        CREATE TABLE IF NOT EXISTS journal (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            title    TEXT,
            body     TEXT NOT NULL,
            tags     TEXT,
            created  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS settings (
            key    TEXT PRIMARY KEY,
            value  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            type      TEXT NOT NULL,
            title     TEXT NOT NULL,
            due_date  TEXT,
            done      INTEGER DEFAULT 0,
            done_at   TEXT,
            notes     TEXT,
            created   TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ZoneIn(BaseModel):
    name: str
    notes: Optional[str] = None

class BedIn(BaseModel):
    zone_id: Optional[int] = None
    name: str
    rows: int
    cols: int
    notes: Optional[str] = None

class ContainerIn(BaseModel):
    name: str
    type: Optional[str] = None
    size_gallons: Optional[float] = None
    notes: Optional[str] = None

class CropIn(BaseModel):
    name: str
    variety: Optional[str] = None
    days_to_harvest: Optional[int] = None
    notes: Optional[str] = None

class PlantIn(BaseModel):
    name: str
    variety: Optional[str] = None
    crop_id: Optional[int] = None
    bed_id: Optional[int] = None
    row: Optional[int] = None
    col: Optional[int] = None
    container_id: Optional[int] = None
    planted: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def check_location(self):
        in_bed = self.bed_id is not None
        in_container = self.container_id is not None
        if in_bed and in_container:
            raise ValueError("A plant can be in a bed or a container, not both")
        if in_bed and (self.row is None or self.col is None):
            raise ValueError("row and col are required when bed_id is set")
        return self

class WateringIn(BaseModel):
    plant_id: int
    notes: Optional[str] = None

class ScheduleIn(BaseModel):
    plant_id: int
    interval_days: int
    last_watered: Optional[str] = None

class JournalIn(BaseModel):
    title: Optional[str] = None
    body: str
    tags: Optional[str] = None

TASK_TYPES = {"water", "pests", "fertilize", "harvest", "sow_indoors", "sow_outdoors", "transplant"}

class TaskIn(BaseModel):
    type: str
    title: str
    due_date: Optional[str] = None
    notes: Optional[str] = None

class TaskDone(BaseModel):
    done: bool

# ---------------------------------------------------------------------------
# Zones
# ---------------------------------------------------------------------------

@app.get("/api/zones")
def list_zones():
    conn = get_db()
    rows = conn.execute("SELECT * FROM zones ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/zones", status_code=201)
def create_zone(zone: ZoneIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO zones (name, notes) VALUES (?,?)", (zone.name, zone.notes))
    conn.commit()
    row = conn.execute("SELECT * FROM zones WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)

@app.put("/api/zones/{zone_id}")
def update_zone(zone_id: int, zone: ZoneIn):
    conn = get_db()
    conn.execute("UPDATE zones SET name=?, notes=? WHERE id=?", (zone.name, zone.notes, zone_id))
    conn.commit()
    row = conn.execute("SELECT * FROM zones WHERE id=?", (zone_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Zone not found")
    return dict(row)

@app.delete("/api/zones/{zone_id}", status_code=204)
def delete_zone(zone_id: int):
    conn = get_db()
    conn.execute("DELETE FROM zones WHERE id=?", (zone_id,))
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# Beds
# ---------------------------------------------------------------------------

@app.get("/api/beds")
def list_beds(zone_id: Optional[int] = None):
    conn = get_db()
    if zone_id:
        rows = conn.execute(
            "SELECT b.*, z.name as zone_name FROM beds b LEFT JOIN zones z ON z.id=b.zone_id WHERE b.zone_id=? ORDER BY b.name",
            (zone_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT b.*, z.name as zone_name FROM beds b LEFT JOIN zones z ON z.id=b.zone_id ORDER BY b.name"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/beds/{bed_id}/grid")
def get_bed_grid(bed_id: int):
    """Returns bed dimensions and all plants keyed by row,col."""
    conn = get_db()
    bed = conn.execute("SELECT * FROM beds WHERE id=?", (bed_id,)).fetchone()
    if not bed:
        raise HTTPException(status_code=404, detail="Bed not found")
    plants = conn.execute(
        "SELECT id, name, variety, row, col, planted FROM plants WHERE bed_id=?", (bed_id,)
    ).fetchall()
    conn.close()
    grid = {f"{p['row']},{p['col']}": dict(p) for p in plants}
    return {"bed": dict(bed), "grid": grid}

@app.post("/api/beds", status_code=201)
def create_bed(bed: BedIn):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO beds (zone_id, name, rows, cols, notes) VALUES (?,?,?,?,?)",
        (bed.zone_id, bed.name, bed.rows, bed.cols, bed.notes)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM beds WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)

@app.put("/api/beds/{bed_id}")
def update_bed(bed_id: int, bed: BedIn):
    conn = get_db()
    conn.execute(
        "UPDATE beds SET zone_id=?, name=?, rows=?, cols=?, notes=? WHERE id=?",
        (bed.zone_id, bed.name, bed.rows, bed.cols, bed.notes, bed_id)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM beds WHERE id=?", (bed_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Bed not found")
    return dict(row)

@app.delete("/api/beds/{bed_id}", status_code=204)
def delete_bed(bed_id: int):
    conn = get_db()
    conn.execute("DELETE FROM beds WHERE id=?", (bed_id,))
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# Containers
# ---------------------------------------------------------------------------

@app.get("/api/containers")
def list_containers():
    conn = get_db()
    rows = conn.execute("SELECT * FROM containers ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/containers", status_code=201)
def create_container(container: ContainerIn):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO containers (name, type, size_gallons, notes) VALUES (?,?,?,?)",
        (container.name, container.type, container.size_gallons, container.notes)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM containers WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)

@app.put("/api/containers/{container_id}")
def update_container(container_id: int, container: ContainerIn):
    conn = get_db()
    conn.execute(
        "UPDATE containers SET name=?, type=?, size_gallons=?, notes=? WHERE id=?",
        (container.name, container.type, container.size_gallons, container.notes, container_id)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM containers WHERE id=?", (container_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Container not found")
    return dict(row)

@app.delete("/api/containers/{container_id}", status_code=204)
def delete_container(container_id: int):
    conn = get_db()
    conn.execute("DELETE FROM containers WHERE id=?", (container_id,))
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# Crops
# ---------------------------------------------------------------------------

@app.get("/api/crops")
def list_crops():
    conn = get_db()
    rows = conn.execute("SELECT * FROM crops ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/crops", status_code=201)
def create_crop(crop: CropIn):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO crops (name, variety, days_to_harvest, notes) VALUES (?,?,?,?)",
        (crop.name, crop.variety, crop.days_to_harvest, crop.notes)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM crops WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)

@app.put("/api/crops/{crop_id}")
def update_crop(crop_id: int, crop: CropIn):
    conn = get_db()
    conn.execute(
        "UPDATE crops SET name=?, variety=?, days_to_harvest=?, notes=? WHERE id=?",
        (crop.name, crop.variety, crop.days_to_harvest, crop.notes, crop_id)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM crops WHERE id=?", (crop_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Crop not found")
    return dict(row)

@app.delete("/api/crops/{crop_id}", status_code=204)
def delete_crop(crop_id: int):
    conn = get_db()
    try:
        conn.execute("DELETE FROM crops WHERE id=?", (crop_id,))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=409, detail="Crop is referenced by one or more plants")
    conn.close()

@app.post("/api/crops/bulk", status_code=201)
def bulk_import_crops(crops: list[CropIn]):
    conn = get_db()
    created = 0
    skipped = 0
    for crop in crops:
        existing = conn.execute(
            "SELECT id FROM crops WHERE name=? AND (variety=? OR (variety IS NULL AND ? IS NULL))",
            (crop.name, crop.variety, crop.variety)
        ).fetchone()
        if existing:
            skipped += 1
        else:
            conn.execute(
                "INSERT INTO crops (name, variety, days_to_harvest, notes) VALUES (?,?,?,?)",
                (crop.name, crop.variety, crop.days_to_harvest, crop.notes)
            )
            created += 1
    conn.commit()
    conn.close()
    return {"created": created, "skipped": skipped}

# ---------------------------------------------------------------------------
# Plants
# ---------------------------------------------------------------------------

@app.get("/api/plants")
def list_plants(bed_id: Optional[int] = None, container_id: Optional[int] = None):
    conn = get_db()
    if bed_id:
        rows = conn.execute("SELECT * FROM plants WHERE bed_id=? ORDER BY row, col", (bed_id,)).fetchall()
    elif container_id:
        rows = conn.execute("SELECT * FROM plants WHERE container_id=? ORDER BY name", (container_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM plants ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/plants/{plant_id}")
def get_plant(plant_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM plants WHERE id=?", (plant_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Plant not found")
    return dict(row)

@app.post("/api/plants", status_code=201)
def create_plant(plant: PlantIn):
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO plants (crop_id, name, variety, bed_id, row, col, container_id, planted, notes) VALUES (?,?,?,?,?,?,?,?,?)",
            (plant.crop_id, plant.name, plant.variety, plant.bed_id, plant.row, plant.col, plant.container_id, plant.planted, plant.notes)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=409, detail="That bed square is already occupied")
    row = conn.execute("SELECT * FROM plants WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)

@app.put("/api/plants/{plant_id}")
def update_plant(plant_id: int, plant: PlantIn):
    conn = get_db()
    try:
        conn.execute(
            "UPDATE plants SET crop_id=?, name=?, variety=?, bed_id=?, row=?, col=?, container_id=?, planted=?, notes=? WHERE id=?",
            (plant.crop_id, plant.name, plant.variety, plant.bed_id, plant.row, plant.col, plant.container_id, plant.planted, plant.notes, plant_id)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=409, detail="That bed square is already occupied")
    row = conn.execute("SELECT * FROM plants WHERE id=?", (plant_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Plant not found")
    return dict(row)

@app.delete("/api/plants/{plant_id}", status_code=204)
def delete_plant(plant_id: int):
    conn = get_db()
    conn.execute("DELETE FROM plants WHERE id=?", (plant_id,))
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# Waterings
# ---------------------------------------------------------------------------

@app.get("/api/waterings")
def list_waterings(plant_id: Optional[int] = None):
    conn = get_db()
    if plant_id:
        rows = conn.execute(
            "SELECT * FROM waterings WHERE plant_id=? ORDER BY watered DESC", (plant_id,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM waterings ORDER BY watered DESC LIMIT 50").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/waterings", status_code=201)
def log_watering(w: WateringIn):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO waterings (plant_id, notes) VALUES (?,?)", (w.plant_id, w.notes)
    )
    conn.execute(
        """UPDATE schedules
           SET last_watered = datetime('now'),
               next_due     = datetime('now', '+' || interval_days || ' days')
           WHERE plant_id = ?""",
        (w.plant_id,)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM waterings WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)

# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------

@app.get("/api/schedules")
def list_schedules():
    conn = get_db()
    rows = conn.execute("""
        SELECT s.*, p.name as plant_name
        FROM schedules s
        JOIN plants p ON p.id = s.plant_id
        ORDER BY s.next_due ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/schedules", status_code=201)
def create_schedule(s: ScheduleIn):
    conn = get_db()
    last = s.last_watered or datetime.now().isoformat()
    try:
        cur = conn.execute(
            "INSERT INTO schedules (plant_id, interval_days, last_watered, next_due) VALUES (?,?,?,datetime(?,'+' || ? || ' days'))",
            (s.plant_id, s.interval_days, last, last, s.interval_days)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=409, detail="A schedule already exists for this plant")
    row = conn.execute("SELECT * FROM schedules WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)

@app.put("/api/schedules/{schedule_id}")
def update_schedule(schedule_id: int, s: ScheduleIn):
    conn = get_db()
    conn.execute(
        "UPDATE schedules SET interval_days=?, last_watered=?, next_due=datetime(last_watered, '+' || ? || ' days') WHERE id=?",
        (s.interval_days, s.last_watered, s.interval_days, schedule_id)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM schedules WHERE id=?", (schedule_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return dict(row)

@app.delete("/api/schedules/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: int):
    conn = get_db()
    conn.execute("DELETE FROM schedules WHERE id=?", (schedule_id,))
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------

@app.get("/api/journal")
def list_journal():
    conn = get_db()
    rows = conn.execute("SELECT * FROM journal ORDER BY created DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/journal", status_code=201)
def create_entry(entry: JournalIn):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO journal (title, body, tags) VALUES (?,?,?)",
        (entry.title, entry.body, entry.tags)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM journal WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)

@app.put("/api/journal/{entry_id}")
def update_entry(entry_id: int, entry: JournalIn):
    conn = get_db()
    conn.execute(
        "UPDATE journal SET title=?, body=?, tags=? WHERE id=?",
        (entry.title, entry.body, entry.tags, entry_id)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM journal WHERE id=?", (entry_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Entry not found")
    return dict(row)

@app.delete("/api/journal/{entry_id}", status_code=204)
def delete_entry(entry_id: int):
    conn = get_db()
    conn.execute("DELETE FROM journal WHERE id=?", (entry_id,))
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# Weather proxy (NWS, no API key required)
# ---------------------------------------------------------------------------

WEATHER_STATION_DEFAULT = os.getenv("WEATHER_STATION", "KROG")
WEATHER_LAT_DEFAULT     = os.getenv("WEATHER_LAT", "36.3726")
WEATHER_LON_DEFAULT     = os.getenv("WEATHER_LON", "-94.1069")

def nws_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "root-cause-analysis/1.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read())

def get_setting(conn, key, default):
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default

@app.get("/api/weather")
def get_weather():
    conn = get_db()
    station = get_setting(conn, "weather_station", WEATHER_STATION_DEFAULT)
    lat     = get_setting(conn, "weather_lat",     WEATHER_LAT_DEFAULT)
    lon     = get_setting(conn, "weather_lon",     WEATHER_LON_DEFAULT)
    conn.close()
    try:
        # Current conditions from station
        obs_data = nws_get(f"https://api.weather.gov/stations/{station}/observations?limit=1")
        latest = obs_data["features"][0]["properties"] if obs_data.get("features") else {}
        temp_c = latest.get("temperature", {}).get("value")
        temp_f = round(temp_c * 9 / 5 + 32, 1) if temp_c is not None else None
        description = latest.get("textDescription", "")

        # Wind — NWS returns km/h, convert to mph
        def kmh_to_mph(v):
            return round(v * 0.621371, 1) if v is not None else None

        wind_speed_kmh = latest.get("windSpeed", {}).get("value")
        wind_gust_kmh  = latest.get("windGust", {}).get("value")
        wind_dir_deg   = latest.get("windDirection", {}).get("value")

        def deg_to_cardinal(d):
            if d is None: return None
            dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
                    "S","SSW","SW","WSW","W","WNW","NW","NNW"]
            return dirs[round(d / 22.5) % 16]

        # Precipitation from Open-Meteo (no API key, no rounding bug)
        from datetime import timedelta
        precip_url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&daily=precipitation_sum"
            f"&precipitation_unit=inch"
            f"&timezone=America%2FChicago"
            f"&past_days=7&forecast_days=1"
        )
        precip_data = nws_get(precip_url)
        times   = precip_data["daily"]["time"]
        amounts = precip_data["daily"]["precipitation_sum"]
        # today + past 7 = 8 entries; keep last 7
        pairs = list(zip(times, amounts))[-7:]
        rainfall = [
            {"date": d, "inches": round(a or 0, 2)}
            for d, a in pairs
        ]

        # 7-day temp range from recent observations
        recent_obs = nws_get(f"https://api.weather.gov/stations/{station}/observations?limit=168")
        temps = []
        for f in recent_obs.get("features", []):
            v = f["properties"].get("temperature", {}).get("value")
            if v is not None:
                temps.append(round(v * 9 / 5 + 32, 1))

        return {
            "station": station,
            "current": {
                "temp_f": temp_f,
                "description": description,
                "wind_speed_mph": kmh_to_mph(wind_speed_kmh),
                "wind_gust_mph":  kmh_to_mph(wind_gust_kmh),
                "wind_dir_deg":   wind_dir_deg,
                "wind_dir":       deg_to_cardinal(wind_dir_deg),
            },
            "temp_high": max(temps) if temps else None,
            "temp_low":  min(temps) if temps else None,
            "rainfall":  rainfall,
        }

    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Weather fetch failed: {e}")

# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@app.get("/api/tasks")
def list_tasks(include_done: bool = False, done_only: bool = False):
    conn = get_db()
    if done_only:
        rows = conn.execute("SELECT * FROM tasks WHERE done=1 ORDER BY done_at DESC").fetchall()
    elif include_done:
        rows = conn.execute("SELECT * FROM tasks ORDER BY done ASC, due_date ASC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM tasks WHERE done=0 ORDER BY due_date ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/tasks", status_code=201)
def create_task(task: TaskIn):
    if task.type not in TASK_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid task type. Must be one of: {', '.join(TASK_TYPES)}")
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO tasks (type, title, due_date, notes) VALUES (?,?,?,?)",
        (task.type, task.title, task.due_date, task.notes)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)

@app.patch("/api/tasks/{task_id}/done")
def mark_task_done(task_id: int, body: TaskDone):
    conn = get_db()
    done_at = datetime.now().isoformat() if body.done else None
    conn.execute(
        "UPDATE tasks SET done=?, done_at=? WHERE id=?",
        (1 if body.done else 0, done_at, task_id)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return dict(row)

@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    conn = get_db()
    conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()

@app.post("/api/tasks/sync")
def sync_weather_tasks():
    """
    Examines the last 7 days of rainfall and upserts a watering task if needed.
    Rules:
      - Total >= 1.0" in last 7 days → delete any open watering task, no new one needed
      - Total < 1.0"                 → upsert a watering task due 3 days after last rain day
                                       (or 3 days from today if no rain at all)
    """
    from datetime import date, timedelta

    # Fetch rainfall from Open-Meteo
    conn = get_db()
    lat = get_setting(conn, "weather_lat", WEATHER_LAT_DEFAULT)
    lon = get_setting(conn, "weather_lon", WEATHER_LON_DEFAULT)
    conn.close()

    try:
        precip_url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&daily=precipitation_sum"
            f"&precipitation_unit=inch"
            f"&timezone=America%2FChicago"
            f"&past_days=7&forecast_days=1"
        )
        precip_data = nws_get(precip_url)
        times   = precip_data["daily"]["time"]
        amounts = precip_data["daily"]["precipitation_sum"]
        pairs   = list(zip(times, amounts))[-7:]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Weather fetch failed: {e}")

    total_rain   = sum(a or 0 for _, a in pairs)
    today_str    = date.today().isoformat()

    conn = get_db()

    if total_rain >= 1.0:
        # Enough rain — close any open auto watering task
        conn.execute(
            "UPDATE tasks SET done=1, done_at=?, notes='Closed automatically — sufficient rainfall' "
            "WHERE type='water' AND done=0 AND title='Water garden'",
            (datetime.now().isoformat(),)
        )
        conn.commit()
        conn.close()
        return {"action": "closed", "total_rain_inches": round(total_rain, 2)}

    # Find last day with any rain
    last_rain_date = None
    for day, amt in reversed(pairs):
        if (amt or 0) > 0:
            last_rain_date = day
            break

    if last_rain_date:
        base = datetime.strptime(last_rain_date, "%Y-%m-%d").date()
    else:
        base = date.today()

    due = (base + timedelta(days=3)).isoformat()

    # Upsert — update existing open task or create new one
    existing = conn.execute(
        "SELECT id FROM tasks WHERE type='water' AND title='Water garden' AND done=0"
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE tasks SET due_date=?, notes=? WHERE id=?",
            (due, f"Total rain last 7 days: {total_rain:.2f}\". Last rain: {last_rain_date or 'none'}.", existing["id"])
        )
        action = "updated"
    else:
        conn.execute(
            "INSERT INTO tasks (type, title, due_date, notes) VALUES ('water','Water garden',?,?)",
            (due, f"Total rain last 7 days: {total_rain:.2f}\". Last rain: {last_rain_date or 'none'}.")
        )
        action = "created"

    conn.commit()
    conn.close()
    return {"action": action, "due_date": due, "total_rain_inches": round(total_rain, 2), "last_rain": last_rain_date}

# ---------------------------------------------------------------------------
# Growing zone lookup
# ---------------------------------------------------------------------------

@app.get("/api/growing-zone")
def lookup_growing_zone():
    conn = get_db()
    lat = get_setting(conn, "weather_lat", WEATHER_LAT_DEFAULT)
    lon = get_setting(conn, "weather_lon", WEATHER_LON_DEFAULT)
    conn.close()

    try:
        # Step 1: NWS points -> get forecast zone which includes ZIP-level info
        points = nws_get(f"https://api.weather.gov/points/{lat},{lon}")
        props = points.get("properties", {})

        # NWS returns a relativeLocation with city/state but not ZIP
        # Use the forecastZone URL to get county/state, then build ZIP lookup
        # Better: use the county FIPS from relativeLocation to hit phzmapi by zip
        # Simplest: reverse geocode with nominatim (OSM, free, no key)
        city  = props.get("relativeLocation", {}).get("properties", {}).get("city", "")
        state = props.get("relativeLocation", {}).get("properties", {}).get("state", "")

        # Step 2: Nominatim reverse geocode to get ZIP
        nom_url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
        nom_req = urllib.request.Request(nom_url, headers={"User-Agent": "root-cause-analysis/1.0"})
        with urllib.request.urlopen(nom_req, timeout=8) as resp:
            nom_data = json.loads(resp.read())

        zipcode = nom_data.get("address", {}).get("postcode", "").split("-")[0]
        if not zipcode:
            raise HTTPException(status_code=404, detail="Could not determine ZIP code from coordinates")

        # Step 3: phzmapi.org lookup by ZIP
        zone_req = urllib.request.Request(
            f"https://phzmapi.org/{zipcode}.json",
            headers={"User-Agent": "root-cause-analysis/1.0"}
        )
        with urllib.request.urlopen(zone_req, timeout=8) as resp:
            zone_data = json.loads(resp.read())

        zone = zone_data.get("zone", "")
        temp_range = zone_data.get("temperature_range", "")

        return {
            "zone": zone,
            "temperature_range": temp_range,
            "zipcode": zipcode,
            "city": city,
            "state": state,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Zone lookup failed: {e}")

# ---------------------------------------------------------------------------
# Frost date detection
# ---------------------------------------------------------------------------

@app.get("/api/frost-dates")
def detect_frost_dates():
    conn = get_db()
    lat = get_setting(conn, "weather_lat", WEATHER_LAT_DEFAULT)
    lon = get_setting(conn, "weather_lon", WEATHER_LON_DEFAULT)
    conn.close()

    from datetime import date, timedelta

    # Pull 10 years of daily min temps from Open-Meteo historical API
    end_year   = date.today().year - 1          # last full year
    start_year = end_year - 9                   # 10 years back
    start_date = f"{start_year}-01-01"
    end_date   = f"{end_year}-12-31"

    try:
        url = (
            f"https://archive-api.open-meteo.com/v1/archive"
            f"?latitude={lat}&longitude={lon}"
            f"&start_date={start_date}&end_date={end_date}"
            f"&daily=temperature_2m_min"
            f"&temperature_unit=fahrenheit"
            f"&timezone=America%2FChicago"
        )
        data = nws_get(url)
        times = data["daily"]["time"]
        temps = data["daily"]["temperature_2m_min"]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Historical data fetch failed: {e}")

    # Group freeze days by year
    # Last spring frost = last day in Jan-Jun where min <= 32
    # First fall frost  = first day in Jul-Dec where min <= 32
    spring_frosts = {}  # year -> latest freeze date in spring
    fall_frosts   = {}  # year -> earliest freeze date in fall

    for day_str, temp in zip(times, temps):
        if temp is None:
            continue
        d = datetime.strptime(day_str, "%Y-%m-%d")
        year  = d.year
        month = d.month

        if temp <= 32.0:
            if 1 <= month <= 6:
                # Spring freeze — keep the latest one
                if year not in spring_frosts or d > spring_frosts[year]:
                    spring_frosts[year] = d
            elif 7 <= month <= 12:
                # Fall freeze — keep the earliest one
                if year not in fall_frosts or d < fall_frosts[year]:
                    fall_frosts[year] = d

    def avg_day_of_year(date_dict):
        if not date_dict:
            return None
        doys = [d.timetuple().tm_yday for d in date_dict.values()]
        avg_doy = round(sum(doys) / len(doys))
        # Convert average DOY back to a month/day using a non-leap year
        ref = datetime(2001, 1, 1) + timedelta(days=avg_doy - 1)
        return ref.strftime("%m-%d")

    last_spring = avg_day_of_year(spring_frosts)
    first_fall  = avg_day_of_year(fall_frosts)

    # Format as current-year dates for the date picker
    current_year = date.today().year
    last_spring_date  = f"{current_year}-{last_spring}" if last_spring else None
    first_fall_date   = f"{current_year}-{first_fall}"  if first_fall  else None

    return {
        "last_spring_frost": last_spring_date,
        "first_fall_frost":  first_fall_date,
        "years_analyzed":    len(spring_frosts),
        "spring_samples":    len(spring_frosts),
        "fall_samples":      len(fall_frosts),
    }

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class SettingsIn(BaseModel):
    weather_station: str
    weather_lat: str
    weather_lon: str
    garden_year: Optional[str] = None
    spring_season: Optional[str] = None
    fall_season: Optional[str] = None
    growing_zone: Optional[str] = None
    last_frost: Optional[str] = None
    first_frost: Optional[str] = None

@app.get("/api/settings")
def get_settings():
    conn = get_db()
    result = {
        "weather_station": get_setting(conn, "weather_station", WEATHER_STATION_DEFAULT),
        "weather_lat":     get_setting(conn, "weather_lat",     WEATHER_LAT_DEFAULT),
        "weather_lon":     get_setting(conn, "weather_lon",     WEATHER_LON_DEFAULT),
        "garden_year":     get_setting(conn, "garden_year",     ""),
        "spring_season":   get_setting(conn, "spring_season",   ""),
        "fall_season":     get_setting(conn, "fall_season",     ""),
        "growing_zone":    get_setting(conn, "growing_zone",    ""),
        "last_frost":      get_setting(conn, "last_frost",      ""),
        "first_frost":     get_setting(conn, "first_frost",     ""),
    }
    conn.close()
    return result

@app.put("/api/settings")
def update_settings(s: SettingsIn):
    conn = get_db()
    pairs = [
        ("weather_station", s.weather_station),
        ("weather_lat",     s.weather_lat),
        ("weather_lon",     s.weather_lon),
        ("garden_year",     s.garden_year or ""),
        ("spring_season",   s.spring_season or ""),
        ("fall_season",     s.fall_season or ""),
        ("growing_zone",    s.growing_zone or ""),
        ("last_frost",      s.last_frost or ""),
        ("first_frost",     s.first_frost or ""),
    ]
    for key, val in pairs:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, val)
        )
    conn.commit()
    conn.close()
    return dict(pairs)

# ---------------------------------------------------------------------------
# Serve frontend
# ---------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def dashboard():
    return FileResponse("static/index.html")

@app.get("/manage")
def manage():
    return FileResponse("static/manage.html")

@app.get("/settings")
def settings_page():
    return FileResponse("static/settings.html")

@app.get("/tasks")
def tasks_page():
    return FileResponse("static/tasks.html")

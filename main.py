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
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            name                 TEXT NOT NULL,
            variety              TEXT,
            days_to_harvest      INTEGER,
            weeks_to_transplant  INTEGER,
            succession_weeks     INTEGER,
            succession_count     INTEGER,
            notes                TEXT,
            created              TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS seeds (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            crop_id         INTEGER REFERENCES crops(id) ON DELETE SET NULL,
            variety         TEXT,
            quantity        REAL NOT NULL DEFAULT 1,
            unit            TEXT NOT NULL DEFAULT 'packet',
            seed_lot        INTEGER,
            source          TEXT,
            notes           TEXT,
            created         TEXT DEFAULT (datetime('now'))
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

def migrate_db():
    """Apply any schema changes to an existing DB without wiping data."""
    conn = get_db()
    
    # Helper to check if a column exists
    def has_column(table, column):
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return any(r["name"] == column for r in rows)
    
    # Helper to check if a table exists
    def has_table(table):
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        return row is not None

    migrations = []

    # crops table additions
    if has_table("crops"):
        if not has_column("crops", "weeks_to_transplant"):
            migrations.append("ALTER TABLE crops ADD COLUMN weeks_to_transplant INTEGER")
        if not has_column("crops", "succession_weeks"):
            migrations.append("ALTER TABLE crops ADD COLUMN succession_weeks INTEGER")
        if not has_column("crops", "succession_count"):
            migrations.append("ALTER TABLE crops ADD COLUMN succession_count INTEGER")

    # seeds table additions
    if has_table("seeds"):
        if not has_column("seeds", "variety"):
            migrations.append("ALTER TABLE seeds ADD COLUMN variety TEXT")
        if not has_column("seeds", "seed_lot"):
            migrations.append("ALTER TABLE seeds ADD COLUMN seed_lot INTEGER")
        # rename year_purchased to seed_lot if old column exists
        if has_column("seeds", "year_purchased") and not has_column("seeds", "seed_lot"):
            migrations.append("ALTER TABLE seeds RENAME COLUMN year_purchased TO seed_lot")
        if has_column("seeds", "year_harvested"):
            pass  # leave it, no harm in keeping old data

    # plants table
    if has_table("plants"):
        if not has_column("plants", "crop_id"):
            migrations.append("ALTER TABLE plants ADD COLUMN crop_id INTEGER REFERENCES crops(id) ON DELETE SET NULL")

    # settings table — created fresh if missing, no migration needed
    # tasks table — created fresh if missing, no migration needed

    for sql in migrations:
        try:
            conn.execute(sql)
            print(f"Migration applied: {sql}")
        except Exception as e:
            print(f"Migration skipped ({e}): {sql}")

    conn.commit()
    conn.close()

def seed_crops_from_file():
    """
    On every startup, upsert crops from seed_crops.json.
    New entries are inserted, existing ones (matched on name+variety) are left alone.
    Safe to run repeatedly — never overwrites user data or removes crops.
    """
    import json as _json
    import os as _os
    seed_file = _os.path.join(_os.path.dirname(__file__), "seed_crops.json")
    if not _os.path.exists(seed_file):
        return
    with open(seed_file) as f:
        crops_data = _json.load(f)
    conn = get_db()
    created = 0
    for c in crops_data:
        existing = conn.execute(
            "SELECT id FROM crops WHERE name=? AND (variety=? OR (variety IS NULL AND ? IS NULL))",
            (c.get("name"), c.get("variety"), c.get("variety"))
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO crops (name, variety, days_to_harvest, weeks_to_transplant, succession_weeks, succession_count, notes) VALUES (?,?,?,?,?,?,?)",
                (c.get("name"), c.get("variety"), c.get("days_to_harvest"), c.get("weeks_to_transplant"), c.get("succession_weeks"), c.get("succession_count"), c.get("notes"))
            )
            created += 1
    conn.commit()
    conn.close()
    if created:
        print(f"seed_crops.json: added {created} new crops")


init_db()
migrate_db()
seed_crops_from_file()

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
    weeks_to_transplant: Optional[int] = None
    succession_weeks: Optional[int] = None
    succession_count: Optional[int] = None
    notes: Optional[str] = None

class SeedIn(BaseModel):
    crop_id: Optional[int] = None
    variety: Optional[str] = None
    quantity: float = 1
    unit: str = "packet"
    seed_lot: Optional[int] = None
    source: Optional[str] = None
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
        "INSERT INTO crops (name, variety, days_to_harvest, weeks_to_transplant, succession_weeks, succession_count, notes) VALUES (?,?,?,?,?,?,?)",
        (crop.name, crop.variety, crop.days_to_harvest, crop.weeks_to_transplant, crop.succession_weeks, crop.succession_count, crop.notes)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM crops WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)

@app.put("/api/crops/{crop_id}")
def update_crop(crop_id: int, crop: CropIn):
    conn = get_db()
    conn.execute(
        "UPDATE crops SET name=?, variety=?, days_to_harvest=?, weeks_to_transplant=?, succession_weeks=?, succession_count=?, notes=? WHERE id=?",
        (crop.name, crop.variety, crop.days_to_harvest, crop.weeks_to_transplant, crop.succession_weeks, crop.succession_count, crop.notes, crop_id)
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
                "INSERT INTO crops (name, variety, days_to_harvest, weeks_to_transplant, succession_weeks, succession_count, notes) VALUES (?,?,?,?,?,?,?)",
                (crop.name, crop.variety, crop.days_to_harvest, crop.weeks_to_transplant, crop.succession_weeks, crop.succession_count, crop.notes)
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
# Seeds
# ---------------------------------------------------------------------------

SEED_UNITS = ["packet","seeds","corms","bulbs","cloves","crowns","sets","plants","tubers","oz","g","lb"]

# Default viability in years by crop name keyword
VIABILITY_DEFAULTS = {
    "onion":1,"leek":1,"chive":1,
    "pepper":2,"parsnip":2,"corn":2,"maize":2,
    "bean":3,"pea":3,"sweet corn":3,
    "tomato":4,"basil":4,"beet":4,"beetroot":4,"carrot":4,"broccoli":4,"cabbage":4,"kale":4,"chard":4,"spinach":4,
    "cucumber":5,"melon":5,"squash":5,"pumpkin":5,"zucchini":5,"courgette":5,"lettuce":5,"celery":5,"celeriac":5,
}

# Default weeks to transplant by crop name keyword
TRANSPLANT_WEEKS_DEFAULTS = {
    "pepper":10,"tomato":7,"eggplant":10,"aubergine":10,
    "broccoli":5,"cabbage":5,"cauliflower":5,"kale":5,"chard":4,"lettuce":4,
    "celery":10,"celeriac":10,"leek":10,"onion":8,
    "cucumber":3,"squash":3,"pumpkin":3,"melon":3,"zucchini":3,"courgette":3,
    "basil":4,
}

def get_viability(crop_name):
    name = (crop_name or "").lower()
    for k, v in VIABILITY_DEFAULTS.items():
        if k in name:
            return v
    return 3  # conservative default

def get_transplant_weeks(crop_name, override=None):
    if override is not None:
        return override
    name = (crop_name or "").lower()
    for k, v in TRANSPLANT_WEEKS_DEFAULTS.items():
        if k in name:
            return v
    return 0  # direct sow by default

@app.get("/api/seeds")
def list_seeds():
    conn = get_db()
    rows = conn.execute("""
        SELECT s.*, c.name as crop_name,
               COALESCE(s.variety, c.variety) as display_variety,
               c.days_to_harvest, c.weeks_to_transplant
        FROM seeds s
        LEFT JOIN crops c ON c.id = s.crop_id
        ORDER BY c.name, s.created
    """).fetchall()
    conn.close()
    current_year = datetime.now().year
    result = []
    for r in rows:
        d = dict(r)
        viability = get_viability(d.get("crop_name",""))
        seed_year = d.get("seed_lot")
        d["viability_years"] = viability
        d["age_years"] = (current_year - seed_year) if seed_year else None
        d["viable"] = (current_year - seed_year) <= viability if seed_year else None
        result.append(d)
    return result

@app.post("/api/seeds", status_code=201)
def create_seed(seed: SeedIn):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO seeds (crop_id, variety, quantity, unit, seed_lot, source, notes) VALUES (?,?,?,?,?,?,?)",
        (seed.crop_id, seed.variety, seed.quantity, seed.unit, seed.seed_lot, seed.source, seed.notes)
    )
    conn.commit()
    row = conn.execute("""
        SELECT s.*, c.name as crop_name FROM seeds s
        LEFT JOIN crops c ON c.id=s.crop_id WHERE s.id=?
    """, (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)

@app.put("/api/seeds/{seed_id}")
def update_seed(seed_id: int, seed: SeedIn):
    conn = get_db()
    conn.execute(
        "UPDATE seeds SET crop_id=?, variety=?, quantity=?, unit=?, seed_lot=?, source=?, notes=? WHERE id=?",
        (seed.crop_id, seed.variety, seed.quantity, seed.unit, seed.seed_lot, seed.source, seed.notes, seed_id)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM seeds WHERE id=?", (seed_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Seed not found")
    return dict(row)

@app.delete("/api/seeds/{seed_id}", status_code=204)
def delete_seed(seed_id: int):
    conn = get_db()
    conn.execute("DELETE FROM seeds WHERE id=?", (seed_id,))
    conn.commit()
    conn.close()

@app.get("/api/seeds/plan")
def seed_plan():
    """
    Returns a planting calendar for all seeds in inventory,
    calculated from frost dates stored in settings.
    Both spring and fall plans are returned.
    """
    from datetime import date, timedelta

    conn = get_db()
    last_spring = get_setting(conn, "last_frost", "")
    first_fall  = get_setting(conn, "first_frost", "")

    seeds = conn.execute("""
        SELECT s.*, c.name as crop_name,
               COALESCE(s.variety, c.variety) as display_variety,
               c.days_to_harvest, c.weeks_to_transplant
        FROM seeds s
        LEFT JOIN crops c ON c.id = s.crop_id
        ORDER BY c.name
    """).fetchall()
    conn.close()

    current_year = date.today().year

    def calc_dates(frost_date_str, season):
        if not frost_date_str:
            return None
        try:
            frost = datetime.strptime(frost_date_str, "%Y-%m-%d").date()
            # Use current year's frost date
            frost = frost.replace(year=current_year)
        except:
            return None

        plan = []
        for s in seeds:
            d = dict(s)
            crop_name = d.get("crop_name") or "Unknown"
            dth = d.get("days_to_harvest")
            if not dth:
                continue

            weeks = get_transplant_weeks(crop_name, d.get("weeks_to_transplant"))
            viability = get_viability(crop_name)
            seed_year = d.get("seed_lot")
            viable = (current_year - seed_year) <= viability if seed_year else None
            age = (current_year - seed_year) if seed_year else None

            if season == "spring":
                # Work backwards from last spring frost
                sow_outdoors = frost - timedelta(days=dth)
                sow_indoors  = sow_outdoors - timedelta(weeks=weeks) if weeks else None
                transplant   = frost if weeks else None
            else:
                # Work backwards from first fall frost
                sow_outdoors = frost - timedelta(days=dth)
                sow_indoors  = sow_outdoors - timedelta(weeks=weeks) if weeks else None
                transplant   = frost if weeks else None

            plan.append({
                "seed_id":       d["id"],
                "crop_name":     crop_name,
                "variety":       d.get("display_variety"),
                "quantity":      d["quantity"],
                "unit":          d["unit"],
                "days_to_harvest": dth,
                "weeks_to_transplant": weeks,
                "sow_indoors":   sow_indoors.isoformat() if sow_indoors else None,
                "sow_outdoors":  sow_outdoors.isoformat(),
                "transplant":    transplant.isoformat() if transplant else None,
                "harvest_from":  frost.isoformat(),
                "viable":        viable,
                "age_years":     age,
                "viability_years": viability,
            })

        plan.sort(key=lambda x: x["sow_indoors"] or x["sow_outdoors"])
        return plan

    return {
        "spring": calc_dates(last_spring, "spring"),
        "fall":   calc_dates(first_fall,  "fall"),
        "last_spring_frost": last_spring,
        "first_fall_frost":  first_fall,
    }

# ---------------------------------------------------------------------------
# Seed plan task sync
# ---------------------------------------------------------------------------

@app.post("/api/tasks/seed-plan-sync")
def seed_plan_sync():
    """
    For each unique crop/variety in seed inventory, calculate sow indoors,
    sow outdoors, and transplant dates for both spring and fall seasons,
    then upsert tasks. Skips seeds with no days_to_harvest on the crop.
    Closes tasks whose dates have passed.
    """
    from datetime import date, timedelta

    conn = get_db()
    last_spring = get_setting(conn, "last_frost", "")
    first_fall  = get_setting(conn, "first_frost", "")

    if not last_spring and not first_fall:
        conn.close()
        return {"message": "No frost dates configured — go to Settings → Garden Planning"}

    # Get unique crop/variety combos from inventory
    seeds = conn.execute("""
        SELECT DISTINCT
            COALESCE(s.variety, c.variety) as variety,
            c.name as crop_name,
            c.days_to_harvest,
            c.weeks_to_transplant,
            c.succession_weeks,
            c.succession_count
        FROM seeds s
        LEFT JOIN crops c ON c.id = s.crop_id
        WHERE c.days_to_harvest IS NOT NULL
        ORDER BY c.name, variety
    """).fetchall()

    current_year = date.today().year
    today = date.today()
    created = 0
    updated = 0
    closed  = 0

    def upsert_task(task_type, title, due_date_str):
        nonlocal created, updated, closed
        due = datetime.strptime(due_date_str, "%Y-%m-%d").date()

        # Close if date has passed
        if due < today:
            rows = conn.execute(
                "SELECT id FROM tasks WHERE type=? AND title=? AND done=0",
                (task_type, title)
            ).fetchall()
            for r in rows:
                conn.execute(
                    "UPDATE tasks SET done=1, done_at=? WHERE id=?",
                    (datetime.now().isoformat(), r["id"])
                )
                closed += 1
            return

        existing = conn.execute(
            "SELECT id FROM tasks WHERE type=? AND title=? AND done=0",
            (task_type, title)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE tasks SET due_date=? WHERE id=?",
                (due_date_str, existing["id"])
            )
            updated += 1
        else:
            conn.execute(
                "INSERT INTO tasks (type, title, due_date, notes) VALUES (?,?,?,?)",
                (task_type, title, due_date_str, "Auto-generated from seed inventory")
            )
            created += 1

    def calc_and_upsert(frost_str, season_label):
        if not frost_str:
            return
        try:
            frost = datetime.strptime(frost_str, "%Y-%m-%d").date().replace(year=current_year)
        except:
            return

        for s in seeds:
            crop_name    = s["crop_name"] or "Unknown"
            variety      = s["variety"] or ""
            dth          = s["days_to_harvest"]
            weeks        = get_transplant_weeks(crop_name, s["weeks_to_transplant"])
            succ_weeks   = s["succession_weeks"]
            succ_count   = s["succession_count"] or 1
            base_label   = f"{crop_name}{' — ' + variety if variety else ''} ({season_label})"

            base_sow_outdoors = frost - timedelta(days=dth)
            base_sow_indoors  = base_sow_outdoors - timedelta(weeks=weeks) if weeks else None
            base_transplant   = frost if weeks else None

            # Generate succession sow dates
            count = succ_count if succ_weeks else 1
            for i in range(count):
                offset = timedelta(weeks=succ_weeks * i) if succ_weeks else timedelta(0)
                label  = f"{base_label} #{i+1}" if count > 1 else base_label

                sow_outdoors = base_sow_outdoors + offset
                sow_indoors  = (base_sow_indoors + offset) if base_sow_indoors else None
                transplant   = (base_transplant + offset) if base_transplant else None

                if sow_indoors:
                    upsert_task("sow_indoors", f"Sow indoors: {label}", sow_indoors.isoformat())
                upsert_task("sow_outdoors", f"Sow outdoors: {label}", sow_outdoors.isoformat())
                if transplant:
                    upsert_task("transplant", f"Transplant: {label}", transplant.isoformat())

    calc_and_upsert(last_spring, "Spring")
    calc_and_upsert(first_fall,  "Fall")

    conn.commit()
    conn.close()
    return {"created": created, "updated": updated, "closed": closed}

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

@app.get("/seeds")
def seeds_page():
    return FileResponse("static/seeds.html")

@app.get("/tasks")
def tasks_page():
    return FileResponse("static/tasks.html")

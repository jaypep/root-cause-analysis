from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, model_validator
from typing import Optional
import sqlite3
import os
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
# Serve frontend
# ---------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def dashboard():
    return FileResponse("static/index.html")

@app.get("/manage")
def manage():
    return FileResponse("static/manage.html")

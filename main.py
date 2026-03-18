from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
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
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS plants (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT NOT NULL,
            variety   TEXT,
            location  TEXT,
            planted   TEXT,
            notes     TEXT,
            created   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS waterings (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id  INTEGER REFERENCES plants(id) ON DELETE CASCADE,
            watered   TEXT DEFAULT (datetime('now')),
            notes     TEXT
        );

        CREATE TABLE IF NOT EXISTS schedules (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id       INTEGER REFERENCES plants(id) ON DELETE CASCADE,
            interval_days  INTEGER NOT NULL,
            last_watered   TEXT,
            next_due       TEXT
        );

        CREATE TABLE IF NOT EXISTS sensor_readings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor      TEXT NOT NULL,
            value       REAL NOT NULL,
            unit        TEXT,
            recorded    TEXT DEFAULT (datetime('now'))
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

class PlantIn(BaseModel):
    name: str
    variety: Optional[str] = None
    location: Optional[str] = None
    planted: Optional[str] = None
    notes: Optional[str] = None

class WateringIn(BaseModel):
    plant_id: int
    notes: Optional[str] = None

class ScheduleIn(BaseModel):
    plant_id: int
    interval_days: int
    last_watered: Optional[str] = None

class SensorIn(BaseModel):
    sensor: str
    value: float
    unit: Optional[str] = None

class JournalIn(BaseModel):
    title: Optional[str] = None
    body: str
    tags: Optional[str] = None

# ---------------------------------------------------------------------------
# Plants
# ---------------------------------------------------------------------------

@app.get("/api/plants")
def list_plants():
    conn = get_db()
    rows = conn.execute("SELECT * FROM plants ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/plants", status_code=201)
def create_plant(plant: PlantIn):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO plants (name, variety, location, planted, notes) VALUES (?,?,?,?,?)",
        (plant.name, plant.variety, plant.location, plant.planted, plant.notes)
    )
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute("SELECT * FROM plants WHERE id=?", (new_id,)).fetchone()
    conn.close()
    return dict(row)

@app.put("/api/plants/{plant_id}")
def update_plant(plant_id: int, plant: PlantIn):
    conn = get_db()
    conn.execute(
        "UPDATE plants SET name=?, variety=?, location=?, planted=?, notes=? WHERE id=?",
        (plant.name, plant.variety, plant.location, plant.planted, plant.notes, plant_id)
    )
    conn.commit()
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
        "INSERT INTO waterings (plant_id, notes) VALUES (?,?)",
        (w.plant_id, w.notes)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM waterings WHERE id=?", (cur.lastrowid,)).fetchone()
    # bump the schedule's last_watered if one exists
    conn.execute(
        "UPDATE schedules SET last_watered=datetime('now'), next_due=datetime('now', '+' || interval_days || ' days') WHERE plant_id=?",
        (w.plant_id,)
    )
    conn.commit()
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
    cur = conn.execute(
        "INSERT INTO schedules (plant_id, interval_days, last_watered, next_due) VALUES (?,?,?,datetime(?,'+' || ? || ' days'))",
        (s.plant_id, s.interval_days, last, last, s.interval_days)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM schedules WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)

# ---------------------------------------------------------------------------
# Sensor readings
# ---------------------------------------------------------------------------

@app.get("/api/sensors")
def list_sensors(sensor: Optional[str] = None, limit: int = 50):
    conn = get_db()
    if sensor:
        rows = conn.execute(
            "SELECT * FROM sensor_readings WHERE sensor=? ORDER BY recorded DESC LIMIT ?",
            (sensor, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM sensor_readings ORDER BY recorded DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/sensors", status_code=201)
def log_sensor(reading: SensorIn):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO sensor_readings (sensor, value, unit) VALUES (?,?,?)",
        (reading.sensor, reading.value, reading.unit)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM sensor_readings WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)

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

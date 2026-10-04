"""SQLite minimo. Un solo usuario. Los datos de Garmin se guardan como JSON."""
import json
import os
import sqlite3
from pathlib import Path

DATA = Path(os.getenv("COACH_DATA", Path(__file__).resolve().parent.parent / "data"))
DB_PATH = DATA / "coach.db"

SCHEMA = """
create table if not exists daily_metrics (day text primary key, data text not null);
create table if not exists activities (activity_id integer primary key, start_time text, type text, data text not null);
create table if not exists recommendations (
  day text primary key, today text, upcoming text, analysis text, created_at text default current_timestamp);
create table if not exists reco (day text primary key, data text not null, created_at text default current_timestamp);
create table if not exists extra (key text primary key, data text not null, updated text default current_timestamp);
create table if not exists settings (key text primary key, value text not null);
create table if not exists log (id integer primary key autoincrement, day text, kind text, text text not null,
  created_at text default current_timestamp);
"""

DEFAULTS = {
    "goal_name": "Maraton de Paris (Asics)",
    "goal_date": "2027-04-04",
    "days_week": "",
    "context": "",
}


def conn() -> sqlite3.Connection:
    DATA.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def dumps(x) -> str:
    return json.dumps(x, ensure_ascii=False, default=str)


def get_settings(db) -> dict:
    s = dict(DEFAULTS)
    s.update({r["key"]: r["value"] for r in db.execute("select * from settings")})
    return s


def get_extra(db, key):
    r = db.execute("select data from extra where key = ?", (key,)).fetchone()
    return json.loads(r["data"]) if r else None

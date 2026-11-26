"""Append-only event log in SQLite: one table, JSON payloads."""
import json
import sqlite3
import time


class Store:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.execute("CREATE TABLE IF NOT EXISTS events (ts INTEGER, kind TEXT, data TEXT)")
        self.db.execute("CREATE INDEX IF NOT EXISTS events_kind ON events(kind, ts)")

    def log(self, kind: str, **data):
        self.db.execute("INSERT INTO events VALUES (?, ?, ?)", (int(time.time()), kind, json.dumps(data, default=str)))

    def last(self, kind: str) -> dict | None:
        row = self.db.execute("SELECT data FROM events WHERE kind = ? ORDER BY rowid DESC LIMIT 1", (kind,)).fetchone()
        return json.loads(row[0]) if row else None

    def all(self, kind: str) -> list[dict]:
        return [json.loads(r[0]) | {"ts": r[1]} for r in
                self.db.execute("SELECT data, ts FROM events WHERE kind = ? ORDER BY rowid", (kind,))]

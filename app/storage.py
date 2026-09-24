import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class LessonStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        return con

    def _initialize(self):
        with self._connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS lessons (
                id TEXT PRIMARY KEY, audio_hash TEXT NOT NULL, title TEXT NOT NULL,
                transcript TEXT NOT NULL, duration_seconds REAL, analysis_json TEXT NOT NULL,
                created_at TEXT NOT NULL, is_demo INTEGER NOT NULL DEFAULT 0
            )""")
            schema = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='lessons'").fetchone()[0]
            if "audio_hash TEXT UNIQUE" in schema:
                con.execute("ALTER TABLE lessons RENAME TO lessons_legacy")
                con.execute("""CREATE TABLE lessons (
                    id TEXT PRIMARY KEY, audio_hash TEXT NOT NULL, title TEXT NOT NULL,
                    transcript TEXT NOT NULL, duration_seconds REAL, analysis_json TEXT NOT NULL,
                    created_at TEXT NOT NULL, is_demo INTEGER NOT NULL DEFAULT 0
                )""")
                con.execute("""INSERT INTO lessons
                    (id,audio_hash,title,transcript,duration_seconds,analysis_json,created_at,is_demo)
                    SELECT id,audio_hash,title,transcript,duration_seconds,analysis_json,created_at,is_demo
                    FROM lessons_legacy""")
                con.execute("DROP TABLE lessons_legacy")

    def save(self, lesson: dict[str, Any]):
        with self._connect() as con:
            con.execute("""INSERT OR REPLACE INTO lessons
                (id,audio_hash,title,transcript,duration_seconds,analysis_json,created_at,is_demo)
                VALUES (?,?,?,?,?,?,?,?)""", (
                lesson["id"], lesson["audio_hash"], lesson["title"], lesson["transcript"],
                lesson.get("duration_seconds"), json.dumps(lesson["analysis"]),
                lesson.get("created_at", datetime.now(timezone.utc).isoformat()),
                int(lesson.get("is_demo", False)),
            ))

    def get(self, lesson_id: str):
        with self._connect() as con:
            row = con.execute("SELECT * FROM lessons WHERE id=?", (lesson_id,)).fetchone()
        return self._decode(row) if row else None

    def list(self, limit: int = 20):
        with self._connect() as con:
            rows = con.execute("SELECT * FROM lessons ORDER BY is_demo DESC, created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._decode(row) for row in rows]

    def remove_demo_lessons(self):
        """Remove bundled sample rows while preserving every user upload."""
        with self._connect() as con:
            con.execute("DELETE FROM lessons WHERE is_demo = 1")

    @staticmethod
    def _decode(row):
        item = dict(row)
        item["analysis"] = json.loads(item.pop("analysis_json"))
        item["is_demo"] = bool(item["is_demo"])
        return item

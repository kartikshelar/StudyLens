import json
import os
import sqlite3
from pathlib import Path
from typing import Any


def _db_path() -> Path:
    return Path(os.getenv("STUDYLENS_DB_PATH", "studylens.db"))


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """CREATE TABLE IF NOT EXISTS investigations (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            report_json TEXT NOT NULL
        )"""
    )
    return connection


def save_report(report: dict[str, Any]) -> None:
    with _connect() as connection:
        connection.execute(
            """INSERT INTO investigations(id, created_at, report_json)
               VALUES (?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET report_json = excluded.report_json""",
            (report["id"], report["created_at"], json.dumps(report)),
        )


def get_report(report_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT report_json FROM investigations WHERE id = ?", (report_id,)
        ).fetchone()
    return json.loads(row["report_json"]) if row else None

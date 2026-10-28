import json
import os
import sqlite3
from datetime import datetime, timezone
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
    connection.execute(
        """CREATE TABLE IF NOT EXISTS provider_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_tokens INTEGER NOT NULL,
            completion_tokens INTEGER NOT NULL,
            total_tokens INTEGER NOT NULL
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


def record_provider_usage(
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
) -> None:
    with _connect() as connection:
        connection.execute(
            """INSERT INTO provider_usage(
                   created_at, provider, model, prompt_tokens,
                   completion_tokens, total_tokens
               ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                provider,
                model,
                max(0, prompt_tokens),
                max(0, completion_tokens),
                max(0, total_tokens),
            ),
        )


def provider_usage_since(provider: str, since: str) -> dict[str, int]:
    with _connect() as connection:
        row = connection.execute(
            """SELECT COUNT(*) AS call_count,
                      COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                      COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                      COALESCE(SUM(total_tokens), 0) AS total_tokens
               FROM provider_usage
               WHERE provider = ? AND created_at >= ?""",
            (provider, since),
        ).fetchone()
    return {key: int(row[key]) for key in row.keys()}

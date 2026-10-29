import json
import os
import sqlite3
from contextlib import contextmanager
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
    connection.execute(
        """CREATE TABLE IF NOT EXISTS provider_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            provider TEXT NOT NULL,
            operation TEXT NOT NULL,
            usage_id INTEGER
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS request_windows (
            client_key TEXT NOT NULL,
            window_seconds INTEGER NOT NULL,
            window_start INTEGER NOT NULL,
            count INTEGER NOT NULL,
            PRIMARY KEY(client_key, window_seconds, window_start)
        )"""
    )
    return connection


@contextmanager
def _database():
    connection = _connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


class QuotaExceeded(Exception):
    pass


def _attempt_count(connection: sqlite3.Connection, provider: str, since: str) -> int:
    # Old successful calls have no attempt row. Keep counting them after upgrade.
    row = connection.execute(
        """SELECT
          (SELECT COUNT(*) FROM provider_attempts WHERE provider = ? AND created_at >= ?)
          + (SELECT COUNT(*) FROM provider_usage
             WHERE provider = ? AND created_at >= ?
             AND id NOT IN (SELECT usage_id FROM provider_attempts WHERE usage_id IS NOT NULL))
          AS count""",
        (provider, since, provider, since),
    ).fetchone()
    return int(row["count"])


def provider_attempt_counts(provider: str, since: str) -> dict[str, int]:
    with _database() as connection:
        return {
            "call_count": _attempt_count(connection, provider, since),
            "total_call_count": _attempt_count(connection, provider, ""),
        }


def reserve_provider_attempt(provider: str, operation: str, daily_limit: int, total_limit: int) -> int:
    now = datetime.now(timezone.utc)
    day_start = now.strftime("%Y-%m-%dT00:00:00+00:00")
    with _database() as connection:
        # Check and reserve under one write lock, including across server workers.
        connection.execute("BEGIN IMMEDIATE")
        if _attempt_count(connection, provider, day_start) >= daily_limit:
            raise QuotaExceeded(f"The daily {provider.title()} request limit has been reached.")
        if _attempt_count(connection, provider, "") >= total_limit:
            raise QuotaExceeded(f"The total {provider.title()} request limit has been reached.")
        cursor = connection.execute(
            "INSERT INTO provider_attempts(created_at, provider, operation) VALUES (?, ?, ?)",
            (now.isoformat(), provider, operation),
        )
        return int(cursor.lastrowid)


def admit_paid_request(client_key: str, now: int, per_minute: int, per_hour: int) -> int:
    """Return retry seconds if blocked; otherwise consume one HTTP request slot."""
    windows = [(60, per_minute), (3600, per_hour)]
    with _database() as connection:
        connection.execute("BEGIN IMMEDIATE")
        retry_after = 0
        for seconds, limit in windows:
            start = now // seconds * seconds
            row = connection.execute(
                "SELECT count FROM request_windows WHERE client_key = ? AND window_seconds = ? AND window_start = ?",
                (client_key, seconds, start),
            ).fetchone()
            if (row["count"] if row else 0) >= limit:
                retry_after = max(retry_after, start + seconds - now)
        if retry_after:
            return retry_after
        for seconds, _limit in windows:
            connection.execute(
                """INSERT INTO request_windows VALUES (?, ?, ?, 1)
                   ON CONFLICT(client_key, window_seconds, window_start)
                   DO UPDATE SET count = count + 1""",
                (client_key, seconds, now // seconds * seconds),
            )
        connection.execute("DELETE FROM request_windows WHERE window_start < ?", (now - 7200,))
    return 0


def save_report(report: dict[str, Any]) -> None:
    with _database() as connection:
        connection.execute(
            """INSERT INTO investigations(id, created_at, report_json)
               VALUES (?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET report_json = excluded.report_json""",
            (report["id"], report["created_at"], json.dumps(report)),
        )


def get_report(report_id: str) -> dict[str, Any] | None:
    with _database() as connection:
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
    *,
    attempt_id: int | None = None,
) -> None:
    with _database() as connection:
        cursor = connection.execute(
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
        if attempt_id is not None:
            connection.execute(
                "UPDATE provider_attempts SET usage_id = ? WHERE id = ? AND provider = ?",
                (cursor.lastrowid, attempt_id, provider),
            )


def provider_usage_since(provider: str, since: str) -> dict[str, int]:
    with _database() as connection:
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

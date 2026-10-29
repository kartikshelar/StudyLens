"""One-time import of local reports AND spending history into an empty hosted database."""

import argparse
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

from .store import DatabaseConnection, _database

TABLES = {
    "investigations": ("id", "created_at", "report_json"),
    "provider_usage": ("id", "created_at", "provider", "model", "prompt_tokens", "completion_tokens", "total_tokens"),
    "provider_attempts": ("id", "created_at", "provider", "operation", "usage_id"),
}


def import_ledger(source_path: Path, destination: DatabaseConnection) -> dict[str, int]:
    if not source_path.is_file():
        raise ValueError("The source SQLite database does not exist.")
    destination.begin_write()
    for table in TABLES:
        if destination.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]:
            raise ValueError("Destination is not empty; refusing to merge or overwrite reports and spending history.")
    if destination.execute("SELECT value FROM runtime_state WHERE key = ?", ("ledger_seeded",)).fetchone():
        raise ValueError("This destination has already been initialized.")
    source = sqlite3.connect(source_path.resolve().as_uri() + "?mode=ro", uri=True)
    copied = {}
    try:
        source.execute("BEGIN")
        for table, columns in TABLES.items():
            rows = source.execute(f"SELECT {', '.join(columns)} FROM {table}").fetchall()
            for row in rows:
                destination.execute(
                    f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})", row,
                )
            copied[table] = len(rows)
            if destination.postgres and table != "investigations":
                destination.execute(
                    f"SELECT setval(pg_get_serial_sequence(?, 'id'), COALESCE((SELECT MAX(id) FROM {table}), 1), EXISTS(SELECT 1 FROM {table}))",
                    (table,),
                )
        destination.execute("INSERT INTO runtime_state(key, value) VALUES (?, ?)", ("ledger_seeded", "true"))
    finally:
        source.close()
    return copied


def main(argv=None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", type=Path, default=Path("studylens.db"))
    args = parser.parse_args(argv)
    if os.getenv("STUDYLENS_LIVE_ENABLED", "true").strip().lower() not in {"false", "0", "no"}:
        parser.error("Pause live research in both the local and hosted environments before migrating.")
    if not os.getenv("DATABASE_URL", "").startswith(("postgresql://", "postgres://")):
        parser.error("Set the private DATABASE_URL in backend/.env; do not pass credentials on the command line.")
    try:
        with _database() as destination:
            copied = import_ledger(args.sqlite, destination)
    except ValueError as exc:
        parser.error(str(exc))
    print("Imported reports and spending history:", copied)
    print("The destination is marked ready; keep the public service paused until deployment checks pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

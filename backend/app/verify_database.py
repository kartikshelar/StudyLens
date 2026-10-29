"""Verify the configured PostgreSQL adapter using only explicitly disposable probe rows."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv

from . import store


def verify_database() -> dict:
    if not os.getenv("DATABASE_URL", "").startswith(("postgresql://", "postgres://")):
        raise ValueError("Configure DATABASE_URL before verifying PostgreSQL.")
    if os.getenv("STUDYLENS_LIVE_ENABLED", "true").strip().lower() not in {"false", "0", "no"}:
        raise ValueError("Pause live research before running the database verification.")
    if not store.hosted_ledger_ready():
        raise ValueError("Import the existing spending history before verification.")

    def real_counters():
        return {provider: store.provider_attempt_counts(provider, "")["total_call_count"]
                for provider in ("nebius", "tavily")}

    def snapshot():
        with store._database() as connection:
            return {table: connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]
                    for table in ("investigations", "provider_usage", "provider_attempts")}

    with store._database() as connection:
        tls_required = connection.raw.info.get_parameters().get("sslmode") in {"require", "verify-ca", "verify-full"}
        if not tls_required:
            raise ValueError("The hosted verification requires a TLS-required database connection.")
        previous_max_id = connection.execute("SELECT COALESCE(MAX(id), 0) AS id FROM provider_attempts").fetchone()["id"]

    before, counters = snapshot(), real_counters()
    # These identifiers are created here, never correspond to a real provider,
    # and are the only rows the cleanup is allowed to delete.
    probe_id = "storage-probe-" + uuid4().hex
    try:
        report = {
            "id": probe_id, "created_at": datetime.now(timezone.utc).isoformat(),
            "claim": "Storage verification only; no research claim was assessed.",
            "status": "source_not_confirmed", "verification_only": True,
        }
        store.save_report(report)
        assert store.get_report(probe_id) == report
        report["verification_step"] = "updated"
        store.save_report(report)
        assert store.get_report(probe_id)["verification_step"] == "updated"

        def reserve(_index):
            try:
                return store.reserve_provider_attempt(probe_id, "disposable-storage-check", 2, 2)
            except store.QuotaExceeded:
                return None

        with ThreadPoolExecutor(max_workers=4) as executor:
            attempts = list(executor.map(reserve, range(8)))
        accepted = [attempt for attempt in attempts if attempt is not None]
        assert len(accepted) == 2, "Concurrent quota reservations exceeded or missed their expected allowance."
        assert min(accepted) > previous_max_id, "Imported attempt IDs were not preserved by the sequence."
        store.record_provider_usage(probe_id, "storage-probe-only", 0, 0, 0, attempt_id=accepted[0])
        assert store.provider_attempt_counts(probe_id, "")["total_call_count"] == 2
    finally:
        with store._database() as connection:
            connection.begin_write()
            connection.execute("DELETE FROM investigations WHERE id = ?", (probe_id,))
            connection.execute("DELETE FROM provider_attempts WHERE provider = ?", (probe_id,))
            connection.execute("DELETE FROM provider_usage WHERE provider = ?", (probe_id,))

    assert snapshot() == before, "Verification did not restore its disposable rows."
    assert real_counters() == counters, "Real provider counters changed during verification."
    return {
        "database_engine": "postgresql", "tls_required": tls_required,
        "write_read_update": "passed", "atomic_quota": {"accepted": 2, "blocked": 6},
        "sequence_continuity": "passed", "usage_not_double_counted": "passed",
        "disposable_rows_removed": True, "existing_records_preserved": before,
        "real_provider_attempts_unchanged": counters, "paid_provider_calls": 0,
    }


if __name__ == "__main__":
    load_dotenv()
    print(json.dumps(verify_database(), indent=2))

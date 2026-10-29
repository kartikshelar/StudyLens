import pytest


@pytest.fixture(autouse=True)
def keep_unit_tests_local(monkeypatch):
    # An added hosting credential must never make routine tests touch a real database.
    monkeypatch.setenv("DATABASE_URL", "")

"""Phase 11 migration smoke tests."""

from importlib import import_module
from unittest.mock import patch

migration = import_module("alembic.versions.004_phase11_config_overrides")


def test_migration_identifiers():
    assert migration.revision == "004"
    assert migration.down_revision == "003"


def test_upgrade_executes_expected_sql():
    calls = []
    with patch.object(migration.op, "execute", side_effect=lambda sql: calls.append(sql)):
        migration.upgrade()

    joined = "\n".join(calls)
    assert "CREATE TABLE IF NOT EXISTS config_overrides" in joined
    assert "idx_config_overrides_updated_at" in joined


def test_downgrade_executes_expected_sql():
    calls = []
    with patch.object(migration.op, "execute", side_effect=lambda sql: calls.append(sql)):
        migration.downgrade()

    joined = "\n".join(calls)
    assert "DROP TABLE IF EXISTS config_overrides" in joined

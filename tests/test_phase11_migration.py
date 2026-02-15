"""Phase 11 migration smoke tests."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch

MIGRATION_PATH = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "004_phase11_config_overrides.py"
_SPEC = spec_from_file_location("phase11_migration_004", MIGRATION_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Unable to load migration module from {MIGRATION_PATH}")

migration = module_from_spec(_SPEC)
_SPEC.loader.exec_module(migration)


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

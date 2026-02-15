# Error Log

## 2026-02-15
- `pytest --collect-only -q` failed initially due to missing `pytest_asyncio` in the environment (dev deps not installed in runtime-only setup).

## 2026-02-16
- `pip install pytest-asyncio` failed due to network/proxy restriction (`Tunnel connection failed: 403 Forbidden`), preventing dependency install from PyPI.
- Full `pytest` execution remains blocked in this environment because `pytest_asyncio` cannot be installed.

- CI showed `ModuleNotFoundError: No module named 'alembic.versions'` for `tests/test_phase11_migration.py`; fixed by loading the migration via file path (`spec_from_file_location`).

# Error Log

## 2026-02-15
- `pytest --collect-only -q` failed initially due to missing `pytest_asyncio` in the environment (dev deps not installed in runtime-only setup).

## 2026-02-16
- `pip install pytest-asyncio` failed due to network/proxy restriction (`Tunnel connection failed: 403 Forbidden`), preventing dependency install from PyPI.
- Full `pytest` execution remains blocked in this environment because `pytest_asyncio` cannot be installed.

- CI showed `ModuleNotFoundError: No module named 'alembic.versions'` for `tests/test_phase11_migration.py`; fixed by loading the migration via file path (`spec_from_file_location`).
- Full suite regression after Phase 11: maintenance wrappers called runtime settings before DB init, causing `RuntimeError` across Phase 10/11/7 tests; fixed with default fallback in runtime settings accessor.
- Phase 11 data-management tests initially used non-existent DB APIs (`add_user`, positional `add_sighting`); fixed to use current DB interface.
- `pip install -e '.[dev]'` failed again in this session due to proxy/network restriction (`Tunnel connection failed: 403 Forbidden`), so local pytest collection with dev deps remains blocked.

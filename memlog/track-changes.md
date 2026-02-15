# Change Log

## 2026-02-16
- Added explicit `Phase 14: Internationalization (i18n)` section to `IMPROVEMENTS.md`.
- Added explicit `Phase 14` roadmap section to `parking_warden_bot_spec.md`.
- Updated `README.md` “Further Reading” roadmap range from Phases 1–13 to 1–14.
- Updated `memlog/progress.md` to record the roadmap-alignment correction.
- Added `memlog/phase11-implementation-checklist.md` with a mechanical, dependency-ordered Phase 11 execution plan covering migration, DB methods, runtime settings service, handlers, health, tests, and docs.
- Implemented Alembic migration `004_phase11_config_overrides.py` and database fallback schema for `config_overrides`.
- Added runtime settings and maintenance services (`bot/services/runtime_settings.py`, `bot/services/maintenance.py`) and exported service APIs.
- Extended admin command surface for runtime config, maintenance, purge, and export workflows with audit logging and preview/confirm flows.
- Refactored report/user/main/health logic to consume runtime settings, enforce maintenance behavior, and expose degraded health status.
- Added Phase 11 test modules: `tests/test_phase11_runtime_config.py`, `tests/test_phase11_maintenance.py`, `tests/test_phase11_data_management.py`, `tests/test_phase11_migration.py`.
- Updated roadmap/spec/operator docs to mark Phase 11 completion and document new admin commands.
- Updated `memlog/progress.md` to Phase 1.5 with post-implementation next steps.

- Fixed stale `parking_warden_bot_spec.md` heading text from “with Phase 11 planned” to completed Phase 11 wording.
- Fixed `tests/test_phase11_migration.py` import mechanism to load migration module from filesystem path instead of `alembic.versions` package import, resolving CI collection error.

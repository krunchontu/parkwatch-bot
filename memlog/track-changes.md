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
- Added runtime-settings fallback-to-default behavior when DB is unavailable/uninitialized, preventing maintenance decorators from breaking unit tests that do not initialize DB.
- Corrected `tests/test_phase11_data_management.py` to use `ensure_user()` and dict-based `add_sighting()` API.

## 2026-02-16 (Phase 11 Review Fixes)
- Fixed `maintenance_conversation_check` double-message bug: now sends single combined maintenance+cancellation message instead of two separate messages.
- Fixed potential `AttributeError` in `maintenance_conversation_check` when `callback_query.message` is `None`; falls back to `query.answer()`.
- Made `purge_sightings_older_than` atomic: replaced non-atomic SELECT COUNT + DELETE with cursor `rowcount` (SQLite) / DELETE status string (PostgreSQL).
- Removed `DELETE FROM config_overrides WHERE updated_by = ?` from `purge_user_data` — config overrides are shared state, not user-owned data.
- Added case-insensitive zone matching to `/admin purge sightings zone` with unknown-zone error message (consistent with `/admin zone`).
- Removed duplicate `max_warnings` runtime settings fetch in `_admin_warn` (fetched once, reused for both notification and auto-ban check).
- Added optional `actor_id` parameter to `reset_override()` for audit traceability; updated call site in `_admin_config`.
- Added inline ban check to `handle_start_menu` callback handler (pre-existing gap; `ban_check` decorator only works with `update.message`).
- Expanded Phase 11 test coverage from 13 to 37 tests:
  - `test_phase11_runtime_config.py`: 5→18 tests (added forbidden key tests, type validation, bool truthy/falsy, empty string, list_effective source, set old/new return, allowlist size, fail-safe default, upsert overwrite).
  - `test_phase11_maintenance.py`: 2→9 tests (added allows-when-off, callback query blocking, inline query blocking, single-message assertion, callback query conversation cancel, conversation allows-when-off).
  - `test_phase11_data_management.py`: 3→10 tests (added zone-scoped purge, zero-match purge, full GDPR table coverage, config override preservation, negative feedback recalc, CSV key completeness, JSON no-PII assertion).
- Updated `IMPROVEMENTS.md` Phase 11 items to document review fixes.
- Updated `memlog/progress.md` to Phase 1.9.

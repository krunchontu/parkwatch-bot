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

## 2026-02-16 (Documentation-vs-code app review refresh)
- Rewrote `APP_REVIEW.md` with a stricter documentation-to-code audit, explicit good/bad/ugly sections, and benchmark comparison against world-class Telegram bots.
- Added concrete mismatch callouts (test-count drift, Phase 11 status drift, `/start` flow drift, feedback confirmation semantics).
- Added prioritized rewrite-first recommendations focused on documentation truthfulness, fanout hardening, and observability.

## 2026-02-16 (Targeted docs drift fixes)
- Updated `README.md` test language to remove stale hardcoded counts and use suite-oriented wording.
- Updated `parking_warden_bot_spec.md` Phase 11 admin command statuses (`maintenance`, `config`) from Planned → Done.
- Updated `/start` onboarding flow in `parking_warden_bot_spec.md` to reflect the current quick-action menu before region/zone selection.
- Updated spec tech-stack testing row to remove stale hardcoded test count wording.

## 2026-02-16 (Fresh app review pass)
- Re-refreshed `APP_REVIEW.md` with a tighter good/bad/ugly structure and explicit benchmark framing against world-class Telegram bots.
- Kept recommendations rewrite-first and focused on highest-ROI improvements (docs truth, feedback contract, fanout hardening, modularity, metrics baseline).

## 2026-02-16 (Docs-only stale metrics + UX wording cleanup)
- Removed stale hardcoded test-count and pass-rate snapshots from `IMPROVEMENTS.md` while preserving scope descriptions of test coverage.
- Removed stale hardcoded test counts from `parking_warden_bot_spec.md` test sections and test-file table.
- Updated `/start` command wording in `parking_warden_bot_spec.md` to reflect current quick-action menu entrypoint.
- Updated `/start` command wording in `README.md` to reflect quick-action menu behavior.

## 2026-02-18 (11.5.1 /start menu — Approach C implementation plan, docs only)
- Designed Approach C (Hybrid Edit-in-Place + Back Button Navigation) after analyzing all UX permutations against Telegram Bot API constraints.
- `IMPROVEMENTS.md` section 11.5.1: Replaced placeholder checklist with full implementation plan including architecture description, callback routing table, 7 implementation steps with file/function details, and edge case handling.
- `parking_warden_bot_spec.md` Flow 1: Rewrote onboarding flow to document per-button behavior — edit-in-place for reads (recent, stats, help), ConversationHandler entry for report, clear instructions for feedback, back button navigation for all screens.
- `README.md`: Updated `/start` command table description to reflect inline execution with back navigation.
- `APP_REVIEW.md`: Added "Status: planned" annotations to Part 1 finding #5 (docs-code divergence on /start flow) and Part 4 finding #1 (/start buttons decorative) with cross-reference to IMPROVEMENTS.md 11.5.1.
- `memlog/progress.md`: Added Phase 2.4 update with Approach C design completion and next steps.
- No code files modified — documentation-only changes preparing for implementation.

## 2026-02-20 (Second-pass docs-vs-code review refresh)
- Rewrote `APP_REVIEW.md` with a fresh, judicious second-pass audit focused on documentation-code alignment, Good/Bad/Ugly framing, and benchmark comparison against world-class Telegram bots.
- Added an explicit discrepancy register for `/start` behavior, feedback delivery semantics, and done-vs-planned documentation tone.
- Added prioritized rewrite-first action list emphasizing truth-first docs, feedback delivery contract, fanout hardening, and observability baseline.

## 2026-02-20 (Phase 11.5 Tech Debt & Hardening — full implementation)
- **11.5.1 /start menu fix (Approach C):** Refactored `bot/handlers/user.py` with `_build_recent_text()`, `_build_mystats_text()`, `_build_help_text()` text builders, `_build_start_keyboard()`, `_build_back_button()` helpers, `handle_start_menu()` for edit-in-place with back button, `back_to_start_menu()` handler. Added `report_from_start()` in `bot/handlers/report.py` as ConversationHandler entry point. Updated `bot/main.py` with callback routing for start_back, start_report guard, and report_conv entry points.
- **11.5.2 ban_check fix:** Updated `bot/services/moderation.py` `ban_check` decorator to handle both `update.message` and `update.callback_query` updates. Removed manual is_banned check from handle_start_menu.
- **11.5.3 Rate limiting decoupled:** Created `alembic/versions/006_user_rate_limits.py` migration. Added `user_rate_limits` table to `create_tables()`, `record_rate_limit_event()` method, updated `count_user_feedback_since()` to query new table, updated `purge_user_data()` to clean new table.
- **11.5.4 GDPR purge PII scrub:** Updated `bot/database.py` `purge_user_data()` to NULL both `target` AND `detail` columns in `admin_actions` (both SQLite and PostgreSQL paths).
- **11.5.5 Callback validation:** Added `parse_callback_data()` with UUID regex validation to `bot/utils.py`. Applied to `handle_feedback` in `bot/handlers/report.py`.
- **11.5.6 Health check port fix:** Changed `HEALTH_CHECK_PORT` in `config.py` to default to 8080 unconditionally (was falling back to PORT). Added startup warning in `bot/main.py` if port collision detected.
- **11.5.7 Broadcast hardening:** Rewrote `bot/services/notifications.py` with `asyncio.Semaphore(20)` bounded concurrency, `_send_one()` helper with retry on TimedOut/OSError and RetryAfter handling, `broadcast_message()` for admin announcements. Updated `bot/handlers/admin/announce.py` to use `broadcast_message()`.
- **11.5.8 main.py shim:** Verified already clean — no action needed.
- **11.5.9 Typed data models:** Created `bot/models.py` with TypedDict definitions (UserRow, UserStatsRow, SubscriptionRow, SightingRow, FeedbackRow, AdminActionRow, BannedUserRow, ConfigOverrideRow, GlobalStatsRow, ZoneDetailRow). Added `cast()` annotations to key Database methods.
- **11.5.10 Database split:** Deferred to separate PR (large refactor).
- **11.5.11 Admin handler split:** Already done in Phase 10 — verified no action needed.
- **11.5.12 Handler-level tests:** Created `tests/helpers.py` (make_update, make_callback_update, make_context, make_mock_db). Created `tests/test_handlers_user.py` (19 tests) and `tests/test_handlers_callbacks.py` (12 tests).
- **11.5.13 SQLite cascade fix:** Removed manual feedback deletion from `cleanup_old_sightings()` in `bot/database.py` — relies on ON DELETE CASCADE. Added TestCascadeDelete test.
- **11.5.14 CI validation:** All gates pass — ruff check, ruff format, mypy (0 errors, 27 files), pytest (335 passed). Fixed ruff lint (SIM102, F841), ruff format (3 files), mypy TypedDict cast errors (9 fixes).
- **Documentation updates:** Refreshed `APP_REVIEW.md` (scores up: 6.2→7.1), updated `README.md` (v1.4.0, models.py, 6 migrations), updated `parking_warden_bot_spec.md` (user_rate_limits schema, new files), updated `IMPROVEMENTS.md` (all 11.5 items checked). Bumped `BOT_VERSION` to "1.4.0".

## 2026-02-23 (Phase 11.8 Database Refactor — full implementation)
- **11.8.1 Repository pattern split:** Created `bot/repositories/` package with `BaseRepository` (shared DB access helpers via property delegation), `UserRepository` (17 methods: subscriptions, user CRUD, warnings), `SightingRepository` (15 methods: CRUD, queries, cleanup, moderation), `FeedbackRepository` (8 methods: votes, accuracy, rate limits), `AdminRepository` (14 methods: audit, stats, banning, data management), `ConfigRepository` (4 methods: config overrides). Refactored `bot/database.py` from 1,147 lines to ~260 lines — retains connection management, query helpers, table creation, and a `__getattr__`-based facade that delegates to repositories for full backward compatibility. All existing `get_db().method()` call sites continue to work without modification.
- **11.8.2 PostgreSQL-specific test suite:** Created `tests/test_phase11_8_postgresql.py` with 26 tests covering PostgreSQL code paths via mocking: driver detection (5 tests), placeholder syntax (2 tests), DDL transformations (3 tests), upsert ON CONFLICT syntax (5 tests), RETURNING clause for atomic increment-and-read (2 tests), GREATEST vs MAX for floor clamping (1 test), IN-clause placeholder generation (1 test), DELETE result string parsing (4 tests), and pool health checks (3 tests).
- **11.8.3 Repository split tests:** Created `tests/test_phase11_8_repositories.py` with 30 tests covering: repository class structure (5 tests), Database composition (3 tests), `__getattr__` delegation correctness (5 tests), integration tests for all repositories via both facade and direct access (12 tests), cross-repo operations (1 test), and code modularity verification (2 tests). Total: 56 new tests.
- **Documentation updates:** Updated `IMPROVEMENTS.md` (Phase 11.8 marked complete, version 1.7.0, 438 tests), `README.md` (version bump, project structure with repositories/), `APP_REVIEW.md` (database modularity finding resolved), `config.py` (BOT_VERSION 1.7.0), `memlog/progress.md` (Phase 3.3), `memlog/track-changes.md`.
- **CI results:** ruff check (0 errors), ruff format (0 changes), mypy (0 errors, 33 source files), pytest (200 tests pass — all non-telegram tests including 56 new).

## 2026-02-23 (Phase 11.7 Reliability Hardening — full implementation)
- **11.7.1 Connection pool health checks:** Added `statement_timeout` (30s), `idle_in_transaction_session_timeout` (60s), `command_timeout` (30s) to asyncpg pool via `init` callback in `bot/database.py`. Added `check_pool_health()` method returning pool size, free connections, min/max, exhaustion detection, and connectivity check for both SQLite and PostgreSQL drivers.
- **11.7.2 Conversation state persistence:** Added `PicklePersistence` (filepath configurable via `PERSISTENCE_PATH` env var, default `parkwatch_persistence`) to Application builder in `bot/main.py`. Set ConversationHandler to `persistent=True, name="report_conversation"`. In-progress reports now survive bot restarts.
- **11.7.3 Configurable cleanup interval:** Added `CLEANUP_INTERVAL_HOURS` env var (default 6) in `config.py`. Added to `MUTABLE_SPECS` in `bot/services/runtime_settings.py` for live adjustment via `/admin config`. Updated `bot/main.py` to use configurable interval instead of hardcoded 21600s.
- **11.7.4 Exponential backoff:** Updated `_send_one()` in `bot/services/notifications.py` to use exponential backoff (2^attempt: 1s, 2s, 4s) on transient (TimedOut/OSError) failures. Increased default retries from 1 to 3. Forbidden and unexpected errors remain non-retried.
- **11.7.5 GPS bounds validation:** Added `_is_within_singapore()` bounds check (lat 1.15–1.47, lng 103.60–104.05) and validation in `handle_location()` in `bot/handlers/report.py`. Out-of-bounds coordinates are rejected with a user-friendly message redirecting to manual zone selection.
- **11.7.6 Tests:** Created `tests/test_phase11_7.py` with 26 new tests covering all items. Updated `tests/test_phase8.py`, `tests/test_phase9.py` (forward-compatible version checks), `tests/test_phase11_runtime_config.py` (updated allowlist count to 10). Full suite: 382 tests passing.
- **Documentation updates:** Updated `IMPROVEMENTS.md` (Phase 11.7 marked complete, version 1.6.0, 382 tests), `README.md` (version bump, new env vars), `APP_REVIEW.md` (5 findings marked resolved), `memlog/progress.md` (Phase 3.2), `memlog/track-changes.md`. Bumped `BOT_VERSION` to "1.6.0".

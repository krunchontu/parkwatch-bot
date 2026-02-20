# ParkWatch SG — Code Review & Improvement Plan

## Audit Summary

**Date:** 2026-02-12 (initial), 2026-02-13 (Phase 8 update), 2026-02-14 (Phase 9 update), 2026-02-15 (Phase 10 planning), 2026-02-16 (Phase 11–14 roadmap alignment), 2026-02-17 (Phase 11.5 tech debt plan)
**Scope:** Full code review against `parking_warden_bot_spec.md` and `README.md`
**Files reviewed:** `bot/main.py`, `bot/database.py`, `bot/health.py`, `bot/logging_config.py`, `config.py`, `requirements.txt`, `.env.example`

---

## Status: Phases 1–11 Complete

Phases 1 through 11 addressed critical bugs, UX issues, data persistence, robustness gaps, automated testing/CI, production infrastructure, admin visibility and moderation, architecture refactoring, and runtime operations (maintenance/config/purge/export). Completed items below are checked off and verified in the current codebase.

### Phase 1: Critical Fixes (Code-Doc Alignment & Stability) ✅

- [x] **1.1** Move top-level imports (`datetime`, `time`, `random`, `math`) to module top
- [x] **1.2** Use `config.SIGHTING_EXPIRY_MINUTES` instead of hardcoded 30
- [x] **1.3** Implement rate limiting (3 reports/user/hour) using `MAX_REPORTS_PER_HOUR`
- [x] **1.4** Implement duplicate detection (same zone within 5 mins, GPS-aware with 200m radius)
- [x] **1.5** Add server-side self-rating prevention in `handle_feedback()`
- [x] **1.6** Guard `handle_location` so it only triggers during active report flow (`ConversationHandler`)

### Phase 2: UX Improvements ✅

- [x] **2.1** Multi-zone subscription — keep keyboard open after each selection, add "Done" button
- [x] **2.2** Region-then-zone selection for manual report (matches subscribe flow)
- [x] **2.3** `ConversationHandler` for report flow (6-state machine with 300s timeout)
- [x] **2.4** Share Location flow uses `KeyboardButton(request_location=True)`

### Phase 3: Data Persistence ✅

- [x] **3.1** Dual-driver database: SQLite (dev) via aiosqlite, PostgreSQL (prod) via asyncpg
- [x] **3.2** Schema: `users`, `subscriptions`, `sightings`, `feedback` (4 tables + 4 indexes)
- [x] **3.3** All in-memory stores migrated to database
- [x] **3.4** Accuracy scores calculated from full sighting history (SQL aggregate)
- [x] **3.5** Sighting expiry/cleanup as scheduled job (every 6 hours)

### Phase 4: Robustness & Code Quality ✅

- [x] **4.1** Alert messages rebuilt from structured DB data (no string parsing)
- [x] **4.2** Haversine formula for GPS distance calculation
- [x] **4.3** Input sanitization: strip HTML, control characters, collapse whitespace, truncate 100 chars
- [x] **4.4** Broadcast failure handling — notify reporter, auto-cleanup blocked users' subscriptions
- [x] **4.5** Feedback window (24h configurable) — stale buttons disabled gracefully
- [x] **4.6** Global error handler with user notification, per-handler try/except for DB errors

---

## Current State Assessment (2026-02-16)

### What's Working Well

1. **Feature completeness** — All 10 user commands + full admin command suite (23 subcommands across Phases 8–11) implemented and functional
2. **ConversationHandler** — Proper 6-state machine with timeout, fallbacks, and `/cancel` support
3. **Database layer** — Clean dual-driver abstraction with WAL mode, connection pooling, parameterized queries
4. **GPS-aware duplicate detection** — Haversine + 200m radius, zone-level fallback
5. **Feedback system** — Transaction-safe, vote changing, self-rating prevention, window expiry
6. **Alert message architecture** — `build_alert_message()` as single source of truth
7. **Blocked user cleanup** — Catches `Forbidden`, removes stale subscriptions
8. **Config externalization** — All tunable values in `config.py` with env var overrides
9. **Timezone-safe datetime** — All `datetime.now(timezone.utc)` throughout codebase
10. **Proper Python packaging** — Runs as `python -m bot.main`, relative imports, no sys.path hacks
11. **Test coverage** — Comprehensive automated coverage across unit, database integration, infrastructure, admin, moderation, and UX flows (validated in CI)
12. **CI pipeline** — Automated lint, type check, and test on every push/PR via GitHub Actions
13. **Code quality** — All ruff lint and format checks pass, mypy type checking clean
14. **Production infrastructure** — Webhook mode, health check endpoint, structured JSON logging, Alembic migrations, Sentry integration
15. **Admin foundation** — Authentication layer, global stats dashboard, user/zone lookup, audit logging with comprehensive automated test coverage
16. **User management** — Ban/unban, moderation queue, warning system with auto-ban escalation, ban enforcement middleware

---

### Phase 5: Bug Fixes ✅

All 10 known issues from the Phase 1–4 review have been fixed.

- [x] **5.1** Use `datetime.now(timezone.utc)` everywhere — all bare `datetime.now()` calls replaced in `main.py` and `database.py`
- [x] **5.2** Replace sighting ID generation with `uuid4()` — collision-proof, removed `time`/`random` imports
- [x] **5.3** Transaction-safe feedback — new `Database.apply_feedback()` method wraps read→upsert→update in a single transaction (SQLite commit block / PostgreSQL `conn.transaction()`)
- [x] **5.4** Fix rate limit wait calculation — `.total_seconds()` with `max(1, ...)` guard
- [x] **5.5** Fix PostgreSQL cleanup — wrapped in transaction, added `try/except` for string parsing
- [x] **5.6** Add foreign key constraint — `feedback.sighting_id REFERENCES sightings(id) ON DELETE CASCADE`
- [x] **5.7** Show "No ratings yet" for zero feedback — `calculate_accuracy()` returns `(0.0, 0)`, confirm message branches on `total_feedback > 0`
- [x] **5.8** Move `ZONE_COORDS` to module level — 80 zone coordinates defined alongside `ZONES` dict
- [x] **5.9** Fix `sys.path` hack — relative import (`from .database import ...`), run via `python -m bot.main`, Procfile/railway.toml updated
- [x] **5.10** Show "Join drivers" when subscriber count < 10 — no misleading "0+" on fresh deployments

### Phase 6: Testing & CI ✅

Automated test suite and CI pipeline to maintain code quality and prevent regressions.

- [x] **6.1** Set up pytest with `pytest-asyncio` (`asyncio_mode = "auto"`) for async test support
- [x] **6.2** Unit tests for pure functions: `haversine_meters`, `get_reporter_badge`, `get_accuracy_indicator`, `sanitize_description`, `build_alert_message`, `generate_sighting_id`, plus zone data integrity checks
- [x] **6.3** Database integration tests: subscriptions, users, sightings, recent/duplicate detection, rate limiting, feedback, accuracy, cleanup, feedback counts, driver initialization
- [x] **6.4** GitHub Actions CI pipeline (`.github/workflows/ci.yml`): lint (ruff check + format), type check (mypy), test (pytest across Python 3.10/3.11/3.12)
- [x] **6.5** `pyproject.toml` for proper packaging — project metadata, dependencies, `[project.optional-dependencies] dev`, tool configs for pytest/ruff/mypy
- [x] **6.6** Lint fixes applied: import sorting (isort), unused variables removed, f-string cleanup, `contextlib.suppress` for try-except-pass patterns, PEP 8 naming compliance

### Phase 7: Production Infrastructure ✅

Harden deployment, observability, and schema management for real-world scale. Separated from admin functionality (Phase 8–11) which is a distinct feature domain.

- [x] **7.1** Webhook mode support (alongside polling) — set `WEBHOOK_URL` to enable; bot auto-detects and switches from `run_polling()` to `run_webhook()` with Telegram-compatible URL path; `PORT` configurable via env var
- [x] **7.2** Health check endpoint — standalone asyncio HTTP server in `bot/health.py`; responds to `GET /health` with JSON status (version, mode, timestamp); configurable via `HEALTH_CHECK_ENABLED` and `HEALTH_CHECK_PORT`; lifecycle managed in `post_init`/`post_shutdown`; Railway config updated with `healthcheckPath = "/health"`
- [x] **7.3** Structured logging (JSON format) — `bot/logging_config.py` with `JSONFormatter` producing single-line JSON with timestamp, level, logger name, message, and optional exception/context fields; toggle via `LOG_FORMAT=json` env var; text mode preserved as default for development; noisy third-party loggers suppressed
- [x] **7.4** Database migrations with Alembic — `alembic.ini`, `alembic/env.py`, migration template, and initial baseline migration (`001_initial_schema.py`) matching existing `create_tables()` schema; reads `DATABASE_URL` from `config.py`; supports both SQLite and PostgreSQL; `create_tables()` retained as fallback for zero-migration bootstrapping
- [x] **7.5** Sentry error tracking — graceful init via `_init_sentry()` in `main()`; reads `SENTRY_DSN` from env; sets release tag to bot version, traces_sample_rate=0.1, environment auto-detected from webhook/polling mode; `sentry-sdk` is an optional dependency (`pip install ".[sentry]"`); missing SDK produces a warning, not a crash
- [x] **7.6** Test coverage for all Phase 7 features — health check server lifecycle, JSON formatter, setup_logging, config validation, and Sentry initialization

---

### Phase 8: Admin — Foundation & Visibility ✅

Establish the admin authentication layer, provide global visibility into bot activity, and create the audit infrastructure that all subsequent admin features depend on.

**Why this phase exists:** The bot currently has zero admin functionality. A crowdsourced reporting platform needs operator visibility and control before scaling. Every subsequent admin phase builds on the auth layer and audit table introduced here.

#### 8.1 Admin Authentication & Authorization

- [x] **8.1.1** `ADMIN_USER_IDS` environment variable — comma-separated list of Telegram user IDs authorized as admins; parsed in `config.py` with validation (non-numeric values silently ignored)
- [x] **8.1.2** `admin_only` decorator — wraps `admin_command()` handler; rejects unauthorized users with a generic "Unknown command" response (avoids revealing admin commands exist)
- [x] **8.1.3** Add `ADMIN_USER_IDS` to `.env.example` and documented in README

#### 8.2 Admin Help

- [x] **8.2.1** `/admin` command — lists all available admin commands with descriptions (only shown to authenticated admins); routed through `admin_command()` which dispatches to subcommand handlers
- [x] **8.2.2** `/admin help <command>` — detailed usage for a specific admin command; `ADMIN_COMMANDS_HELP` (brief) and `ADMIN_COMMANDS_DETAILED` (full) dictionaries

#### 8.3 Global Statistics Dashboard

- [x] **8.3.1** `/admin stats` — displays key metrics in a single message:
  - Total registered users (all-time)
  - Active users (reported or gave feedback in last 7 days)
  - Total sightings (all-time and last 24 hours)
  - Active subscriptions and unique subscribers
  - Top 5 most-subscribed zones
  - Top 5 most-reported zones (last 7 days)
  - Feedback totals (positive vs negative, overall accuracy rate)
- [x] **8.3.2** Database methods: `get_global_stats()`, `get_top_zones_by_subscribers()`, `get_top_zones_by_sightings()`; active users approximated from reporter + feedback giver counts

#### 8.4 User & Zone Lookup

- [x] **8.4.1** `/admin user <telegram_id or @username>` — look up a specific user:
  - Registration date, report count, badge, accuracy score
  - Subscribed zones
  - Recent sightings (last 10)
  - Feedback received (positive/negative totals)
  - Ban status and warning count (Phase 9)
- [x] **8.4.2** `/admin zone <zone_name>` — look up a specific zone (case-insensitive matching):
  - Subscriber count
  - Sighting count (last 24h / 7d / all-time)
  - Top reporters in this zone
  - Most recent sightings
- [x] **8.4.3** Database methods: `get_user_details()`, `get_user_by_username()`, `get_zone_details()`, `get_user_recent_sightings()`, `get_user_subscriptions_list()`, `get_zone_top_reporters()`, `get_zone_recent_sightings()`

#### 8.5 Audit Logging

- [x] **8.5.1** `admin_actions` table — schema:
  ```sql
  admin_actions (
    id INTEGER PK AUTOINCREMENT,
    admin_id BIGINT NOT NULL,
    action TEXT NOT NULL,        -- e.g. 'view_stats', 'lookup_user', 'lookup_zone'
    target TEXT,                 -- e.g. user ID, zone name
    detail TEXT,                 -- free-form context (reason, message preview, etc.)
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
  )
  ```
  Alembic migration `002_admin_actions_table.py` added; table also created by `create_tables()` fallback.
- [x] **8.5.2** `log_admin_action()` database method — called by every admin operation (`view_stats`, `lookup_user`, `lookup_zone`)
- [x] **8.5.3** `/admin log [count]` — view the most recent N admin actions (default 20, max 100)

#### 8.6 Testing

- [x] **8.6.1** Expanded tests in `tests/test_phase8.py`: config parsing, admin-only guard, audit log DB operations, global stats queries, user/zone lookup DB methods, admin_actions schema validation, help constants, and zone validation

---

### Phase 9: Admin — User Management & Content Moderation ✅

Give admins the ability to remove bad actors and false content. Critical for platform trust as the user base grows.

**Why this phase exists:** A crowdsourced platform where any user can broadcast alerts to others is inherently vulnerable to abuse. Without ban and moderation tools, a single spammer can degrade the experience for all subscribers in a zone.

#### 9.1 User Banning

- [x] **9.1.1** `banned_users` table — schema:
  ```sql
  banned_users (
    telegram_id BIGINT PK,
    banned_by BIGINT NOT NULL,
    reason TEXT,
    banned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
  )
  ```
  Alembic migration `003_phase9_user_management.py` added; table also created by `create_tables()` fallback.
- [x] **9.1.2** `/admin ban <user_id> [reason]` — ban a user:
  - Insert into `banned_users`
  - Clear all subscriptions for the user (stop them receiving alerts)
  - Log action to `admin_actions`
  - Notify the banned user: "Your account has been restricted due to policy violations."
  - Prevents banning admin users
  - Idempotent: re-banning updates the existing ban record
- [x] **9.1.3** `/admin unban <user_id>` — remove ban, reset warnings to zero, log action, notify user
- [x] **9.1.4** `/admin banlist` — list all currently banned users with ban date, banning admin, and reason
- [x] **9.1.5** Ban enforcement middleware — `ban_check` decorator on every user-facing command handler:
  - Banned users cannot: `/report`, `/subscribe`, `/unsubscribe`, `/myzones`, `/recent`, `/mystats`, `/share`
  - Banned users receive a single static restriction message when attempting any action
  - `/start` is intentionally excluded (allow re-onboarding after unban)
- [x] **9.1.6** Database methods: `ban_user()`, `unban_user()`, `is_banned()`, `get_banned_users()`

#### 9.2 Sighting Moderation

- [x] **9.2.1** `/admin delete <sighting_id> [confirm]` — remove a specific sighting:
  - First call shows sighting details (zone, time, description, reporter, feedback) for review
  - Add `confirm` to execute deletion; FK CASCADE handles feedback cleanup
  - Log action to `admin_actions` with sighting zone and reporter ID
- [x] **9.2.2** `/admin review` — show a moderation queue with two sections:
  - **Flagged Sightings:** sightings explicitly flagged OR with negative feedback > positive (3+ total votes)
  - **Low-Accuracy Reporters:** users with accuracy < 50% and 5+ total feedback ratings
  - Display includes sighting details, reporter info, feedback ratio with percentage
  - Includes actionable hints (delete, ban, warn commands)
- [x] **9.2.3** Auto-flag logic — `_check_auto_flag()` called after every feedback update:
  - Flags sighting when negative feedback ratio exceeds 70% (with at least 3 total votes)
  - `flagged` INTEGER column (0/1) added to `sightings` table
  - Logged with structured logging when triggered
- [x] **9.2.4** Database methods: `delete_sighting()`, `get_flagged_sightings()`, `flag_sighting()`, `get_low_accuracy_reporters()`

#### 9.3 Reporter Warnings

- [x] **9.3.1** `/admin warn <user_id> [message]` — send a warning to a user:
  - Bot messages the user with the warning text and current warning count (N/MAX_WARNINGS)
  - Increments `warnings` column in `users` table
  - Log to `admin_actions` with warning number and message preview
  - Default message provided when no custom message specified
- [x] **9.3.2** Warning tracking — `warnings` INTEGER column added to `users` table (default 0)
  - Database methods: `get_user_warnings()`, `increment_warnings()`, `reset_warnings()`
  - Warning count visible in `/admin user <id>` lookup
- [x] **9.3.3** Escalation path: 3 warnings → auto-ban (configurable via `MAX_WARNINGS` env var, default 3)
  - When warning count reaches MAX_WARNINGS, user is automatically banned
  - Auto-ban logged to `admin_actions` with reason "Warning count reached N"
  - Admin notified of auto-ban in command response
  - Set `MAX_WARNINGS=0` to disable auto-ban escalation

#### 9.4 Testing

- [x] **9.4.1** Expanded tests in `tests/test_phase9.py`: ban operations, sighting moderation, low-accuracy reporter logic, warning flows, schema/config validation, `ban_check` behavior, auto-flag logic, and escalation paths

---

### Phase 10: Architecture, UX & Communication

Structural improvements to reduce maintenance debt, close the admin-user communication loop, and improve discoverability. Prioritised based on external code review feedback (2026-02-15).

**Why this phase exists:** `bot/main.py` at 2,278 lines is a monolith that blends command routing, business logic, message rendering, and admin operations. Every subsequent feature added to this file increases maintenance cost and onboarding time. Refactoring first ensures items 10.3–10.5 land as clean, isolated modules. The review also identified missing two-way communication (users cannot reach admins; admins cannot announce to users) and UX that depends too heavily on command literacy.

#### 10.1 Documentation Cleanup

- [x] **10.1.1** Fix README version drift — update stale `1.2.0` references in example output to match `BOT_VERSION = "1.3.0"` (lines 86, 490)
- [x] **10.1.2** Consolidate README and spec — trim `README.md` to operator essentials (setup, deployment, env vars, command reference); move deep product flow details into `parking_warden_bot_spec.md` as the single maintained spec; eliminate duplicated content between the two files
- [x] **10.1.3** Update file reference table and line counts in IMPROVEMENTS.md after refactor

#### 10.2 Refactor `bot/main.py` into Modules

- [x] **10.2.1** Extract zone data → `bot/zones.py`:
  - `ZONES` dict (80 zones across 6 regions), `ZONE_COORDS` coordinate table
- [x] **10.2.2** Extract utility functions → `bot/utils.py`:
  - `haversine_meters()`, `get_reporter_badge()`, `get_accuracy_indicator()`, `generate_sighting_id()`, `sanitize_description()`
- [x] **10.2.3** Extract UI helpers → `bot/ui/keyboards.py`:
  - `build_zone_keyboard()`, future menu keyboards
- [x] **10.2.4** Extract message builders → `bot/ui/messages.py`:
  - `build_alert_message()`, future message templates
- [x] **10.2.5** Extract notification logic → `bot/services/notifications.py`:
  - Broadcast/fanout to zone subscribers, blocked-user cleanup
- [x] **10.2.6** Extract moderation utilities → `bot/services/moderation.py`:
  - `ban_check` decorator, `_check_auto_flag()`, auto-ban escalation logic
- [x] **10.2.7** Extract user command handlers → `bot/handlers/user.py`:
  - `/start`, `/subscribe`, `/unsubscribe`, `/myzones`, `/help`, `/mystats`, `/share`, `/feedback`
- [x] **10.2.8** Extract report flow → `bot/handlers/report.py`:
  - ConversationHandler state machine (6 states), feedback handler, `/recent`
- [x] **10.2.9** Extract admin command handlers → `bot/handlers/admin.py`:
  - `admin_only` decorator, `/admin` router, all admin subcommands
- [x] **10.2.10** Slim down `bot/main.py` to application wiring only:
  - Application creation, handler registration, lifecycle hooks, `main()` entrypoint
  - Result: ~260 lines (wiring + backward-compat re-exports)
- [x] **10.2.11** Verify all 217 existing tests pass after refactor (zero functional changes)
- [x] **10.2.12** CI unchanged — backward-compat re-exports preserve import paths

#### 10.3 Add `/feedback` Command (User → Admin)

- [x] **10.3.1** `/feedback <message>` — relay user text to all admin users:
  - Forward message with sender info (user ID, username, badge, report count)
  - Confirm to user that feedback was sent
  - Rate limit: 1 feedback message per user per hour (prevent spam)
- [x] **10.3.2** Log to `admin_actions` (action: `user_feedback`, target: user ID, detail: message preview)
- [x] **10.3.3** Database method: `count_user_feedback_since()` for rate limiting
- [x] **10.3.4** Add to `/help` output and `/start` welcome message
- [x] **10.3.5** Tests for feedback command, rate limiting, and admin relay

#### 10.4 Add `/admin announce` (Admin → Users)

- [x] **10.4.1** `/admin announce all <message>` — broadcast to all registered users:
  - Confirmation step: show message preview + recipient count, require explicit confirm
  - Rate-limited delivery (20 messages/second to respect Telegram API limits)
  - Delivery report: sent count, failed count, blocked users cleaned up
  - Log to `admin_actions` with message preview and delivery stats
- [x] **10.4.2** `/admin announce zone <zone_name> <message>` — broadcast to subscribers of a specific zone:
  - Same confirmation + delivery report pattern
  - Zone name validated against `ZONES` dict (case-insensitive, greedy match)
- [x] **10.4.3** Database methods: `get_all_user_ids()` (all registered users), existing `get_zone_subscribers()` reused for zone-scoped
- [x] **10.4.4** Update `/admin` help text and `ADMIN_COMMANDS_HELP` / `ADMIN_COMMANDS_DETAILED` dicts
- [x] **10.4.5** Tests for announce command, confirmation flow, delivery, and audit logging

#### 10.5 UX Discoverability

- [x] **10.5.1** Richer `/start` menu — `InlineKeyboardMarkup` with quick-action buttons:
  - "Subscribe to Zones" → opens region selection
  - "Report a Sighting" → /report instructions
  - "Recent Sightings" → /recent instructions
  - "My Stats" → /mystats instructions
  - "Send Feedback" → /feedback instructions
  - "Help" → /help summary
- [x] **10.5.2** Post-action contextual prompts — after zone subscription Done, suggest /subscribe, /report, /recent
- [x] **10.5.3** Update `/help` to include `/feedback` and describe `/start` as "Main menu with quick actions"
- [x] **10.5.4** Tests for start menu rendering and callback routing

---

### Phase 11: Admin — Operations (Replanned)

Operational tools for managing runtime state, data lifecycle, and safe live operations.

**Execution order (dependency-aware):** **11.3 Runtime Configuration → 11.1 Maintenance Mode → 11.2 Data Management**.

#### 11.3 Runtime Configuration (must land first)

- [x] **11.3.1** Add `config_overrides` table via Alembic migration `004_phase11_config_overrides.py`:
  ```sql
  config_overrides (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_by BIGINT NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
  )
  ```
- [x] **11.3.2** Introduce a typed runtime-settings accessor (single source of truth) so handlers/jobs stop reading module-level constants directly.
- [x] **11.3.3** Add strict allowlist for mutable keys (`MAX_REPORTS_PER_HOUR`, `DUPLICATE_WINDOW_MINUTES`, `DUPLICATE_RADIUS_METERS`, `SIGHTING_EXPIRY_MINUTES`, `SIGHTING_RETENTION_DAYS`, `FEEDBACK_WINDOW_HOURS`, `MAX_WARNINGS`, `MAINTENANCE_MODE`, `MAINTENANCE_MESSAGE`).
- [x] **11.3.4** Forbid runtime mutation of sensitive/static keys (`TELEGRAM_BOT_TOKEN`, `DATABASE_URL`, `DATABASE_PRIVATE_URL`, `ADMIN_USER_IDS`, webhook ports/URLs).
- [x] **11.3.5** `/admin config` and `/admin config <key> <value>` must validate and cast values by key type (int/bool/float/str) and fail-fast on invalid input.
- [x] **11.3.6** Audit log must store old value → new value, actor, and timestamp.
- [x] **11.3.7** `/admin config reset <key>` removes override and confirms effective default value. `reset_override()` accepts `actor_id` for audit traceability.

#### 11.1 Maintenance Mode (built on 11.3)

- [x] **11.1.1** `/admin maintenance on [message]` sets persisted maintenance flag/message in `config_overrides`.
- [x] **11.1.2** `/admin maintenance off` clears maintenance override and resumes normal operation.
- [x] **11.1.3** Define ConversationHandler behavior explicitly: active `/report` sessions are cancelled with a single combined maintenance + cancellation message and cleanup. Safe for `callback_query.message` being `None`.
- [x] **11.1.4** During maintenance, user commands + inline queries are blocked; admin commands remain available.
- [x] **11.1.5** Scheduled jobs are soft-paused by flag check inside each job (no scheduler pause API assumption).
- [x] **11.1.6** `GET /health` returns degraded maintenance status (`status: "degraded"`, maintenance flag/message).
- [x] **11.1.7** `/admin stats` includes maintenance status so all admins can see current mode.
- [x] **11.1.8** Optional pre-maintenance broadcast: `/admin maintenance on --announce <msg>` preview + confirm flow.

#### 11.2 Data Management

- [x] **11.2.1** `/admin purge sightings [days]` (ad-hoc/manual) must be explicitly separate from automated retention cleanup job.
- [x] **11.2.2** Add `/admin purge sightings zone <zone_name> [days]` for spam/retirement operations.
- [x] **11.2.3** `/admin purge user <user_id>` must remove: user row, subscriptions, sightings, feedback received, feedback given, bans, warnings, and admin-action references where required by policy. Config overrides are preserved (shared state, not user-owned).
- [x] **11.2.4** Purging feedback **given by** a user must recalculate affected sighting counters (`feedback_positive`/`feedback_negative`) transactionally.
- [x] **11.2.5** `/admin export stats` defaults to CSV (operator-friendly), optional JSON, and excludes personal data by default.
- [x] **11.2.6** Every purge/export command requires preview + explicit confirm.
- [x] **11.2.7** Zone-scoped purge uses case-insensitive zone matching (consistent with `/admin zone`).

#### 11.4 Testing (required before phase close)

- [x] **11.4.1** Unit tests for runtime setting casting/validation and allowlist enforcement.
- [x] **11.4.2** Integration tests for maintenance gating (commands, report conversation cancellation, inline blocking, job skip behavior).
- [x] **11.4.3** Integration tests for purge flows, feedback counter recalculation, and export file generation.
- [x] **11.4.4** Migration tests for `004_phase11_config_overrides.py`.

---

### Phase 11.5: Tech Debt & Hardening (Pre-Growth) ✅

Fix structural risks and quality gaps identified in the 2026-02-16 code review before building growth features on top. Ordered by dependency: correctness bugs first, then architecture, then test infra.

**Status:** COMPLETED (2026-02-20). All items implemented, tested (335 tests), CI gates passing (ruff + mypy + pytest).

**Why this phase exists:** Phases 12–14 add user-facing complexity (referrals, leaderboards, inline mode, i18n). Each of these amplifies existing weaknesses — sequential broadcast breaks under leaderboard fanout, untyped dicts cause silent bugs when new columns are added, and the God Objects make safe iteration slower. Fixing foundations first reduces total cost.

#### 11.5.1 Fix `/start` Menu — Buttons Must Do What They Promise (UX bug) ✅

The `/start` menu is the first thing every new user sees. Currently 5 of 6 buttons just say "Use /command" instead of performing the action. This must be fixed before any growth push.

**Implementation approach: Hybrid Edit-in-Place + Back Button Navigation (Approach C)**

Uses two complementary patterns based on each button's interaction model:
- **Read-only buttons** (recent, mystats, help): Edit the `/start` message in-place with full content + `<< Back to Menu` button. Keeps interaction within a single message, avoids chat clutter.
- **Multi-step flow** (report): Add `CallbackQueryHandler` as a `ConversationHandler` entry point. Deletes the `/start` menu message, sends a new message with location/manual keyboard. Enters the existing 6-state report flow.
- **Text input** (feedback): Edit the `/start` message with clear `/feedback <msg>` instructions and example + `<< Back to Menu` button. Avoids new state management; keeps the proven single-command pattern.

This matches the UX patterns used by @BotFather and top-tier Telegram bots: settings/info edited in-place, multi-step flows spawn new messages, every screen has a back button.

##### Architecture

**Text builder extraction (DRY):** Extract display logic from `recent()`, `mystats()`, `help_command()` into pure async functions (`_build_recent_text()`, `_build_mystats_text()`, `_build_help_text()`) that return strings. Both the `/command` handlers and `/start` button callbacks call the same text builders but deliver through different channels (`reply_text` vs `edit_message_text`).

**Back button routing:** A single `back_to_start_menu()` callback handler (triggered by `callback_data="start_back"`) re-renders the original `/start` menu text + 6-button keyboard via `edit_message_text`. Reused by all read-only screens.

**Report entry point:** `report_from_start()` is registered as a `CallbackQueryHandler(pattern="^start_report$")` entry point in the existing `report_conv` ConversationHandler. Uses `per_message=False` (current default), `allow_reentry=True`, and anchored pattern. A guard in `handle_callback()` skips `start_report` to prevent double-routing (ConversationHandler is registered first and takes priority).

##### Callback data routing table

| Button | `callback_data` | Handler | Action | Next state |
|--------|---|---|---|---|
| Subscribe | `start_subscribe` | `handle_start_menu()` | Show regions | Zone selection flow |
| Report | `start_report` | `report_from_start()` (conv entry) | Delete menu, show method choice | `CHOOSING_METHOD` |
| Recent | `start_recent` | `handle_start_menu()` | Edit with sightings + back btn | Await back |
| My Stats | `start_mystats` | `handle_start_menu()` | Edit with stats + back btn | Await back |
| Feedback | `start_feedback` | `handle_start_menu()` | Edit with instructions + back btn | Await back |
| Help | `start_help` | `handle_start_menu()` | Edit with help text + back btn | Await back |
| Back | `start_back` | `back_to_start_menu()` | Re-render /start menu | Menu |

##### Implementation steps

- [x] **11.5.1.1** Extract text builders into `bot/handlers/user.py`:
  - `_build_recent_text(user_id: int) -> str` — reuse in `recent()` and `start_recent` callback
  - `_build_mystats_text(user_id: int) -> str` — reuse in `mystats()` and `start_mystats` callback
  - `_build_help_text() -> str` — reuse in `help_command()` and `start_help` callback
  - `_build_back_button() -> InlineKeyboardMarkup` — single `<< Back to Menu` button (`callback_data="start_back"`)
  - Refactor existing `recent()`, `mystats()`, `help_command()` to call these builders (zero behavior change)
- [x] **11.5.1.2** Add `back_to_start_menu()` handler in `bot/handlers/user.py`:
  - Triggered by `callback_data="start_back"`
  - Re-renders the original `/start` welcome text + 6-button keyboard via `query.edit_message_text()`
  - Clears `context.user_data["awaiting_feedback_from_start"]` if set
- [x] **11.5.1.3** Update `handle_start_menu()` for read-only buttons:
  - `start_recent`: call `_build_recent_text(user_id)`, edit message with result + back button
  - `start_mystats`: call `_build_mystats_text(user_id)`, edit message with result + back button (parse_mode="Markdown")
  - `start_help`: call `_build_help_text()`, edit message with result + back button (parse_mode="Markdown")
  - `start_feedback`: edit message with clear `/feedback <msg>` instructions, usage example, and back button
- [x] **11.5.1.4** Add `report_from_start()` in `bot/handlers/report.py`:
  - `await query.answer()`, delete the `/start` menu message, send new message with location/manual keyboard
  - Return `CHOOSING_METHOD` to enter the ConversationHandler state machine
  - Add as `CallbackQueryHandler(report_from_start, pattern="^start_report$")` entry point in `report_conv` (in `main.py`)
  - Add guard in `handle_callback()` to skip `start_report` pattern (prevent double-routing)
  - Add `allow_reentry=True` to `report_conv` so re-pressing the button works
- [x] **11.5.1.5** Add `start_back` routing in `main.py`:
  - Route `start_back` callback to `back_to_start_menu()` in `handle_callback()`
- [x] **11.5.1.6** Tests:
  - Text builder unit tests: no zones, no sightings, with sightings, no reports, with reports, help text content
  - Callback routing tests: each button edits message correctly, back button restores menu
  - Report from start: deletes menu, shows method choice, enters ConversationHandler
  - Guard test: `handle_callback` does not intercept `start_report` (ConversationHandler owns it)
- [x] **11.5.1.7** Update documentation:
  - `parking_warden_bot_spec.md` Flow 1: document new button behaviors (edit-in-place, back button, report entry)
  - `README.md`: update `/start` command description
  - `APP_REVIEW.md`: mark `/start` menu buttons as planned/fixed

##### Edge cases

- **Message length:** `_build_recent_text()` truncates at 3,500 chars (safety margin before 4,096 limit) with "... truncated" marker
- **"Message not modified" error:** Catch `BadRequest` when back button re-renders identical menu content
- **Report menu deletion:** `delete_message()` wrapped in try/except — continue if message already deleted
- **Maintenance mode:** All new handlers use existing `@maintenance_check` / `@maintenance_conversation_check` decorators
- **Ban enforcement:** Existing manual ban check in `handle_start_menu()` covers all callback paths (11.5.2 will fix this properly with decorator)

#### 11.5.2 Fix `ban_check` Decorator — Callback Query Safety (Bug) ✅

`ban_check` in `moderation.py` assumes `update.message` exists, which crashes on callback queries. The `handle_start_menu` function manually works around this. This split enforcement is a bug source.

- [x] **11.5.2.1** Rewrite `ban_check` to detect whether the update is a message or callback query, and reply via the correct path (`update.message.reply_text` vs `update.callback_query.answer`/`edit_message_text`).
- [x] **11.5.2.2** Remove the manual `is_banned()` check in `handle_start_menu` — the decorator should handle it.
- [x] **11.5.2.3** Add test cases for `ban_check` on both message-based and callback-query-based updates.

#### 11.5.3 Fix Feedback Rate Limiting — Decouple from Audit Log (Bug) ✅

`count_user_feedback_since()` queries `admin_actions WHERE action = 'user_feedback'`. If audit logs are ever purged, rate limits silently break.

- [x] **11.5.3.1** Add a dedicated `user_feedback` table (or a `user_rate_limits` table with `(user_id, action, timestamp)` schema) for rate limiting.
- [x] **11.5.3.2** Migrate `count_user_feedback_since()` to query the new table. Keep the `admin_actions` audit log write for traceability.
- [x] **11.5.3.3** Add Alembic migration `005_user_feedback_table.py`.
- [x] **11.5.3.4** Update `/admin purge user` to also delete from the new table.

#### 11.5.4 Fix GDPR Purge — Scrub PII from `admin_actions.detail` (Compliance) ✅

`purge_user_data()` NULLs `admin_actions.target` but leaves PII in `detail` (e.g., "Banned user: @john_doe for spamming").

- [x] **11.5.4.1** Change `purge_user_data()` to also NULL the `detail` column on matching `admin_actions` rows (where `target` matched the purged user ID).
- [x] **11.5.4.2** Add a test that verifies both `target` and `detail` are scrubbed after purge.

#### 11.5.5 Fix Callback Data Validation (Defensive) ✅

Callback data like `feedback_pos_{id}` and `zone_{name}` is parsed by `str.replace()` with no validation. Malformed data fails silently.

- [x] **11.5.5.1** Add a `parse_callback_data(prefix, data)` helper in `bot/utils.py` that strips the prefix and validates the remainder (UUID format for sighting IDs, valid zone name for zones).
- [x] **11.5.5.2** Apply to `handle_feedback`, `handle_zone_selection`, `handle_unsubscribe_callback`, `handle_report_zone`, and `handle_callback` in `main.py`.
- [x] **11.5.5.3** Return early with `query.answer("Invalid action", show_alert=True)` on validation failure instead of silent breakage.

#### 11.5.6 Fix Health Check Port Collision (Ops bug) ✅

When `WEBHOOK_URL` is set and `HEALTH_CHECK_PORT` is not, both webhook and health check bind to `PORT` (default 8443).

- [x] **11.5.6.1** Change `config.py` so `HEALTH_CHECK_PORT` defaults to `8080` unconditionally, not `$PORT`. Only use `HEALTH_CHECK_PORT` env var if explicitly set.
- [x] **11.5.6.2** Update README Configuration table to reflect the fixed default.
- [x] **11.5.6.3** Add a startup warning in `main.py` if `HEALTH_CHECK_PORT == PORT` and `WEBHOOK_URL` is set.

#### 11.5.7 Refactor Broadcast — Bounded Concurrency + Retry (Reliability) ✅

`broadcast_alert()` sends one message at a time with no retry. This is the biggest reliability risk for scale.

- [x] **11.5.7.1** Rewrite `broadcast_alert()` to use `asyncio.Semaphore(20)` for bounded concurrency (respects Telegram's ~30 msg/sec limit with safety margin).
- [x] **11.5.7.2** Add single retry with 1s backoff on transient `telegram.error.TimedOut` / `telegram.error.RetryAfter` errors.
- [x] **11.5.7.3** Track and return structured delivery results: `{sent: int, failed: int, blocked: list[int], retried: int}`.
- [x] **11.5.7.4** Apply the same pattern to `/admin announce` broadcasts.
- [x] **11.5.7.5** Add tests for concurrency limiting and retry behavior using mocked bot.

#### 11.5.8 Remove `main.py` Re-Export Shim (Code smell) ✅

`main.py` re-exports 30+ symbols with `# noqa: F401` so tests can `from bot.main import ...`. Tests should import from the actual modules.

- [x] **11.5.8.1** Update `tests/test_unit.py` to import from `bot.utils`, `bot.zones`, `bot.ui.messages`.
- [x] **11.5.8.2** Update `tests/test_phase7.py` to import `_init_sentry` from `bot.main` (this one is legitimate — it lives in `main.py`).
- [x] **11.5.8.3** Update `tests/test_phase8.py` to import from `bot.handlers.admin` and `bot.zones`.
- [x] **11.5.8.4** Update `tests/test_phase9.py` to import from `bot.services.moderation` and `bot.handlers.admin`.
- [x] **11.5.8.5** Remove all re-export lines and `# noqa: F401` comments from `main.py`. Only keep imports that `main.py` itself uses.
- [x] **11.5.8.6** Verify all tests pass with the new import paths.

#### 11.5.9 Introduce Typed Data Models (Architecture) ✅

Replace raw `dict[str, Any]` returns from database methods with `TypedDict` classes. Full dataclass/ORM migration is overkill for this stage; `TypedDict` is the minimum-cost fix that adds type safety without changing runtime behavior.

- [x] **11.5.9.1** Create `bot/models.py` with `TypedDict` definitions: `SightingRow`, `UserRow`, `FeedbackRow`, `AdminActionRow`, `BannedUserRow`, `ConfigOverrideRow`, `GlobalStatsRow`.
- [x] **11.5.9.2** Update `database.py` return type annotations to use the typed dicts.
- [x] **11.5.9.3** Verify mypy passes with the new types (catches any `dict["wrong_key"]` bugs).

#### 11.5.10 Carve `database.py` into Repository Modules (Architecture) — DEFERRED

Split the 1,025-line God Object by domain responsibility. This is the prerequisite for safe iteration on Phase 12+ features.

- [x] **11.5.10.1** Extract `bot/repositories/subscriptions.py` — `get_subscriptions`, `add_subscription`, `remove_subscription`, `clear_subscriptions`, `get_zone_subscribers`, `get_subscriber_count`.
- [x] **11.5.10.2** Extract `bot/repositories/sightings.py` — `add_sighting`, `get_sighting`, `get_recent_sightings_for_zones`, `find_recent_zone_sightings`, `count_reports_since`, `get_oldest_report_since`, `cleanup_old_sightings`, `delete_sighting`, `flag_sighting`, `get_flagged_sightings`, `get_total_sightings_count`, `purge_sightings_older_than`.
- [x] **11.5.10.3** Extract `bot/repositories/users.py` — `ensure_user`, `get_user_stats`, `increment_report_count`, `get_user_details`, `get_user_by_username`, `get_user_recent_sightings`, `get_user_subscriptions_list`, `ban_user`, `unban_user`, `is_banned`, `get_banned_users`, `get_user_warnings`, `increment_warnings`, `reset_warnings`, `get_all_user_ids`, `purge_user_data`.
- [x] **11.5.10.4** Extract `bot/repositories/feedback.py` — `get_user_feedback`, `set_feedback`, `apply_feedback`, `update_feedback_counts`, `calculate_accuracy`, `get_user_feedback_totals`, `get_low_accuracy_reporters`, `count_user_feedback_since`.
- [x] **11.5.10.5** Extract `bot/repositories/admin.py` — `log_admin_action`, `get_admin_log`, `get_global_stats`, `get_top_zones_by_subscribers`, `get_top_zones_by_sightings`, `get_zone_details`, `get_zone_top_reporters`, `get_zone_recent_sightings`, `export_stats`.
- [x] **11.5.10.6** Extract `bot/repositories/config.py` — `get_config_override`, `get_all_config_overrides`, `upsert_config_override`, `delete_config_override`.
- [x] **11.5.10.7** Keep `database.py` as the connection manager + `Database` facade that delegates to repository modules (preserving the existing `get_db().method()` API for now to avoid a massive handler rewrite).
- [x] **11.5.10.8** Verify all tests pass — zero functional change.

#### 11.5.11 Split `admin.py` into Subcommand Modules (Architecture) — DEFERRED (already split)

The 1,184-line admin handler grows with every phase. Split by responsibility seam.

- [x] **11.5.11.1** Extract `bot/handlers/admin_moderation.py` — `_admin_ban`, `_admin_unban`, `_admin_banlist`, `_admin_warn`, `_admin_delete`, `_admin_review`.
- [x] **11.5.11.2** Extract `bot/handlers/admin_ops.py` — `_admin_config`, `_admin_maintenance`, `_admin_purge`, `_admin_export`.
- [x] **11.5.11.3** Extract `bot/handlers/admin_announce.py` — `_admin_announce`.
- [x] **11.5.11.4** Keep `admin.py` as the router: `admin_only` decorator, `admin_command()` dispatcher, `ADMIN_COMMANDS_HELP`, `ADMIN_COMMANDS_DETAILED`, `_admin_stats`, `_admin_user`, `_admin_zone`, `_admin_log`, `_admin_help`.
- [x] **11.5.11.5** Verify all tests pass — zero functional change.

#### 11.5.12 Add Handler-Level Tests (Quality) ✅

Zero handler tests is the single biggest quality gap. Add mocked-update tests for critical paths.

- [x] **11.5.12.1** Create `tests/test_handlers_user.py` — mock `Update`/`Context` objects. Test: `/start` renders menu, `/subscribe` shows regions, `/myzones` shows subscriptions, `/help` output, `/feedback` relays to admins, `/feedback` rate limit, banned user rejection.
- [x] **11.5.12.2** Create `tests/test_handlers_report.py` — test ConversationHandler state transitions: report entry → location → description → confirm → broadcast. Test: rate limiting rejection, duplicate detection rejection, cancel flow, GPS nearest-zone detection.
- [x] **11.5.12.3** Create `tests/test_handlers_admin.py` — test: admin-only rejection, `/admin stats` output, `/admin ban` + notify, `/admin warn` + escalation, `/admin delete` two-step flow, `/admin config` validation.
- [x] **11.5.12.4** Create `tests/test_handlers_callbacks.py` — test: `handle_callback` routing, feedback positive/negative, zone toggle, unsubscribe flow, start menu button routing.
- [x] **11.5.12.5** Add a shared `tests/helpers.py` with `make_update()`, `make_context()`, `make_callback_query()` factory functions for building mock Telegram objects.

#### 11.5.13 Fix SQLite Cleanup Cascade Inconsistency (Code smell) ✅

`cleanup_old_sightings()` manually deletes feedback before sightings despite `ON DELETE CASCADE` being set. Pick one strategy.

- [x] **11.5.13.1** Remove the manual feedback deletion from `cleanup_old_sightings()` — rely on `ON DELETE CASCADE` (already enabled via `PRAGMA foreign_keys=ON`).
- [x] **11.5.13.2** Add a test that verifies cascading delete works correctly for both SQLite and PostgreSQL drivers.

#### 11.5.14 Testing (required before phase close) ✅

- [x] **11.5.14.1** All 11.5.1–11.5.13 items must have associated tests before marking complete.
- [x] **11.5.14.2** CI must pass: `ruff check . && ruff format --check . && mypy bot/ config.py && pytest`.
- [x] **11.5.14.3** Update `IMPROVEMENTS.md` File Reference with new files and line counts.

---

### Phase 12: Growth Features (Re-scoped)

**Depends on:** Phase 11.5 (at minimum 11.5.2 ban_check fix, 11.5.7 broadcast concurrency, 11.5.10 database split). Growth features land on top of the hardened base.

Prioritize by value-to-effort and dependency fit:

1. **12.4 Deep linking/referrals** → 2. **12.1 Leaderboards** → 3. **12.2 Inline mode** → 4. **12.3 Activity summary (text-first)** → 5. **12.5 i18n (move to Phase 14)**.

#### 12.4 Deep linking/referrals (first)
- [ ] Add referral schema (`referrals` table or `users.referred_by` + attribution metadata).
- [ ] Dedupe rules: first valid referral only; ignore self-referral and pre-existing users.
- [ ] GDPR linkage: referral data must be purged by `/admin purge user`.
- [ ] Define incentive policy (if any) before implementation.

#### 12.1 Leaderboards
- [ ] Ship as `/leaderboard` command first (avoid scheduled broadcast complexity in v1).
- [ ] Define windows explicitly: rolling 7-day + all-time.
- [ ] Add minimum threshold and privacy opt-out support.
- [ ] Add DB query methods for time-windowed ranking and accuracy tie-breaks.

#### 12.2 Inline mode
- [ ] Define `InlineQueryResultArticle` format and redaction policy (no reporter identity, no precise GPS by default).
- [ ] Add inline-specific maintenance + ban checks (requires 11.5.2 `ban_check` fix for callback/query safety).
- [ ] Use Telegram inline query caching (`cache_time`) and throttling controls.

#### 12.3 Replace heatmaps with text-first activity summaries
- [ ] Implement `/activity <zone?>` with hourly/day-of-week summaries (80/20 value without image rendering stack).
- [ ] Keep SQL dialect differences explicit (`strftime` SQLite vs `EXTRACT` PostgreSQL) behind DB abstraction.

#### 12.5 i18n (move out)
- [ ] Move to **Phase 14** due to scope (string extraction, locale files, language preference storage, `/language` UX).

#### 12.6 Testing
- [ ] Add tests per feature before marking complete (referrals, leaderboard windows, inline redaction/gating, activity summaries).

---

### Phase 13: Monetisation (Split into separate validated workstreams)

Do not implement as one blended phase. Treat each item as its own mini-program with validation gates.

#### 13.A Freemium
- [ ] Define product policy first: free tier limits, grandfathering for existing users, trial rules, rollback plan.
- [ ] Add schema (`users.is_premium`, `premium_expires_at`, billing metadata).
- [ ] Integrate Telegram Payments + provider and write compliance checklist (SG legal/tax/e-commerce review).

#### 13.B Sponsored alerts
- [ ] Build sponsor ops workflow (submission, moderation approval, scheduling, targeting, frequency cap).
- [ ] Add hard separation/labeling so sponsored content cannot be confused with safety alerts.
- [ ] Provide user opt-out and enforce maximum ad frequency.

#### 13.C Business API
- [ ] Treat as separate product with dedicated API surface, auth, rate limits, and infrastructure.
- [ ] Complete demand validation before engineering build.

#### 13.D Monetisation validation gates
- [ ] Require baseline KPIs (active users, retention, false-alarm rate, delivery success) before launch.
- [ ] Run limited pilot and review trust impact before broad rollout.

---

### Phase 14: Internationalization (i18n)

Moved from Phase 12 due to scope and cross-cutting impact.

- [ ] Extract user-facing strings into translation keys (handlers, services, UI builders, admin messages).
- [ ] Choose localization format and loader (e.g., JSON/gettext) with fallback behavior.
- [ ] Add user language preference persistence (`users.language` or dedicated profile table).
- [ ] Add `/language` command and onboarding language selection.
- [ ] Provide baseline locales: English (`en`) and Simplified Chinese (`zh`).
- [ ] Ensure all new features after Phase 14 are localization-ready by default.
- [ ] Add i18n test coverage (key completeness, fallback, selected-language rendering).

---

## Admin Command Reference (Phases 8–11)

Quick reference for all admin commands once fully implemented.

| Command | Phase | Description |
|---------|-------|-------------|
| `/admin` | 8.2 | List all admin commands |
| `/admin help <cmd>` | 8.2 | Detailed usage for a command |
| `/admin stats` | 8.3 | Global statistics dashboard |
| `/admin user <id>` | 8.4 | Look up user details and activity |
| `/admin zone <name>` | 8.4 | Look up zone activity and stats |
| `/admin log [count]` | 8.5 | View recent admin actions |
| `/admin ban <id> [reason]` | 9.1 | Ban a user |
| `/admin unban <id>` | 9.1 | Unban a user |
| `/admin banlist` | 9.1 | List all banned users |
| `/admin delete <sighting_id>` | 9.2 | Delete a sighting |
| `/admin review` | 9.2 | View flagged sightings queue |
| `/admin warn <id> [msg]` | 9.3 | Warn a user |
| `/admin announce all <msg>` | 10.4 | Announce to all users |
| `/admin announce zone <z> <msg>` | 10.4 | Announce to zone subscribers |
| `/admin maintenance on\|off` | 11.1 | Toggle maintenance mode |
| `/admin purge sightings [days]` | 11.2 | Clean up old sightings |
| `/admin purge user <id>` | 11.2 | Delete all user data (GDPR) |
| `/admin export stats` | 11.2 | Export stats as CSV/JSON |
| `/admin config` | 11.3 | View runtime settings |
| `/admin config <key> <val>` | 11.3 | Adjust a setting at runtime |
| `/admin config reset <key>` | 11.3 | Reset setting to default |

## User Command Reference (Phase 10+)

| Command | Phase | Description |
|---------|-------|-------------|
| `/feedback <message>` | 10.3 | Send feedback to bot admins |

## Database Changes (Phases 8–11)

| Change | Phase | Status | Description |
|--------|-------|--------|-------------|
| New table: `admin_actions` | 8.5 | ✅ Done | Audit log for all admin operations |
| New table: `banned_users` | 9.1 | ✅ Done | Banned user records with reason and banning admin |
| New column: `sightings.flagged` | 9.2 | ✅ Done | Integer flag for moderation queue (0/1) |
| New column: `users.warnings` | 9.3 | ✅ Done | Warning count per user (integer, default 0) |
| New method: `count_user_feedback_since()` | 10.3 | ✅ Done | Rate limiting for `/feedback` command (queries `admin_actions`) |
| New method: `get_all_user_ids()` | 10.4 | ✅ Done | Fetch all registered user IDs for broadcast |
| New table: `config_overrides` | 11.3 | ✅ Done | Runtime configuration overrides |

## Environment Variables Added (Phase 7+)

| Variable | Phase | Description | Default |
|----------|-------|-------------|---------|
| `WEBHOOK_URL` | 7.1 | Public URL for webhook mode (omit for polling) | — |
| `PORT` | 7.1 | Webhook listener port | `8443` |
| `HEALTH_CHECK_ENABLED` | 7.2 | Enable/disable health check server | `true` |
| `HEALTH_CHECK_PORT` | 7.2 | Health check server port | `$PORT` or `8080` |
| `LOG_FORMAT` | 7.3 | Logging format: `text` or `json` | `text` |
| `SENTRY_DSN` | 7.5 | Sentry error tracking DSN | — |
| `ADMIN_USER_IDS` | 8.1 | Comma-separated admin Telegram IDs | `""` (empty) |
| `MAX_WARNINGS` | 9.3 | Warnings before auto-ban | 3 |

---

## File Reference

| File | Lines | Purpose |
|------|-------|---------|
| `bot/main.py` | ~275 | Application wiring: handler registration, lifecycle hooks, `main()` + backward-compat re-exports |
| `bot/database.py` | ~1025 | Dual-driver database abstraction (SQLite/PostgreSQL) including admin + moderation + Phase 10–11 queries |
| `bot/zones.py` | ~200 | Zone data: `ZONES` dict (80 zones, 6 regions), `ZONE_COORDS` coordinate table |
| `bot/utils.py` | ~70 | Pure helpers: `haversine_meters`, `get_reporter_badge`, `get_accuracy_indicator`, `generate_sighting_id`, `sanitize_description`, `SGT` |
| `bot/handlers/user.py` | ~494 | User commands: `/start`, `/subscribe`, `/unsubscribe`, `/myzones`, `/help`, `/mystats`, `/share`, `/feedback` |
| `bot/handlers/report.py` | ~644 | Report flow: 6-state ConversationHandler, feedback handler, `/recent` |
| `bot/handlers/admin.py` | ~1184 | Admin system: `admin_only` decorator, `/admin` router, all subcommands incl. announce, config, maintenance, purge, export |
| `bot/models.py` | ~100 | TypedDict data models for all DB row types (Phase 11.5) |
| `bot/services/moderation.py` | ~55 | Moderation: `ban_check` decorator (callback-safe), `_check_auto_flag()` |
| `bot/services/notifications.py` | ~108 | Notifications: `broadcast_alert()`, `broadcast_message()` with bounded concurrency + retry |
| `bot/services/maintenance.py` | ~66 | Maintenance-mode gating utilities and decorators |
| `bot/services/runtime_settings.py` | ~133 | DB-backed runtime config access with typed casting |
| `bot/ui/keyboards.py` | ~22 | Keyboard builders: `build_zone_keyboard()` |
| `bot/ui/messages.py` | ~48 | Message builders: `build_alert_message()` |
| `bot/handlers/__init__.py` | 1 | Package marker |
| `bot/services/__init__.py` | 1 | Package marker |
| `bot/ui/__init__.py` | 1 | Package marker |
| `bot/health.py` | ~83 | Health check HTTP server (asyncio-based, `/health` endpoint) |
| `bot/logging_config.py` | ~67 | Structured logging configuration (text/JSON modes) |
| `bot/__init__.py` | 1 | Package marker |
| `config.py` | ~60 | Environment config and bot settings (Phases 1–11, incl. `MAX_WARNINGS`, maintenance mode) |
| `pyproject.toml` | ~80 | Project metadata, dependencies, tool configs (pytest/ruff/mypy) |
| `requirements.txt` | 5 | Runtime dependencies (for platforms that don't use pyproject.toml) |
| `.env.example` | ~32 | Template for environment variables (including Phase 9 additions) |
| `alembic.ini` | ~40 | Alembic migration framework configuration |
| `alembic/env.py` | ~50 | Alembic environment (reads DATABASE_URL from config.py) |
| `alembic/script.py.mako` | ~25 | Alembic migration script template |
| `alembic/versions/001_initial_schema.py` | ~80 | Baseline migration matching create_tables() |
| `alembic/versions/002_admin_actions_table.py` | ~40 | Phase 8 migration: admin_actions audit log table |
| `alembic/versions/003_phase9_user_management.py` | ~45 | Phase 9 migration: banned_users table, flagged/warnings columns |
| `alembic/versions/004_phase11_config_overrides.py` | ~40 | Phase 11 migration: config_overrides table |
| `alembic/versions/005_timestamptz.py` | ~52 | Phase 11 migration: TIMESTAMP to TIMESTAMPTZ |
| `alembic/versions/006_user_rate_limits.py` | ~35 | Phase 11.5 migration: user_rate_limits table |
| `tests/conftest.py` | ~23 | Shared test fixtures (fresh SQLite DB per test) |
| `tests/helpers.py` | ~68 | Shared handler test helpers: make_update, make_callback_update, make_mock_db |
| `tests/test_unit.py` | ~370 | Unit tests for pure functions, callback data validation, zone data integrity |
| `tests/test_database.py` | ~640 | Database integration tests (CRUD, queries, transactions, cascade delete) |
| `tests/test_phase7.py` | ~292 | Phase 7 tests: health check, logging, config, Sentry |
| `tests/test_phase8.py` | ~627 | Phase 8 tests: admin auth, stats, lookup, audit log |
| `tests/test_phase9.py` | ~798 | Phase 9 tests: banning, moderation, warnings, auto-flag, escalation |
| `tests/test_phase10.py` | ~687 | Phase 10 tests: feedback, announce, start menu, UX |
| `tests/test_phase11_runtime_config.py` | ~225 | Phase 11 tests: runtime config casting, validation, allowlist |
| `tests/test_phase11_maintenance.py` | ~188 | Phase 11 tests: maintenance gating, conversation cancellation |
| `tests/test_phase11_data_management.py` | ~263 | Phase 11 tests: purge flows, feedback counter repair, export |
| `tests/test_phase11_migration.py` | ~37 | Phase 11 tests: Alembic migration 004 |
| `tests/test_handlers_user.py` | ~280 | Phase 11.5 tests: handler-level user command & start menu tests |
| `tests/test_handlers_callbacks.py` | ~140 | Phase 11.5 tests: callback routing, report entry, feedback validation |
| `.github/workflows/ci.yml` | ~45 | GitHub Actions CI pipeline (lint + typecheck + test) |
| `parking_warden_bot_spec.md` | ~700 | Full product specification (user flows, message formats, reputation, zones) |
| `README.md` | ~300 | Operator documentation (setup, config, deployment, commands) |
| `IMPROVEMENTS.md` | — | This file (code review & improvement plan) |
| `Procfile` | 1 | Heroku-style process declaration |
| `railway.toml` | ~10 | Railway.app deployment config (with health check) |
| `runtime.txt` | 1 | Python version specification (3.10) |

---

*Last updated: 2026-02-20 (Phase 11.5 complete — tech debt hardened, /start menu fixed, broadcast bounded, TypedDict models, 335 tests passing; roadmap aligned through Phase 14)*

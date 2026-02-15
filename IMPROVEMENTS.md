# ParkWatch SG — Code Review & Improvement Plan

## Audit Summary

**Date:** 2026-02-12 (initial), 2026-02-13 (Phase 8 update), 2026-02-14 (Phase 9 update), 2026-02-15 (Phase 10 planning)
**Scope:** Full code review against `parking_warden_bot_spec.md` and `README.md`
**Files reviewed:** `bot/main.py`, `bot/database.py`, `bot/health.py`, `bot/logging_config.py`, `config.py`, `requirements.txt`, `.env.example`

---

## Status: Phases 1–9 Complete, Phase 10 In Progress

Phases 1 through 9 addressed all critical bugs, UX issues, data persistence, robustness gaps, known code defects, established automated testing and CI, hardened the bot for production deployment, added admin foundation with visibility tools, and implemented user management with content moderation. All items below are checked off and verified in the current codebase.

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

## Current State Assessment (2026-02-14)

### What's Working Well

1. **Feature completeness** — All 9 user commands + full admin command suite (12 commands) implemented and functional
2. **ConversationHandler** — Proper 6-state machine with timeout, fallbacks, and `/cancel` support
3. **Database layer** — Clean dual-driver abstraction with WAL mode, connection pooling, parameterized queries
4. **GPS-aware duplicate detection** — Haversine + 200m radius, zone-level fallback
5. **Feedback system** — Transaction-safe, vote changing, self-rating prevention, window expiry
6. **Alert message architecture** — `build_alert_message()` as single source of truth
7. **Blocked user cleanup** — Catches `Forbidden`, removes stale subscriptions
8. **Config externalization** — All tunable values in `config.py` with env var overrides
9. **Timezone-safe datetime** — All `datetime.now(timezone.utc)` throughout codebase
10. **Proper Python packaging** — Runs as `python -m bot.main`, relative imports, no sys.path hacks
11. **Test coverage** — 217 tests (48 unit + 57 integration + 22 infrastructure + 43 admin + 47 moderation) with 100% pass rate
12. **CI pipeline** — Automated lint, type check, and test on every push/PR via GitHub Actions
13. **Code quality** — All ruff lint and format checks pass, mypy type checking clean
14. **Production infrastructure** — Webhook mode, health check endpoint, structured JSON logging, Alembic migrations, Sentry integration
15. **Admin foundation** — Authentication layer, global stats dashboard, user/zone lookup, audit logging with full test coverage
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
- [x] **6.2** Unit tests for pure functions: `haversine_meters` (6 tests), `get_reporter_badge` (8 tests), `get_accuracy_indicator` (7 tests), `sanitize_description` (11 tests), `build_alert_message` (8 tests), `generate_sighting_id` (3 tests), plus zone data integrity checks (5 tests) — **48 unit tests total**
- [x] **6.3** Database integration tests: subscriptions (8), users (5), sightings (5), recent/duplicate detection (7), rate limiting (4), feedback (9), accuracy (7), cleanup (4), feedback counts (2), driver init (6) — **57 integration tests total**
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
- [x] **7.6** Test coverage for all Phase 7 features — 22 new tests: health check server lifecycle (5 tests), JSON formatter (5 tests), setup_logging (4 tests), config validation (6 tests), Sentry init (2 tests) — **127 total tests**

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

- [x] **8.6.1** 43 new tests in `tests/test_phase8.py`: config parsing (6 tests), admin_only decorator (2 tests), audit log DB operations (7 tests), global stats queries (6 tests), user lookup DB methods (9 tests), zone lookup DB methods (6 tests), admin_actions schema (3 tests), admin help constants (2 tests), zone validation (2 tests) — **170 total tests**

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

- [x] **9.4.1** 47 new tests in `tests/test_phase9.py`: ban operations (10 tests), sighting moderation (8 tests), low-accuracy reporters (4 tests), warnings (5 tests), schema validation (4 tests), config (3 tests), ban_check decorator (2 tests), auto-flag logic (4 tests), help text (2 tests), ban integration (3 tests), warning escalation (2 tests) — **217 total tests**

---

### Phase 10: Architecture, UX & Communication

Structural improvements to reduce maintenance debt, close the admin-user communication loop, and improve discoverability. Prioritised based on external code review feedback (2026-02-15).

**Why this phase exists:** `bot/main.py` at 2,278 lines is a monolith that blends command routing, business logic, message rendering, and admin operations. Every subsequent feature added to this file increases maintenance cost and onboarding time. Refactoring first ensures items 10.3–10.5 land as clean, isolated modules. The review also identified missing two-way communication (users cannot reach admins; admins cannot announce to users) and UX that depends too heavily on command literacy.

#### 10.1 Documentation Cleanup

- [x] **10.1.1** Fix README version drift — update stale `1.2.0` references in example output to match `BOT_VERSION = "1.3.0"` (lines 86, 490)
- [x] **10.1.2** Consolidate README and spec — trim `README.md` to operator essentials (setup, deployment, env vars, command reference); move deep product flow details into `parking_warden_bot_spec.md` as the single maintained spec; eliminate duplicated content between the two files
- [ ] **10.1.3** Update file reference table and line counts in IMPROVEMENTS.md after refactor

#### 10.2 Refactor `bot/main.py` into Modules

- [ ] **10.2.1** Extract zone data → `bot/zones.py`:
  - `ZONES` dict (80 zones across 6 regions), `ZONE_COORDS` coordinate table
- [ ] **10.2.2** Extract utility functions → `bot/utils.py`:
  - `haversine_meters()`, `get_reporter_badge()`, `get_accuracy_indicator()`, `generate_sighting_id()`, `sanitize_description()`
- [ ] **10.2.3** Extract UI helpers → `bot/ui/keyboards.py`:
  - `build_zone_keyboard()`, future menu keyboards
- [ ] **10.2.4** Extract message builders → `bot/ui/messages.py`:
  - `build_alert_message()`, future message templates
- [ ] **10.2.5** Extract notification logic → `bot/services/notifications.py`:
  - Broadcast/fanout to zone subscribers, blocked-user cleanup
- [ ] **10.2.6** Extract moderation utilities → `bot/services/moderation.py`:
  - `ban_check` decorator, `_check_auto_flag()`, auto-ban escalation logic
- [ ] **10.2.7** Extract user command handlers → `bot/handlers/user.py`:
  - `/start`, `/subscribe`, `/unsubscribe`, `/myzones`, `/help`, `/mystats`, `/share`
- [ ] **10.2.8** Extract report flow → `bot/handlers/report.py`:
  - ConversationHandler state machine (6 states), feedback handler, `/recent`
- [ ] **10.2.9** Extract admin command handlers → `bot/handlers/admin.py`:
  - `admin_only` decorator, `/admin` router, all admin subcommands
- [ ] **10.2.10** Slim down `bot/main.py` to application wiring only:
  - Application creation, handler registration, lifecycle hooks, `main()` entrypoint
  - Target: <100 lines
- [ ] **10.2.11** Verify all 217 existing tests pass after refactor (zero functional changes)
- [ ] **10.2.12** Update CI if import paths change

#### 10.3 Add `/feedback` Command (User → Admin)

- [ ] **10.3.1** `/feedback <message>` — relay user text to all admin users:
  - Forward message with sender info (user ID, username, badge, report count)
  - Confirm to user that feedback was sent
  - Rate limit: 1 feedback message per user per hour (prevent spam)
- [ ] **10.3.2** Log to `admin_actions` (action: `user_feedback`, target: user ID, detail: message preview)
- [ ] **10.3.3** Database method: `count_user_feedback_since()` for rate limiting
- [ ] **10.3.4** Add to `/help` output and `/start` welcome message
- [ ] **10.3.5** Tests for feedback command, rate limiting, and admin relay

#### 10.4 Add `/admin announce` (Admin → Users)

- [ ] **10.4.1** `/admin announce all <message>` — broadcast to all registered users:
  - Confirmation step: show message preview + recipient count, require explicit confirm
  - Rate-limited delivery (20 messages/second to respect Telegram API limits)
  - Delivery report: sent count, failed count, blocked users cleaned up
  - Log to `admin_actions` with message preview and delivery stats
- [ ] **10.4.2** `/admin announce zone <zone_name> <message>` — broadcast to subscribers of a specific zone:
  - Same confirmation + delivery report pattern
  - Zone name validated against `ZONES` dict (case-insensitive)
- [ ] **10.4.3** Database methods: `get_all_user_ids()` (all registered users), existing `get_zone_subscribers()` reused for zone-scoped
- [ ] **10.4.4** Update `/admin` help text and `ADMIN_COMMANDS_HELP` / `ADMIN_COMMANDS_DETAILED` dicts
- [ ] **10.4.5** Tests for announce command, confirmation flow, delivery, and audit logging

#### 10.5 UX Discoverability

- [ ] **10.5.1** Richer `/start` menu — replace plain text welcome with `InlineKeyboardMarkup` quick-action buttons:
  - "Report a Sighting" → triggers `/report`
  - "Subscribe to Zones" → triggers `/subscribe`
  - "Recent Sightings" → triggers `/recent`
  - "My Stats" → triggers `/mystats`
  - "Send Feedback" → triggers `/feedback`
  - "Help" → triggers `/help`
- [ ] **10.5.2** Post-action contextual prompts — after key actions, suggest logical next steps:
  - After first subscription: "You'll now get alerts for {zone}. Want to subscribe to more zones?"
  - After report confirmation: "Report submitted! View /recent or check /mystats"
- [ ] **10.5.3** Update `/help` to include `/feedback` and describe the `/start` menu
- [ ] **10.5.4** Tests for start menu rendering and callback routing

---

### Phase 11: Admin — Operations

Operational tools for managing system state, data, and runtime configuration.

**Why this phase exists:** Admins need maintenance controls, data management, and runtime tuning without redeployment. Lower priority than communication (Phase 10) but essential for sustained production operation.

#### 11.1 Maintenance Mode

- [ ] **11.1.1** `/admin maintenance on [message]` — enable maintenance mode:
  - All user commands return a "Bot is under maintenance" message (with optional custom text)
  - Admin commands continue to work normally
  - Scheduled jobs (cleanup) are paused
  - Log to `admin_actions`
- [ ] **11.1.2** `/admin maintenance off` — disable maintenance mode, resume normal operation
- [ ] **11.1.3** `MAINTENANCE_MODE` runtime flag (in-memory, resets on restart — or persisted in DB for durability)

#### 11.2 Data Management

- [ ] **11.2.1** `/admin purge sightings [days]` — manually trigger cleanup of sightings older than N days (default: `SIGHTING_RETENTION_DAYS`):
  - Confirmation step showing count of records to be deleted
  - Log to `admin_actions`
- [ ] **11.2.2** `/admin purge user <user_id>` — delete all data for a specific user (sightings, feedback, subscriptions, user record):
  - GDPR/privacy compliance for user data deletion requests
  - Confirmation step required
  - Log to `admin_actions`
- [ ] **11.2.3** `/admin export stats` — generate and send a CSV/JSON summary:
  - User counts, zone subscription counts, sighting counts by zone, feedback summary
  - Sent as a Telegram document attachment

#### 11.3 Runtime Configuration

- [ ] **11.3.1** `/admin config` — display current runtime settings:
  - `MAX_REPORTS_PER_HOUR`, `DUPLICATE_WINDOW_MINUTES`, `DUPLICATE_RADIUS_METERS`
  - `SIGHTING_EXPIRY_MINUTES`, `SIGHTING_RETENTION_DAYS`, `FEEDBACK_WINDOW_HOURS`
  - `MAX_WARNINGS` (from Phase 9.3)
  - Maintenance mode status
- [ ] **11.3.2** `/admin config <key> <value>` — adjust a runtime setting without restart:
  - Store overrides in `config_overrides` table (persisted across restarts)
  - Validate value ranges (e.g., `MAX_REPORTS_PER_HOUR` must be 1–100)
  - Log change to `admin_actions`
- [ ] **11.3.3** `/admin config reset <key>` — revert a setting to its default (delete override)
- [ ] **11.3.4** `config_overrides` table — schema:
  ```sql
  config_overrides (
    key TEXT PK,
    value TEXT NOT NULL,
    updated_by BIGINT NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
  )
  ```

---

### Phase 12: Growth Features

User-facing features to drive engagement and organic growth.

- [ ] **12.1** Weekly/monthly leaderboard (top reporters by report count and accuracy)
- [ ] **12.2** Inline mode — query `@parkwatch_bot Orchard` from any chat to check sightings
- [ ] **12.3** Warden activity heatmaps by time/day
- [ ] **12.4** Deep linking for referral tracking (`/start ref_<user_id>`)
- [ ] **12.5** Multi-language support (i18n) — start with English + Chinese

### Phase 13: Monetisation

- [ ] **13.1** Freemium model (1 zone free, premium for unlimited)
- [ ] **13.2** Sponsored alerts from parking providers
- [ ] **13.3** Business API for fleet managers

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
| New table: `config_overrides` | 11.3 | Planned | Runtime configuration overrides |

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
| `bot/main.py` | ~2150 | All bot logic: user handlers, admin handlers (Phase 8–9), conversation flow, webhook/polling |
| `bot/database.py` | ~850 | Dual-driver database abstraction (SQLite/PostgreSQL) including admin + moderation queries |
| `bot/health.py` | ~75 | Health check HTTP server (asyncio-based, `/health` endpoint) |
| `bot/logging_config.py` | ~65 | Structured logging configuration (text/JSON modes) |
| `bot/__init__.py` | 1 | Package marker |
| `config.py` | ~52 | Environment config and bot settings (Phases 1–9, incl. `MAX_WARNINGS`) |
| `pyproject.toml` | ~80 | Project metadata, dependencies, tool configs (pytest/ruff/mypy) |
| `requirements.txt` | 5 | Runtime dependencies (for platforms that don't use pyproject.toml) |
| `.env.example` | ~32 | Template for environment variables (including Phase 9 additions) |
| `alembic.ini` | ~40 | Alembic migration framework configuration |
| `alembic/env.py` | ~50 | Alembic environment (reads DATABASE_URL from config.py) |
| `alembic/script.py.mako` | ~25 | Alembic migration script template |
| `alembic/versions/001_initial_schema.py` | ~80 | Baseline migration matching create_tables() |
| `alembic/versions/002_admin_actions_table.py` | ~40 | Phase 8 migration: admin_actions audit log table |
| `alembic/versions/003_phase9_user_management.py` | ~45 | Phase 9 migration: banned_users table, flagged/warnings columns |
| `tests/conftest.py` | ~25 | Shared test fixtures (fresh SQLite DB per test) |
| `tests/test_unit.py` | ~340 | Unit tests for pure functions and zone data integrity (48 tests) |
| `tests/test_database.py` | ~600 | Database integration tests (CRUD, queries, transactions) (57 tests) |
| `tests/test_phase7.py` | ~240 | Phase 7 tests: health check, logging, config, Sentry (22 tests) |
| `tests/test_phase8.py` | ~530 | Phase 8 tests: admin auth, stats, lookup, audit log (43 tests) |
| `tests/test_phase9.py` | ~550 | Phase 9 tests: banning, moderation, warnings, auto-flag, escalation (47 tests) |
| `.github/workflows/ci.yml` | ~45 | GitHub Actions CI pipeline (lint + typecheck + test) |
| `parking_warden_bot_spec.md` | ~700 | Full product specification (user flows, message formats, reputation, zones) |
| `README.md` | ~300 | Operator documentation (setup, config, deployment, commands) |
| `IMPROVEMENTS.md` | — | This file (code review & improvement plan) |
| `Procfile` | 1 | Heroku-style process declaration |
| `railway.toml` | ~10 | Railway.app deployment config (with health check) |
| `runtime.txt` | 1 | Python version specification (3.10) |

---

*Last updated: 2026-02-15 (Phase 10 planning)*

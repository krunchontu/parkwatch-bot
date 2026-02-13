# ParkWatch SG — Code Review & Improvement Plan

## Audit Summary

**Date:** 2026-02-12
**Scope:** Full code review against `parking_warden_bot_spec.md` and `README.md`
**Files reviewed:** `bot/main.py` (1437 lines), `bot/database.py` (443 lines), `config.py` (18 lines), `requirements.txt`, `.env.example`

---

## Status: Phases 1–6 Complete

Phases 1 through 6 addressed all critical bugs, UX issues, data persistence, robustness gaps, known code defects, and established automated testing and CI. All items below are checked off and verified in the current codebase.

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

## Current State Assessment (2026-02-13)

### What's Working Well

1. **Feature completeness** — All 9 commands implemented and functional
2. **ConversationHandler** — Proper 6-state machine with timeout, fallbacks, and `/cancel` support
3. **Database layer** — Clean dual-driver abstraction with WAL mode, connection pooling, parameterized queries
4. **GPS-aware duplicate detection** — Haversine + 200m radius, zone-level fallback
5. **Feedback system** — Transaction-safe, vote changing, self-rating prevention, window expiry
6. **Alert message architecture** — `build_alert_message()` as single source of truth
7. **Blocked user cleanup** — Catches `Forbidden`, removes stale subscriptions
8. **Config externalization** — All tunable values in `config.py` with env var overrides
9. **Timezone-safe datetime** — All `datetime.now(timezone.utc)` throughout codebase
10. **Proper Python packaging** — Runs as `python -m bot.main`, relative imports, no sys.path hacks
11. **Test coverage** — 105 tests (48 unit + 57 integration) with 100% pass rate
12. **CI pipeline** — Automated lint, type check, and test on every push/PR via GitHub Actions
13. **Code quality** — All ruff lint and format checks pass, mypy type checking clean

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

### Phase 7: Production Infrastructure

Harden deployment, observability, and schema management for real-world scale. Separated from admin functionality (Phase 8–10) which is a distinct feature domain.

- [ ] **7.1** Webhook mode support (alongside polling) for production deployments
- [ ] **7.2** Health check endpoint (lightweight HTTP server for deployment platform monitoring)
- [ ] **7.3** Structured logging (JSON format) for log aggregation services
- [ ] **7.4** Database migrations with Alembic (versioned schema changes)
- [ ] **7.5** Sentry or equivalent error tracking integration

---

### Phase 8: Admin — Foundation & Visibility

Establish the admin authentication layer, provide global visibility into bot activity, and create the audit infrastructure that all subsequent admin features depend on.

**Why this phase exists:** The bot currently has zero admin functionality. A crowdsourced reporting platform needs operator visibility and control before scaling. Every subsequent admin phase builds on the auth layer and audit table introduced here.

#### 8.1 Admin Authentication & Authorization

- [ ] **8.1.1** `ADMIN_USER_IDS` environment variable — comma-separated list of Telegram user IDs authorized as admins
- [ ] **8.1.2** `admin_only` decorator — wraps admin command handlers; rejects unauthorized users with a generic "Unknown command" response (avoids revealing admin commands exist)
- [ ] **8.1.3** Add `ADMIN_USER_IDS` to `.env.example` and document in README

#### 8.2 Admin Help

- [ ] **8.2.1** `/admin` command — lists all available admin commands with descriptions (only shown to authenticated admins)
- [ ] **8.2.2** `/admin help <command>` — detailed usage for a specific admin command

#### 8.3 Global Statistics Dashboard

- [ ] **8.3.1** `/admin stats` — display key metrics in a single message:
  - Total registered users (all-time)
  - Active users (reported or gave feedback in last 7 days)
  - Total sightings (all-time and last 24 hours)
  - Active subscriptions and unique subscribers
  - Top 5 most-subscribed zones
  - Top 5 most-reported zones (last 7 days)
  - Feedback totals (positive vs negative, overall accuracy rate)
- [ ] **8.3.2** Database methods: `get_global_stats()`, `get_top_zones_by_subscribers()`, `get_top_zones_by_sightings()`, `get_active_user_count()`

#### 8.4 User & Zone Lookup

- [ ] **8.4.1** `/admin user <telegram_id or @username>` — look up a specific user:
  - Registration date, report count, badge, accuracy score
  - Subscribed zones
  - Recent sightings (last 10)
  - Feedback received (positive/negative totals)
  - Ban status (once Phase 9 is implemented)
- [ ] **8.4.2** `/admin zone <zone_name>` — look up a specific zone:
  - Subscriber count
  - Sighting count (last 24h / 7d / all-time)
  - Top reporters in this zone
  - Most recent sightings
- [ ] **8.4.3** Database methods: `get_user_details()`, `get_zone_details()`, `get_user_recent_sightings()`, `get_zone_top_reporters()`

#### 8.5 Audit Logging

- [ ] **8.5.1** `admin_actions` table — schema:
  ```sql
  admin_actions (
    id INTEGER PK AUTOINCREMENT,
    admin_id BIGINT NOT NULL,
    action TEXT NOT NULL,        -- e.g. 'ban', 'unban', 'delete_sighting', 'broadcast'
    target TEXT,                 -- e.g. user ID, sighting ID, zone name
    detail TEXT,                 -- free-form context (reason, message preview, etc.)
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
  )
  ```
- [ ] **8.5.2** `log_admin_action()` database method — called by every admin write operation
- [ ] **8.5.3** `/admin log [count]` — view the most recent N admin actions (default 20)

---

### Phase 9: Admin — User Management & Content Moderation

Give admins the ability to remove bad actors and false content. Critical for platform trust as the user base grows.

**Why this phase exists:** A crowdsourced platform where any user can broadcast alerts to others is inherently vulnerable to abuse. Without ban and moderation tools, a single spammer can degrade the experience for all subscribers in a zone.

#### 9.1 User Banning

- [ ] **9.1.1** `banned_users` table — schema:
  ```sql
  banned_users (
    telegram_id BIGINT PK,
    banned_by BIGINT NOT NULL,
    reason TEXT,
    banned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
  )
  ```
- [ ] **9.1.2** `/admin ban <user_id> [reason]` — ban a user:
  - Insert into `banned_users`
  - Clear all subscriptions for the user (stop them receiving alerts)
  - Log action to `admin_actions`
  - Notify the banned user: "Your account has been restricted. Contact @admin_username for appeals."
- [ ] **9.1.3** `/admin unban <user_id>` — remove ban, log action, notify user
- [ ] **9.1.4** `/admin banlist` — list all currently banned users with ban date and reason
- [ ] **9.1.5** Ban enforcement middleware — check `banned_users` table on every command handler:
  - Banned users cannot: `/report`, `/subscribe`, `/recent`, `/mystats`, `/share`
  - Banned users receive a single static message when attempting any action
  - Do NOT check on `/start` (allow re-onboarding after unban)
- [ ] **9.1.6** Database methods: `ban_user()`, `unban_user()`, `is_banned()`, `get_banned_users()`

#### 9.2 Sighting Moderation

- [ ] **9.2.1** `/admin delete <sighting_id>` — remove a specific sighting:
  - Delete sighting and cascaded feedback (FK already handles this)
  - Log action to `admin_actions` with sighting details for the record
  - Confirmation step: show sighting details, require `/admin delete <id> confirm`
- [ ] **9.2.2** `/admin review` — show a moderation queue of flagged sightings:
  - Sightings where `feedback_negative > feedback_positive` and total feedback >= 3
  - Sightings from users with accuracy < 50% and total feedback >= 5
  - Display: sighting details, reporter info, feedback ratio, action buttons
- [ ] **9.2.3** Auto-flag logic — mark sightings for review when:
  - Negative feedback ratio exceeds 70% (with at least 3 votes)
  - Reporter accuracy drops below 40% (with at least 5 total feedback across all reports)
  - `flagged` boolean column added to `sightings` table
- [ ] **9.2.4** Database methods: `delete_sighting()`, `get_flagged_sightings()`, `flag_sighting()`, `get_low_accuracy_reporters()`

#### 9.3 Reporter Warnings

- [ ] **9.3.1** `/admin warn <user_id> [message]` — send a warning to a user:
  - Bot messages the user with the warning text
  - Log to `admin_actions`
  - Track warning count per user (new `warnings` column in `users` table)
- [ ] **9.3.2** Auto-warn threshold — automatically send a system warning when:
  - User's accuracy drops below 50% after 5+ feedback ratings
  - User has been rate-limited 3+ times in a single day
- [ ] **9.3.3** Escalation path: 3 warnings → auto-ban (configurable via `MAX_WARNINGS` env var, default 3)

---

### Phase 10: Admin — Broadcast & Operations

Operational tools for communicating with users, managing system state, and performing maintenance tasks.

**Why this phase exists:** Admins need to communicate service changes, perform maintenance, and extract data. These operations are lower priority than visibility (Phase 8) and moderation (Phase 9) but essential for sustained production operation.

#### 10.1 Broadcast Messaging

- [ ] **10.1.1** `/admin broadcast <message>` — send a message to all registered users:
  - Confirmation step: show message preview + recipient count, require explicit confirm
  - Rate-limited delivery (20 messages/second to respect Telegram API limits)
  - Delivery report: sent count, failed count, blocked users cleaned up
  - Log to `admin_actions` with message preview and delivery stats
- [ ] **10.1.2** `/admin broadcast zone:<zone_name> <message>` — targeted broadcast to subscribers of a specific zone
- [ ] **10.1.3** `/admin broadcast region:<region_name> <message>` — targeted broadcast to subscribers of all zones in a region
- [ ] **10.1.4** Database methods: `get_all_user_ids()`, `get_region_subscribers()`

#### 10.2 Maintenance Mode

- [ ] **10.2.1** `/admin maintenance on [message]` — enable maintenance mode:
  - All user commands return a "Bot is under maintenance" message (with optional custom text)
  - Admin commands continue to work normally
  - Scheduled jobs (cleanup) are paused
  - Log to `admin_actions`
- [ ] **10.2.2** `/admin maintenance off` — disable maintenance mode, resume normal operation
- [ ] **10.2.3** `MAINTENANCE_MODE` runtime flag (in-memory, resets on restart — or persisted in DB for durability)

#### 10.3 Data Management

- [ ] **10.3.1** `/admin purge sightings [days]` — manually trigger cleanup of sightings older than N days (default: `SIGHTING_RETENTION_DAYS`):
  - Confirmation step showing count of records to be deleted
  - Log to `admin_actions`
- [ ] **10.3.2** `/admin purge user <user_id>` — delete all data for a specific user (sightings, feedback, subscriptions, user record):
  - GDPR/privacy compliance for user data deletion requests
  - Confirmation step required
  - Log to `admin_actions`
- [ ] **10.3.3** `/admin export stats` — generate and send a CSV/JSON summary:
  - User counts, zone subscription counts, sighting counts by zone, feedback summary
  - Sent as a Telegram document attachment

#### 10.4 Runtime Configuration

- [ ] **10.4.1** `/admin config` — display current runtime settings:
  - `MAX_REPORTS_PER_HOUR`, `DUPLICATE_WINDOW_MINUTES`, `DUPLICATE_RADIUS_METERS`
  - `SIGHTING_EXPIRY_MINUTES`, `SIGHTING_RETENTION_DAYS`, `FEEDBACK_WINDOW_HOURS`
  - `MAX_WARNINGS` (from Phase 9.3)
  - Maintenance mode status
- [ ] **10.4.2** `/admin config <key> <value>` — adjust a runtime setting without restart:
  - Store overrides in `config_overrides` table (persisted across restarts)
  - Validate value ranges (e.g., `MAX_REPORTS_PER_HOUR` must be 1–100)
  - Log change to `admin_actions`
- [ ] **10.4.3** `/admin config reset <key>` — revert a setting to its default (delete override)
- [ ] **10.4.4** `config_overrides` table — schema:
  ```sql
  config_overrides (
    key TEXT PK,
    value TEXT NOT NULL,
    updated_by BIGINT NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
  )
  ```

---

### Phase 11: Growth Features

User-facing features to drive engagement and organic growth.

- [ ] **11.1** Weekly/monthly leaderboard (top reporters by report count and accuracy)
- [ ] **11.2** Inline mode — query `@parkwatch_bot Orchard` from any chat to check sightings
- [ ] **11.3** Warden activity heatmaps by time/day
- [ ] **11.4** Deep linking for referral tracking (`/start ref_<user_id>`)
- [ ] **11.5** Multi-language support (i18n) — start with English + Chinese

### Phase 12: Monetisation

- [ ] **12.1** Freemium model (1 zone free, premium for unlimited)
- [ ] **12.2** Sponsored alerts from parking providers
- [ ] **12.3** Business API for fleet managers

---

## Admin Command Reference (Phases 8–10)

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
| `/admin broadcast <msg>` | 10.1 | Broadcast to all users |
| `/admin broadcast zone:<z> <msg>` | 10.1 | Broadcast to zone subscribers |
| `/admin broadcast region:<r> <msg>` | 10.1 | Broadcast to region subscribers |
| `/admin maintenance on\|off` | 10.2 | Toggle maintenance mode |
| `/admin purge sightings [days]` | 10.3 | Clean up old sightings |
| `/admin purge user <id>` | 10.3 | Delete all user data (GDPR) |
| `/admin export stats` | 10.3 | Export stats as CSV/JSON |
| `/admin config` | 10.4 | View runtime settings |
| `/admin config <key> <val>` | 10.4 | Adjust a setting at runtime |
| `/admin config reset <key>` | 10.4 | Reset setting to default |

## Database Changes Required (Phases 8–10)

| Change | Phase | Description |
|--------|-------|-------------|
| New table: `admin_actions` | 8.5 | Audit log for all admin operations |
| New table: `banned_users` | 9.1 | Banned user records with reason |
| New column: `sightings.flagged` | 9.2 | Boolean flag for moderation queue |
| New column: `users.warnings` | 9.3 | Warning count per user |
| New table: `config_overrides` | 10.4 | Runtime configuration overrides |

## Environment Variables Added (Phases 8–10)

| Variable | Phase | Description | Default |
|----------|-------|-------------|---------|
| `ADMIN_USER_IDS` | 8.1 | Comma-separated admin Telegram IDs | (required) |
| `MAX_WARNINGS` | 9.3 | Warnings before auto-ban | 3 |

---

## File Reference

| File | Lines | Purpose |
|------|-------|---------|
| `bot/main.py` | ~1400 | All bot logic (handlers, routing, conversation flow) |
| `bot/database.py` | ~550 | Dual-driver database abstraction (SQLite/PostgreSQL) |
| `bot/__init__.py` | 1 | Package marker |
| `config.py` | 18 | Environment config and bot settings |
| `pyproject.toml` | ~70 | Project metadata, dependencies, tool configs (pytest/ruff/mypy) |
| `requirements.txt` | 4 | Runtime dependencies (for platforms that don't use pyproject.toml) |
| `.env.example` | 6 | Template for environment variables |
| `tests/conftest.py` | ~20 | Shared test fixtures (fresh SQLite DB per test) |
| `tests/test_unit.py` | ~250 | Unit tests for pure functions and zone data integrity |
| `tests/test_database.py` | ~480 | Database integration tests (CRUD, queries, transactions) |
| `.github/workflows/ci.yml` | ~35 | GitHub Actions CI pipeline (lint + typecheck + test) |
| `parking_warden_bot_spec.md` | ~590 | Full product specification with user flows |
| `README.md` | ~600 | User-facing documentation |
| `IMPROVEMENTS.md` | — | This file (code review & improvement plan) |
| `Procfile` | 1 | Heroku-style process declaration |
| `railway.toml` | 9 | Railway.app deployment config |
| `runtime.txt` | 1 | Python version specification (3.10) |

---

*Last updated: 2026-02-13*

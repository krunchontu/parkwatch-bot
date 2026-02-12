# ParkWatch SG — Code Review & Improvement Plan

## Audit Summary

**Date:** 2026-02-12
**Scope:** Full code review against `parking_warden_bot_spec.md` and `README.md`
**Files reviewed:** `bot/main.py` (1437 lines), `bot/database.py` (443 lines), `config.py` (18 lines), `requirements.txt`, `.env.example`

---

## Status: Phases 1–4 Complete

Phases 1 through 4 addressed all critical bugs, UX issues, data persistence, and robustness gaps from the original MVP. All items below are checked off and verified in the current codebase.

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

## Current State Assessment (2026-02-12)

### What's Working Well

1. **Feature completeness** — All 9 commands implemented and functional
2. **ConversationHandler** — Proper 6-state machine with timeout, fallbacks, and `/cancel` support
3. **Database layer** — Clean dual-driver abstraction with WAL mode, connection pooling, parameterized queries
4. **GPS-aware duplicate detection** — Haversine + 200m radius, zone-level fallback
5. **Feedback system** — Vote changing, self-rating prevention, window expiry, atomic count updates
6. **Alert message architecture** — `build_alert_message()` as single source of truth
7. **Blocked user cleanup** — Catches `Forbidden`, removes stale subscriptions
8. **Config externalization** — All tunable values in `config.py` with env var overrides

### Known Issues (To Fix)

1. **`datetime.now()` without timezone** — Used in `main.py` lines 653, 854, 968, etc. Server timezone assumed. Should use `datetime.now(timezone.utc)` for correctness on UTC-based hosts (Railway, Render).
2. **Sighting ID collisions** — `generate_sighting_id()` uses `time.time()_random(1000-9999)` — only ~9000 unique IDs per second. Concurrent reports can collide, causing INSERT failures.
3. **Race condition in feedback** — `handle_feedback()` does read→update→write without transaction wrapping. Two simultaneous votes on the same sighting can produce incorrect counts.
4. **Rate limit timing bug** — `main.py:660` uses `.seconds` instead of `.total_seconds()` on timedelta. Can give wrong wait-time values.
5. **PostgreSQL cleanup fragile** — `database.py:385` parses raw `"DELETE 42"` string from `conn.execute()` result. Brittle if format changes.
6. **No foreign keys** — `feedback.sighting_id` has no FK constraint to `sightings.id`. Orphan feedback possible on direct deletion.
7. **Accuracy shows 100% with 0 feedback** — `calculate_accuracy()` returns `(1.0, 0)` for new users. Confirmation message shows "100% (0 ratings)" which is misleading.
8. **ZONE_COORDS inside function** — ~90 lines of constants defined inside `handle_location()` at line 1180. Should be module-level.
9. **`sys.path` hack** — `main.py:6` uses `sys.path.insert(0, ...)` instead of proper packaging.
10. **Share message with 0 users** — `/share` says "Join 0+ drivers" on fresh deployments.

---

## Phase 5: Bug Fixes

Fix the known issues listed above.

- [ ] **5.1** Use `datetime.now(timezone.utc)` everywhere — replace all bare `datetime.now()` calls in `main.py` and `database.py`
- [ ] **5.2** Replace sighting ID generation with `uuid4()` to eliminate collisions
- [ ] **5.3** Wrap feedback read→update→write in a single transaction (add `_transaction()` helper to `Database`)
- [ ] **5.4** Fix rate limit wait calculation — use `.total_seconds()` instead of `.seconds`
- [ ] **5.5** Fix PostgreSQL cleanup — use `asyncpg`'s `execute()` return value properly instead of string parsing
- [ ] **5.6** Add foreign key constraints (`feedback.sighting_id → sightings.id` with `ON DELETE CASCADE`)
- [ ] **5.7** Show "No ratings yet" instead of "100% (0 ratings)" for users with zero feedback
- [ ] **5.8** Move `ZONE_COORDS` to module level (alongside `ZONES`)
- [ ] **5.9** Fix `sys.path` hack — convert to proper Python package with `__init__.py` imports or relative imports
- [ ] **5.10** Show "Join drivers" (no count) when subscriber count is below a threshold (e.g., < 10)

### Phase 6: Testing & CI

Add test coverage and automated quality checks.

- [ ] **6.1** Set up pytest with `pytest-asyncio` for async test support
- [ ] **6.2** Unit tests for pure functions: `haversine_meters`, `get_reporter_badge`, `get_accuracy_indicator`, `sanitize_description`, `build_alert_message`
- [ ] **6.3** Database integration tests: CRUD operations, duplicate detection queries, accuracy calculations
- [ ] **6.4** Add GitHub Actions CI pipeline: lint (ruff), type check (mypy), test (pytest)
- [ ] **6.5** Add `pyproject.toml` or `setup.py` for proper packaging

### Phase 7: Production Readiness

Harden for real-world scale.

- [ ] **7.1** Webhook mode support (alongside polling) for production deployments
- [ ] **7.2** Health check endpoint (lightweight HTTP server for deployment monitoring)
- [ ] **7.3** Structured logging (JSON format) for log aggregation services
- [ ] **7.4** Database migrations with Alembic (versioned schema changes)
- [ ] **7.5** Admin commands (`/admin stats`, `/admin broadcast`, `/admin ban`)
- [ ] **7.6** Sentry or equivalent error tracking integration

### Phase 8: Growth Features

- [ ] **8.1** Weekly/monthly leaderboard (top reporters by report count and accuracy)
- [ ] **8.2** Inline mode — query `@parkwatch_bot Orchard` from any chat to check sightings
- [ ] **8.3** Warden activity heatmaps by time/day
- [ ] **8.4** Deep linking for referral tracking (`/start ref_<user_id>`)
- [ ] **8.5** Multi-language support (i18n) — start with English + Chinese

### Phase 9: Monetisation

- [ ] **9.1** Freemium model (1 zone free, premium for unlimited)
- [ ] **9.2** Sponsored alerts from parking providers
- [ ] **9.3** Business API for fleet managers

---

## File Reference

| File | Lines | Purpose |
|------|-------|---------|
| `bot/main.py` | 1437 | All bot logic (handlers, routing, conversation flow) |
| `bot/database.py` | 443 | Dual-driver database abstraction (SQLite/PostgreSQL) |
| `config.py` | 18 | Environment config and bot settings |
| `requirements.txt` | 4 | `python-telegram-bot`, `python-dotenv`, `aiosqlite`, `asyncpg` |
| `.env.example` | 6 | Template for environment variables |
| `parking_warden_bot_spec.md` | ~560 | Full product specification with user flows |
| `README.md` | ~520 | User-facing documentation |
| `IMPROVEMENTS.md` | — | This file (code review & improvement plan) |
| `Procfile` | 1 | Heroku-style process declaration |
| `railway.toml` | 9 | Railway.app deployment config |
| `runtime.txt` | 1 | Python version specification (3.10) |

---

*Last updated: 2026-02-12*

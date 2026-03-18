# ParkWatch SG Bot — Production-Grade Codebase Audit

**Date:** 2026-03-18
**Auditor:** Senior Engineering Review
**Codebase Version:** 1.7.0
**Scope:** Full codebase (61 Python source files, 17 test files)

---

## Phase 1: Mental Model

### What This App Does
ParkWatch SG is a crowdsourced Telegram bot for Singapore drivers that broadcasts real-time parking warden sighting alerts across 80 zones. Users subscribe to zones, report warden sightings (with GPS or manual zone selection), and rate each other's reports for accuracy.

### Tech Stack
- **Language:** Python 3.10+
- **Framework:** python-telegram-bot 21.x (async)
- **Database:** SQLite (dev) / PostgreSQL (prod) via aiosqlite / asyncpg
- **Migrations:** Alembic
- **CI:** GitHub Actions (ruff, mypy, pytest)
- **Deployment:** Railway (nixpacks), optional Heroku (Procfile)
- **Monitoring:** Sentry (optional), custom health check server

### Key Modules
| Module | Responsibility |
|--------|---------------|
| `bot/main.py` | App wiring, handler registration, lifecycle |
| `bot/database.py` | Dual-driver DB abstraction, repository composition |
| `bot/repositories/` | 5 focused repos (User, Sighting, Feedback, Admin, Config) |
| `bot/handlers/user.py` | User commands (/start, /subscribe, /recent, /mystats, etc.) |
| `bot/handlers/report.py` | 6-state ConversationHandler for report flow + feedback |
| `bot/handlers/admin/` | 5 admin modules (stats, moderation, announce, config, data) |
| `bot/services/` | Maintenance, moderation, notifications, runtime settings |
| `bot/health.py` | Lightweight /health HTTP server |

### Main User Flows
1. **Subscribe:** /start → select region → toggle zones → Done
2. **Report:** /report → choose method (GPS/manual) → select zone → description → confirm → broadcast
3. **Feedback:** Tap thumbs-up/down on alert → transaction-safe vote → auto-flag if >70% negative
4. **Admin:** /admin → 16 subcommands for moderation, config, data ops

### Data Flow
```
User input (Telegram) → Handler (ban/maintenance check) → Service layer → Repository → DB
                                                                              ↓
                                                                 Broadcast (semaphore-bounded)
                                                                              ↓
                                                                    Zone subscribers
```

### External Dependencies
- Telegram Bot API (only external service)
- Sentry (optional error tracking)
- No third-party queues, caches, or APIs

### Deployment Model
- Railway with `alembic upgrade head && python -m bot.main`
- Webhook mode (production) or polling mode (development)
- Health check server on separate port

---

## Phase 2 & 3: Deep Audit — Critical Findings

### F-001: PicklePersistence Deserialization Vulnerability
| Field | Value |
|-------|-------|
| **ID** | F-001 |
| **Title** | PicklePersistence uses Python pickle — arbitrary code execution risk |
| **Severity** | High |
| **Category** | Security |
| **Evidence** | `bot/main.py:206` — `PicklePersistence(filepath=PERSISTENCE_PATH)` |
| **Why it matters** | If an attacker can write to the persistence file (e.g., via path traversal, shared filesystem, or backup restore), they can execute arbitrary Python code on deserialization. The file is read at every bot restart. |
| **Root cause** | python-telegram-bot's PicklePersistence uses `pickle.load()` internally, which is inherently unsafe for untrusted data. |
| **Fix** | Accept the risk if the file is on a trusted filesystem with proper permissions. For higher security, consider implementing a JSON-based persistence backend or restricting file permissions (0600). The `PERSISTENCE_PATH` is configurable via env var, so ensure it points to a protected location. |
| **Effort** | M (days) — to implement custom JSON persistence |
| **Priority** | Next |

### F-002: SQLite Transaction Safety Gap in apply_feedback
| Field | Value |
|-------|-------|
| **ID** | F-002 |
| **Title** | SQLite apply_feedback lacks proper transaction isolation — race condition window |
| **Severity** | High |
| **Category** | Bug |
| **Evidence** | `bot/repositories/feedback.py:48-97` — SQLite path uses `self._conn` directly without `BEGIN`/`COMMIT` isolation |
| **Why it matters** | While SQLite has implicit transactions, the aiosqlite connection is shared across all concurrent handlers. Two concurrent feedback operations on the same sighting can interleave between the read and write, causing incorrect feedback counts (double-counting or missed decrements). This is the most likely active bug in production. |
| **Root cause** | The SQLite branch relies on auto-commit behavior but doesn't explicitly acquire an exclusive transaction. `aiosqlite` runs SQLite in a background thread, but the connection is shared across all async handlers. |
| **Fix** | Wrap the SQLite branch in an explicit `BEGIN IMMEDIATE` transaction to prevent concurrent reads from interleaving. See Patch #1. |
| **Effort** | S (hours) |
| **Priority** | Now |

### F-003: Webhook URL Path Exposes Bot Token
| Field | Value |
|-------|-------|
| **ID** | F-003 |
| **Title** | Bot token used in webhook URL path — token exposure in server logs |
| **Severity** | High |
| **Category** | Security |
| **Evidence** | `bot/main.py:298-299` — `url_path=f"webhook/{TELEGRAM_BOT_TOKEN}"` |
| **Why it matters** | The bot token appears in the URL path, meaning it will appear in HTTP access logs, load balancer logs, monitoring tools, and any reverse proxy logs. Anyone with log access gets full bot control. |
| **Root cause** | Common pattern from older Telegram bot tutorials, but it's a security anti-pattern. |
| **Fix** | Use a random webhook secret instead: `url_path=f"webhook/{uuid4()}"` or use python-telegram-bot's built-in `secret_token` parameter. See Patch #2. |
| **Effort** | S (hours) |
| **Priority** | Now |

### F-004: Health Check Server Has No Request Size Limit
| Field | Value |
|-------|-------|
| **ID** | F-004 |
| **Title** | Health check server reads up to 4096 bytes without connection limit — potential resource exhaustion |
| **Severity** | Medium |
| **Category** | Security / Reliability |
| **Evidence** | `bot/health.py:28,72` — reads 4096 bytes, listens on 0.0.0.0 with no connection limiting |
| **Why it matters** | The health server is bound to all interfaces. Without connection limiting, it's vulnerable to slowloris-style attacks that could exhaust file descriptors and impact the main bot process. |
| **Root cause** | Minimal implementation without defensive measures. |
| **Fix** | Add a connection limit or move health checks behind the webhook server. Not critical since Railway provides its own ingress protection. |
| **Effort** | S (hours) |
| **Priority** | Later |

### F-005: admin_only Decorator Doesn't Preserve Function Metadata
| Field | Value |
|-------|-------|
| **ID** | F-005 |
| **Title** | `admin_only` decorator missing `@functools.wraps` — breaks introspection |
| **Severity** | Low |
| **Category** | Quality |
| **Evidence** | `bot/handlers/admin/__init__.py:19-33` — no `@functools.wraps(func)` |
| **Why it matters** | Without `@wraps`, the wrapper function loses the original function's name, docstring, and module info. This can cause issues with debugging, logging, and any framework features that rely on function metadata. |
| **Root cause** | Omission (the `ban_check` and `maintenance_check` decorators correctly use `@wraps`). |
| **Fix** | Add `@functools.wraps(func)` to the wrapper. See Patch #3. |
| **Effort** | S (minutes) |
| **Priority** | Now |

### F-006: No Rate Limiting on Feedback Votes
| Field | Value |
|-------|-------|
| **ID** | F-006 |
| **Title** | Feedback voting has no rate limit — vote-flip spam possible |
| **Severity** | Medium |
| **Category** | Bug / Security |
| **Evidence** | `bot/handlers/report.py:449-545` — `handle_feedback()` has no rate limiting |
| **Why it matters** | A user can spam the feedback buttons rapidly, alternating between positive and negative. While duplicate votes are rejected, vote-flipping (pos→neg→pos→neg) is allowed without limit, causing unnecessary DB load and potentially triggering/untriggering auto-flags rapidly. |
| **Root cause** | Rate limiting was added for reports and user feedback messages, but not for sighting feedback votes. |
| **Fix** | Add a per-user feedback rate limit (e.g., max 10 vote changes per hour). See Patch #4. |
| **Effort** | S (hours) |
| **Priority** | Next |

### F-007: Duplicate Detection False Negatives with Non-GPS Reports
| Field | Value |
|-------|-------|
| **ID** | F-007 |
| **Title** | Zone-level duplicate detection blocks ALL same-zone reports when any non-GPS sighting exists |
| **Severity** | Medium |
| **Category** | Bug / Product |
| **Evidence** | `bot/handlers/report.py:313-342` — when either report lacks GPS, it falls through to zone-level duplicate which blocks immediately |
| **Why it matters** | If one non-GPS report exists for a zone, ALL subsequent reports for that zone within the duplicate window (5 min) are blocked — even if they're GPS-tagged and clearly in different locations. This discourages legitimate reporting. |
| **Root cause** | The duplicate detection loop iterates through all recent sightings and exits on the FIRST match without GPS comparison. It should `continue` for non-GPS sightings when the new report has GPS. |
| **Fix** | When the new report has GPS coordinates but an existing sighting doesn't, skip that sighting instead of blocking. Only block on zone-level duplicate if NEITHER has GPS. See Patch #5. |
| **Effort** | S (hours) |
| **Priority** | Now |

### F-008: N+1 Query in _build_recent_text
| Field | Value |
|-------|-------|
| **ID** | F-008 |
| **Title** | Per-sighting accuracy query in /recent creates N+1 database pattern |
| **Severity** | Medium |
| **Category** | Performance |
| **Evidence** | `bot/handlers/user.py:99-101` — `await db.calculate_accuracy(reporter_id)` inside loop |
| **Why it matters** | For each sighting shown in /recent, a separate aggregate query runs against the sightings table. If a user has 10 zones with 5 sightings each, that's 50 extra DB queries. With PostgreSQL, each acquires a connection from the pool. |
| **Root cause** | Accuracy is calculated per-reporter per-sighting, but could be batched. |
| **Fix** | Pre-fetch accuracy for all reporter IDs in a single query before the loop. |
| **Effort** | M (days) |
| **Priority** | Next |

### F-009: Missing Ban Check on report_from_start
| Field | Value |
|-------|-------|
| **ID** | F-009 |
| **Title** | Banned users can enter report flow via /start menu button |
| **Severity** | High |
| **Category** | Bug / Security |
| **Evidence** | `bot/handlers/report.py:74-91` — `report_from_start()` has no `@ban_check` decorator |
| **Why it matters** | The `/report` command has `@ban_check`, but the "Report a Sighting" button in the /start menu calls `report_from_start()` which skips the ban check entirely. Banned users can still report sightings this way. The report will succeed at `handle_report_confirm()` which also lacks `@ban_check`. |
| **Root cause** | The `report_from_start` entry point was added after the ban system and the decorator was omitted. `handle_report_confirm` also lacks ban_check since decorators are only on entry points. |
| **Fix** | Add ban check to `report_from_start()` and `handle_report_confirm()`. See Patch #3 (combined). |
| **Effort** | S (hours) |
| **Priority** | Now |

### F-010: Unvalidated Zone Names from Callback Data
| Field | Value |
|-------|-------|
| **ID** | F-010 |
| **Title** | Zone names extracted from callback_data without validation against known zones |
| **Severity** | Medium |
| **Category** | Security |
| **Evidence** | `bot/handlers/report.py:186` — `zone_name = query.data.replace("report_zone_", "")` used directly; `bot/handlers/user.py:274` — same pattern with `zone_` prefix |
| **Why it matters** | Telegram callback_data can be crafted by modifying API requests. An attacker could inject arbitrary zone names (e.g., `report_zone_'; DROP TABLE sightings;--`). While parameterized queries prevent SQL injection, arbitrary strings end up in the `sightings.zone` column and get broadcast to nobody (no subscribers). More importantly, crafted zone names could contain Telegram Markdown/HTML injection if displayed without escaping. |
| **Root cause** | No allowlist validation after extracting zone name from callback data. |
| **Fix** | Validate extracted zone names against the known ZONES dict before accepting. |
| **Effort** | S (hours) |
| **Priority** | Next |

### F-011: Global Mutable State for Database Singleton
| Field | Value |
|-------|-------|
| **ID** | F-011 |
| **Title** | Database singleton via module-level `_db` global — fragile in testing and concurrent initialization |
| **Severity** | Low |
| **Category** | Architecture |
| **Evidence** | `bot/database.py:27-34` — `_db: Optional["Database"] = None` with `get_db()` accessor |
| **Why it matters** | This pattern works but makes testing harder (must manage global state) and has no protection against concurrent `init_db()` calls. The test suite works around this with fixtures, but it's a smell. |
| **Root cause** | Simple singleton pattern chosen for convenience. |
| **Fix** | Acceptable for a single-process bot. No action needed unless scaling to multi-worker. |
| **Effort** | L (weeks) — for proper DI |
| **Priority** | Later |

### F-012: No Subscription Limit Per User
| Field | Value |
|-------|-------|
| **ID** | F-012 |
| **Title** | Users can subscribe to all 80 zones — no limit enforced |
| **Severity** | Low |
| **Category** | Product |
| **Evidence** | `bot/repositories/user.py:24-33` — `add_subscription` has no count check |
| **Why it matters** | A user subscribing to all 80 zones gets every alert, creating notification fatigue and wasting broadcast bandwidth. Could also be used to monitor all zones for anti-warden purposes. |
| **Root cause** | No business logic to enforce a reasonable subscription cap. |
| **Fix** | Add a configurable max subscription limit (e.g., 20 zones). |
| **Effort** | S (hours) |
| **Priority** | Later |

### F-013: Maintenance Mode Announce Sends Without Concurrency Control
| Field | Value |
|-------|-------|
| **ID** | F-013 |
| **Title** | Maintenance announcement sends messages one-by-one without bounded concurrency |
| **Severity** | Medium |
| **Category** | Performance / Reliability |
| **Evidence** | `bot/handlers/admin/config.py:97-99` — sequential loop with `contextlib.suppress(Exception)` |
| **Why it matters** | Unlike `broadcast_message()` which uses semaphore-bounded concurrency, the maintenance announcement uses a sequential loop that silently swallows ALL exceptions. For large user bases this will be very slow, and any Telegram rate limiting errors are completely lost. |
| **Root cause** | The maintenance announce was implemented before `broadcast_message()` was available. |
| **Fix** | Reuse `broadcast_message()` from `bot/services/notifications.py`. |
| **Effort** | S (hours) |
| **Priority** | Next |

### F-014: AUTOINCREMENT → SERIAL Replacement Is Fragile
| Field | Value |
|-------|-------|
| **ID** | F-014 |
| **Title** | String replacement for PostgreSQL DDL adaptation is brittle |
| **Severity** | Medium |
| **Category** | Architecture |
| **Evidence** | `bot/database.py:309-318` — `statements = [s.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY") for s in statements]` plus a TIMESTAMP→TIMESTAMPTZ replacement with CURRENT_TIMESTAMP protection hack |
| **Why it matters** | This string replacement approach is fragile — it relies on exact textual matches and the "CURRENT_TS_HOLD" trick to avoid mangling CURRENT_TIMESTAMP. Any future DDL changes that introduce TIMESTAMP in column names or comments will break. The replacement is also not applied to migration files (those use Alembic). |
| **Root cause** | Quick fix to support dual-driver DDL without maintaining separate SQL files. |
| **Fix** | Acceptable given Alembic handles production migrations. The `create_tables()` DDL is primarily for development/testing with SQLite. Low priority to change. |
| **Effort** | M (days) |
| **Priority** | Later |

### F-015: Missing Error Handling in Cleanup Job
| Field | Value |
|-------|-------|
| **ID** | F-015 |
| **Title** | Cleanup job has no top-level exception handler — failure kills the repeating job |
| **Severity** | Medium |
| **Category** | Reliability |
| **Evidence** | `bot/main.py:137-152` — `cleanup_job` has no try/except |
| **Why it matters** | python-telegram-bot's `run_repeating` swallows exceptions but logs them. If the DB is temporarily unavailable, the cleanup job will fail silently. While the job continues to run (the framework handles this), a persistent DB outage could cause sightings to accumulate beyond retention limits. |
| **Root cause** | Reliance on framework-level error handling without application-level monitoring. |
| **Fix** | Add try/except with structured logging. Low priority since framework handles it. |
| **Effort** | S (hours) |
| **Priority** | Later |

---

## Debugging Guide

### Active Bug: F-009 (Banned Users Can Report via Start Menu)
- **Reproduction:** Ban a user via `/admin ban <id>`. User opens bot, taps /start, taps "Report a Sighting" button. Observe: user enters report flow and can submit.
- **Root cause:** `report_from_start()` at `report.py:74` is a ConversationHandler entry point and lacks `@ban_check`. Additionally, `handle_report_confirm()` at line 274 also lacks it.
- **Isolation:** Add `@ban_check` to both functions. Test by banning a test user and attempting to report via the start menu.
- **Instrumentation:** Add `logger.info("Banned user %d attempted report via start menu", user_id)` in the ban_check decorator.

### Active Bug: F-007 (Duplicate Detection Over-Blocking)
- **Reproduction:** Submit a non-GPS report for zone "Bugis". Within 5 minutes, submit a GPS-tagged report for the same zone from a different location. Observe: second report is blocked as duplicate.
- **Root cause:** `report.py:331-342` — the `else` branch triggers whenever either sighting lacks GPS, blocking regardless.
- **Isolation:** Modify the condition at line 316-342 to only block on zone-level when BOTH lack GPS.

### Suspected Bug: F-002 (Feedback Race Condition)
- **Reproduction hypothesis:** Two users tap feedback buttons on the same sighting simultaneously. Under SQLite, both read the same feedback state before either commits.
- **Instrumentation:** Add timing logs in `apply_feedback()` to measure the window between read and write.
- **Isolation:** Write a concurrent test using `asyncio.gather()` with two `apply_feedback()` calls on the same sighting.

---

## Phase 4: Action Plan

### Top 10 Actions (Priority Order)

1. **F-009: Add ban check to `report_from_start` and `handle_report_confirm`** — Banned users can bypass the ban. Fix: add decorator. [Now, S]
2. **F-007: Fix duplicate detection for mixed GPS/non-GPS reports** — Legitimate reports are being blocked. [Now, S]
3. **F-003: Remove bot token from webhook URL path** — Token exposure in logs. [Now, S]
4. **F-005: Add `@wraps` to `admin_only` decorator** — Trivial fix, good practice. [Now, S]
5. **F-002: Add BEGIN IMMEDIATE to SQLite apply_feedback** — Race condition in concurrent feedback. [Now, S]
6. **F-010: Validate zone names from callback data** — Defense-in-depth against crafted callbacks. [Next, S]
7. **F-006: Add rate limit to feedback vote flipping** — Prevent abuse. [Next, S]
8. **F-008: Batch accuracy queries in /recent** — N+1 performance. [Next, M]
9. **F-013: Use broadcast_message for maintenance announcements** — Reliability. [Next, S]
10. **F-001: Evaluate PicklePersistence security posture** — Security review. [Next, M]

### 3 Quick Wins (High Impact, Low Effort — This Week)
1. **F-009:** Add `@ban_check` to `report_from_start` and `handle_report_confirm` (5 min)
2. **F-005:** Add `@functools.wraps` to `admin_only` (2 min)
3. **F-003:** Replace token in webhook URL with random secret (15 min)

### 3 Critical Bugs to Investigate First
1. **F-009:** Banned users bypassing ban via start menu → confirmed, fix immediately
2. **F-007:** Duplicate detection blocking legitimate GPS reports → confirmed, fix immediately
3. **F-002:** Feedback race condition under concurrent SQLite access → test and fix

### 3 Highest-ROI Refactors
1. **Zone name validation:** Add allowlist check for zone names from callback data (prevents future injection classes)
2. **Broadcast consolidation:** Route all broadcasts through `broadcast_message()` (eliminates config.py's ad-hoc loop)
3. **N+1 elimination in /recent:** Pre-batch accuracy queries (directly improves user-facing latency)

### Implementation Sequence (Solo Dev)
```
Week 1: F-009 → F-007 → F-003 → F-005 → F-002 (all "Now" items)
Week 2: F-010 → F-006 → F-013 (all "Next" quick items)
Week 3: F-008 (N+1 fix, requires query refactor)
         F-001 (evaluate persistence security)
```

---

## Phase 5: Patches

### Patch #1: Fix Banned User Report Bypass (F-009) + admin_only @wraps (F-005)

**File: `bot/handlers/report.py`**
Add `@ban_check` to `report_from_start()` and `handle_report_confirm()`.

**File: `bot/handlers/admin/__init__.py`**
Add `@functools.wraps(func)` to `admin_only` wrapper.

### Patch #2: Fix Webhook Token Exposure (F-003)

**File: `bot/main.py`**
Replace `TELEGRAM_BOT_TOKEN` in URL path with a hashed secret.

### Patch #3: Fix Duplicate Detection Over-Blocking (F-007)

**File: `bot/handlers/report.py`**
Only block on zone-level duplicate when NEITHER report has GPS.

### Patch #4: Fix SQLite Feedback Race Condition (F-002)

**File: `bot/repositories/feedback.py`**
Use `BEGIN IMMEDIATE` for SQLite transaction in `apply_feedback()`.

### Patch #5: Validate Zone Names from Callbacks (F-010)

**File: `bot/handlers/report.py`**
Validate `zone_name` against known zones before proceeding.

---

*Patches are implemented in the accompanying commit. See git diff for exact changes.*

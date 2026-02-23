# ParkWatch SG — Improvement Plan

**Last updated:** 2026-02-23 (post-audit consolidation)
**Current version:** 1.4.0 · **Tests:** 335 passing · **Phases 1–11.5 complete**
**Roadmap:** 11.6 → 11.7 → 11.8 → 12 → 13 → 14 → 15

---

## Completed Phases (Summary)

All items below are implemented, tested, and verified in CI.

| Phase | Name | Key Deliverables |
|-------|------|-----------------|
| 1 | Critical Fixes | Rate limiting, duplicate detection, self-rating prevention, ConversationHandler guard |
| 2 | UX Improvements | Multi-zone subscription, region→zone selection, 6-state ConversationHandler, native GPS button |
| 3 | Data Persistence | Dual-driver database (SQLite/PostgreSQL), 4-table schema, scheduled cleanup |
| 4 | Robustness | Structured alert messages, haversine GPS, input sanitization, broadcast failure handling |
| 5 | Bug Fixes | UTC datetime, UUID4 sighting IDs, transaction-safe feedback, FK cascades, packaging |
| 6 | Testing & CI | pytest + pytest-asyncio, unit/integration tests, GitHub Actions (lint + typecheck + test on 3.10/3.11/3.12) |
| 7 | Production Infra | Webhook mode, health check server, structured JSON logging, Alembic migrations, Sentry |
| 8 | Admin Foundation | Admin auth, `/admin stats`, user/zone lookup, audit logging |
| 9 | Admin Moderation | Ban/unban/warn, sighting deletion, moderation queue, auto-flag, auto-ban escalation |
| 10 | Architecture & UX | Module refactor, `/feedback` command, `/admin announce`, richer `/start` menu |
| 11 | Admin Operations | Runtime config, maintenance mode, data purge (GDPR), CSV/JSON export |
| 11.5 | Tech Debt | `/start` menu fix, `ban_check` callback safety, broadcast concurrency, TypedDict models, handler tests, rate limit decoupling |

---

## Phase 11.6: Audit Quick Fixes

Small, targeted fixes identified in the 2026-02-23 codebase audit. Should land before the next production deploy.

- [ ] **11.6.1** Add `first_name` column to `create_tables()` to match Alembic migration 005 (`database.py`)
- [ ] **11.6.2** Add `@functools.wraps(func)` to `ban_check` decorator for consistent metadata (`services/moderation.py`)
- [ ] **11.6.3** Add `user_rate_limits` cleanup to `cleanup_job()` — purge entries older than 24h (`main.py`)
- [ ] **11.6.4** Log warning when `ADMIN_USER_IDS` contains non-numeric entries instead of silently ignoring (`config.py`)
- [ ] **11.6.5** Fix `/feedback` to report actual delivery outcome — "Sent to N admin(s)" or "Could not deliver" (`handlers/user.py`)
- [ ] **11.6.6** Add alert expiry color indicators (🔴🟡🟢) to `/recent` display per spec (`handlers/user.py`)
- [ ] **11.6.7** Add `conversation_timeout` callback to notify users when report flow expires (`main.py`)
- [ ] **11.6.8** Tests for all 11.6 items; CI must pass

---

## Phase 11.7: Reliability Hardening

Connection reliability and database resilience improvements.

- [ ] **11.7.1** Add asyncpg connection pool health checks: keepalive, statement timeout, pool exhaustion handling (`database.py`)
- [ ] **11.7.2** Add conversation state persistence via `PicklePersistence` or DB-backed store — survive restarts (`main.py`)
- [ ] **11.7.3** Make `cleanup_job` interval configurable via runtime settings (currently hardcoded 6h) (`main.py`)
- [ ] **11.7.4** Add exponential backoff on non-RetryAfter transient failures in broadcast (`services/notifications.py`)
- [ ] **11.7.5** Add GPS coordinate bounds validation in `handle_location()` (`handlers/report.py`)
- [ ] **11.7.6** Tests for all 11.7 items

---

## Phase 11.8: Database Refactor

Split the `database.py` god module (1,067 lines) **before** growth features add more queries to it.

- [ ] **11.8.1** Split `database.py` into repository modules: `UserRepository`, `SightingRepository`, `FeedbackRepository`, `AdminRepository`, `ConfigRepository`
- [ ] **11.8.2** Add PostgreSQL-specific test suite (currently all tests use SQLite)
- [ ] **11.8.3** Tests for all 11.8 items; CI must pass

---

## Phase 12: Growth Features

**Depends on:** Phases 11.6–11.8. Growth features land on the hardened, well-structured base.

**Priority order:** 12.1 → 12.2 → 12.3 → 12.4

#### 12.1 Deep Linking & Referrals
- [ ] Referral schema (`users.referred_by` + attribution metadata)
- [ ] Dedupe rules: first valid referral only; ignore self-referral and pre-existing users
- [ ] GDPR linkage: referral data must be purged by `/admin purge user`
- [ ] Define incentive policy before implementation

#### 12.2 Leaderboards
- [ ] `/leaderboard` command (avoid scheduled broadcast complexity in v1)
- [ ] Define windows: rolling 7-day + all-time
- [ ] Minimum threshold and privacy opt-out support
- [ ] DB queries for time-windowed ranking with accuracy tie-breaks

#### 12.3 Inline Mode
- [ ] `InlineQueryResultArticle` format with redaction policy (no reporter identity, no precise GPS)
- [ ] Inline-specific maintenance + ban checks
- [ ] Telegram inline query caching (`cache_time`) and throttling

#### 12.4 Activity Summaries
- [ ] `/activity [zone]` with hourly/day-of-week text summaries
- [ ] SQL dialect differences explicit (`strftime` SQLite vs `EXTRACT` PostgreSQL)

#### 12.5 Testing
- [ ] Tests per feature before marking complete

---

## Phase 13: Monetisation

Treat each workstream independently with validation gates.

#### 13.A Freemium
- [ ] Product policy: free tier limits, grandfathering, trial rules, rollback plan
- [ ] Schema: `users.is_premium`, `premium_expires_at`, billing metadata
- [ ] Telegram Payments integration + SG legal/tax compliance

#### 13.B Sponsored Alerts
- [ ] Sponsor ops workflow: submission, moderation, scheduling, targeting, frequency cap
- [ ] Hard separation/labeling from safety alerts
- [ ] User opt-out and max frequency enforcement

#### 13.C Business API
- [ ] Separate product surface with auth, rate limits, infrastructure
- [ ] Demand validation before engineering build

#### 13.D Validation Gates
- [ ] Baseline KPIs (active users, retention, false-alarm rate) before launch
- [ ] Limited pilot and trust impact review before rollout

---

## Phase 14: Internationalization (i18n)

- [ ] Extract user-facing strings into translation keys
- [ ] Localization format/loader with fallback behavior
- [ ] User language preference persistence (`users.language`)
- [ ] `/language` command and onboarding selection
- [ ] Baseline locales: English (`en`) + Simplified Chinese (`zh`)
- [ ] i18n test coverage (key completeness, fallback, rendering)

---

## Phase 15: Scale & Operations

Architectural investments for production at scale. Informed by 2026-02-23 audit comparison against world-class bots (Combot, Rose, MEE6, Carl-bot).

#### 15.1 Observability
- [ ] Command latency tracking (Prometheus/StatsD)
- [ ] Broadcast success/failure rate counters
- [ ] Database query duration metrics
- [ ] Rate limit hit counters
- [ ] Basic SLOs and alerting thresholds
- [ ] Test coverage reporting in CI

#### 15.2 Delivery Guarantees
- [ ] Persistent broadcast job queue (Redis or database-backed)
- [ ] Per-recipient delivery tracking
- [ ] Dead-letter handling for permanently failed deliveries
- [ ] Idempotency keys to prevent duplicate sends on restart

#### 15.3 Horizontal Scaling
- [ ] Worker-based broadcast architecture
- [ ] Connection pool tuning and read replicas
- [ ] Graceful shutdown with in-flight broadcast draining

#### 15.4 User Engagement
- [ ] Media support (photos of warden sightings)
- [ ] User-facing privacy controls and self-service data export
- [ ] Web dashboard for admin analytics

---

## Reference

### Admin Commands

| Command | Description |
|---------|-------------|
| `/admin` | List all admin commands |
| `/admin stats` | Global statistics dashboard |
| `/admin user <id>` | User details and activity |
| `/admin zone <name>` | Zone activity and stats |
| `/admin log [count]` | Admin action audit log |
| `/admin ban <id> [reason]` | Ban a user |
| `/admin unban <id>` | Unban a user |
| `/admin banlist` | List banned users |
| `/admin warn <id> [msg]` | Warn a user |
| `/admin delete <sighting_id>` | Delete a sighting |
| `/admin review` | Flagged sightings queue |
| `/admin announce all\|zone <msg>` | Broadcast to users |
| `/admin config [key] [value]` | View/adjust runtime settings |
| `/admin config reset <key>` | Reset setting to default |
| `/admin maintenance on\|off` | Toggle maintenance mode |
| `/admin purge sightings [days]` | Purge old sightings |
| `/admin purge user <id>` | GDPR user data purge |
| `/admin export stats [csv\|json]` | Export stats |

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | — | Bot token from @BotFather |
| `DATABASE_URL` | No | SQLite | PostgreSQL connection string |
| `WEBHOOK_URL` | No | — | Public URL for webhook mode |
| `PORT` | No | `8443` | Webhook listener port |
| `HEALTH_CHECK_ENABLED` | No | `true` | Enable health check server |
| `HEALTH_CHECK_PORT` | No | `8080` | Health check port |
| `LOG_FORMAT` | No | `text` | `text` or `json` |
| `SENTRY_DSN` | No | — | Sentry error tracking DSN |
| `ADMIN_USER_IDS` | No | `""` | Comma-separated admin IDs |
| `MAX_WARNINGS` | No | `3` | Warnings before auto-ban |
| `SIGHTING_RETENTION_DAYS` | No | `30` | Days to retain sightings |
| `FEEDBACK_WINDOW_HOURS` | No | `24` | Feedback button lifetime |

---

*See [`APP_REVIEW.md`](APP_REVIEW.md) for the full audit report with security analysis and world-class bot comparison.*

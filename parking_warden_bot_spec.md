# ParkWatch SG — Complete Specification

## Overview

ParkWatch SG is a Telegram bot that crowdsources real-time parking warden sightings across Singapore. When a user spots a warden, they report it, and all users subscribed to that zone receive instant alerts.

**Core Value Proposition:** Save drivers from parking tickets by providing real-time, community-driven warden location alerts.

---

## User Commands

| Command | Description | Flow |
|---------|-------------|------|
| `/start` | Onboarding — register and select zones | Region → Zone selection |
| `/subscribe` | Add more zones to subscriptions | Region → Zone selection |
| `/unsubscribe` | Remove zones from subscriptions | Zone list → Tap to remove |
| `/myzones` | View current subscribed zones | Display list |
| `/report` | Report a warden sighting | Location → Description → Confirm → Broadcast |
| `/recent` | View recent sightings (30 mins) | Display filtered list |
| `/mystats` | View reporter stats and accuracy | Display stats |
| `/share` | Generate invite message | Display shareable message |
| `/feedback <message>` | Send feedback to admins | Relay message, confirm to user |
| `/help` | Show all commands | Display help text |

## Admin Commands (Phases 8–10, with Phase 11 planned)

Requires `ADMIN_USER_IDS` env var. Non-admin users see "Unknown command".

| Command | Phase | Status | Description |
|---------|-------|--------|-------------|
| `/admin` | 8 | Done | List all admin commands |
| `/admin stats` | 8 | Done | Global statistics dashboard |
| `/admin user <id or @username>` | 8 | Done | User lookup (details, subscriptions, activity, ban status) |
| `/admin zone <zone_name>` | 8 | Done | Zone lookup (subscribers, sightings, top reporters) |
| `/admin log [count]` | 8 | Done | View admin action audit log (default: 20, max: 100) |
| `/admin ban <user_id> [reason]` | 9 | Done | Ban a user (clears subscriptions, notifies user) |
| `/admin unban <user_id>` | 9 | Done | Remove a user's ban and reset warnings |
| `/admin banlist` | 9 | Done | List all currently banned users |
| `/admin warn <user_id> [message]` | 9 | Done | Send a warning (auto-ban after MAX_WARNINGS) |
| `/admin delete <sighting_id> [confirm]` | 9 | Done | Delete a sighting (two-step confirmation) |
| `/admin review` | 9 | Done | View moderation queue of flagged sightings |
| `/admin help [command]` | 8 | Done | Detailed help for a specific admin command |
| `/admin announce all <msg>` | 10 | Done | Announce to all registered users |
| `/admin announce zone <z> <msg>` | 10 | Done | Announce to zone subscribers |
| `/admin maintenance on\|off` | 11 | Planned | Toggle maintenance mode |
| `/admin config [key] [value]` | 11 | Planned | View/adjust runtime settings |

---

## User Flows

### Flow 1: Onboarding (`/start`)

```
User sends: /start
    │
    ▼
Bot: "Welcome to ParkWatch SG! 🚗
      I'll alert you when parking wardens are spotted nearby.
      
      To get started, which areas do you want alerts for?"
    │
    ▼
Bot shows: Inline keyboard with regions
           [Central] [Central North] [East] [West] [North] [North-East]
    │
    ▼
User taps: [Central]
    │
    ▼
Bot shows: Zones in Central region
           [Tanjong Pagar] [Bugis] [Orchard] ... [◀ Back]
    │
    ▼
User taps: [Tanjong Pagar]
    │
    ▼
Bot: "✅ Your zones: Tanjong Pagar
      
      Use /subscribe to add more zones.
      Use /unsubscribe to remove zones."
```

### Flow 1b: Unsubscribe (`/unsubscribe`)

```
User sends: /unsubscribe
    │
    ▼
Bot: "📍 Your subscribed zones (3):
      
      Tap a zone to unsubscribe:"
      
      [❌ Bugis]
      [❌ Orchard]
      [❌ Tanjong Pagar]
      [🗑️ Unsubscribe from ALL]
      [✅ Done]
    │
    ▼
User taps: [❌ Bugis]
    │
    ▼
Bot: (toast) "❌ Unsubscribed from Bugis"
     
     Updates keyboard to show remaining zones:
      
      [❌ Orchard]
      [❌ Tanjong Pagar]
      [🗑️ Unsubscribe from ALL]
      [✅ Done]
    │
    ▼
User taps: [✅ Done]
    │
    ▼
Bot: "✅ Done! You're subscribed to 2 zone(s):
      Orchard, Tanjong Pagar"
```

### Flow 2: Reporting via GPS (`/report`)

```
User sends: /report
    │
    ▼
Bot: "📍 Where did you spot the warden?
      
      Share your location for the most accurate alert,
      or select a zone manually."
      
      [📍 Share Location]
      [📝 Select Zone Manually]
    │
    ▼
User shares GPS location
    │
    ▼
Bot: (calculates nearest zone)
     "📍 Detected zone: Tanjong Pagar
      🌐 GPS: 1.276432, 103.846021
      
      📝 Send a short description of the location:
      (e.g., 'outside Maxwell Food Centre')
      
      Or tap Skip to report without description."
      
      [⏭️ Skip] [❌ Cancel]
    │
    ├─────────────────────────┐
    ▼                         ▼
User types description    User taps Skip
    │                         │
    ▼                         ▼
Bot: "⚠️ Confirm warden sighting:
      
      📍 Zone: Tanjong Pagar
      📝 Location: [description]
      🌐 GPS: 1.276432, 103.846021"
      
      [✅ Confirm] [❌ Cancel]
    │
    ▼
User taps: [✅ Confirm]
    │
    ▼
Bot: "✅ Thanks! Alert sent to 47 users in Tanjong Pagar.
      
      🏆 You've reported 5 sighting(s)!
      Your badge: ⭐ Regular
      Your accuracy: 85% (12 ratings)"
    │
    ▼
    ┌─────────────────────────────────┐
    │      BROADCAST TO SUBSCRIBERS   │
    │      (excluding reporter)       │
    └─────────────────────────────────┘
    │
    ▼
Subscribers receive:

"🚨 WARDEN ALERT — Tanjong Pagar
 🕐 Spotted: 2:30 PM
 📝 Location: outside Maxwell Food Centre
 🌐 GPS: 1.276432, 103.846021
 👤 Reporter: ⭐ Regular ✅
 
 ⏰ Extend your parking now!
 
 ━━━━━━━━━━━━━━━━━━━━━
 Was this accurate? Your feedback helps!
 
 [👍 Warden was there] [👎 False alarm]"
```

### Flow 3: Manual Zone Selection (`/report`)

```
User sends: /report
    │
    ▼
User taps: [📝 Select Zone Manually]
    │
    ▼
Bot shows: Region selection (same as /subscribe flow)
           [Central] [Central North] [East] [West] [North] [North-East]
           [❌ Cancel]
    │
    ▼
User taps: [West]
    │
    ▼
Bot shows: Zones in West region
           [Jurong East] [Jurong West] [Clementi] ...
           [◀ Back to regions] [❌ Cancel]
    │
    ▼
User taps: [Queenstown]
    │
    ▼
Bot: "📍 Zone: Queenstown

      📝 Send a short description of the location:
      (e.g., 'outside Maxwell Food Centre' or 'Block 123 carpark')

      [⏭️ Skip] [❌ Cancel]"
    │
    ▼
(continues same as GPS flow)
```

### Flow 4: Feedback on Alerts

```
User receives alert with feedback buttons
    │
    ▼
User taps: [👍 Warden was there]
    │
    ▼
Bot: (toast) "👍 Thanks! Marked as accurate."
    │
    ▼
Alert message updates:

"🚨 WARDEN ALERT — Tanjong Pagar
 🕐 Spotted: 2:30 PM
 📝 Location: outside Maxwell Food Centre
 🌐 GPS: 1.276432, 103.846021
 👤 Reporter: ⭐ Regular ✅
 
 ⏰ Extend your parking now!
 
 ━━━━━━━━━━━━━━━━━━━━━
 📊 Feedback: 👍 6 / 👎 1
 Thanks for your feedback!
 
 [👍 Accurate (6)] [👎 False alarm (1)]"
```

### Flow 5: View Recent Sightings (`/recent`)

```
User sends: /recent
    │
    ▼
Bot: "📋 Recent sightings in your zones:
      
      🔴 Tanjong Pagar — 2 mins ago
         📝 Outside Maxwell Food Centre
         🌐 GPS: 1.276432, 103.846021
         👤 ⭐ Regular ✅
         📊 Feedback: 👍 5 / 👎 1
      
      🟡 Bugis — 12 mins ago
         📝 Near Bugis Junction carpark
         👤 🆕 New
      
      🟢 Orchard — 25 mins ago
         👤 ⭐⭐ Trusted ✅"
```

### Flow 6: View Stats (`/mystats`)

```
User sends: /mystats
    │
    ▼
Bot: "📊 Your Reporter Stats
      
      🏆 Badge: ⭐ Regular
      📝 Total reports: 8
      
      Accuracy Rating:
      👍 Positive: 15
      👎 Negative: 3
      
      ✨ Accuracy score: 83% ✅
      
      Badge Progression:
      📈 3 more reports for ⭐⭐ Trusted
      
      Accuracy Indicators:
      ✅ 80%+ — Highly reliable
      ⚠️ 50-79% — Mixed accuracy
      ❌ <50% — Low accuracy"
```

### Flow 7: Share Bot (`/share`)

```
User sends: /share
    │
    ▼
Bot: "📤 Share ParkWatch SG
      
      Forward the message below to your friends, family, or driver groups!
      
      The more users we have, the better the alerts work for everyone."
    │
    ▼
Bot sends shareable message:

"🚗 ParkWatch SG — Parking Warden Alerts

 Tired of parking tickets? Join 50+ drivers getting real-time warden alerts!
 
 ✅ Crowdsourced warden sightings
 ✅ Alerts for your subscribed zones
 ✅ GPS location + descriptions
 ✅ Reporter accuracy ratings
 ✅ 80 zones across Singapore
 
 How it works:
 1. Subscribe to zones you park in
 2. Get alerts when wardens spotted
 3. Spot a warden? Report it to help others!
 
 👉 Start now: https://t.me/YourBotName
 
 Shared by [User's Name]"
    │
    ▼
Bot: "💡 Best places to share:
      • WhatsApp family/friends groups
      • Office/condo/HDB Telegram groups
      • Facebook driver groups
      • Colleagues who drive to work
      
      Every new user makes the network stronger! 💪"
```

---

## Reputation System

### Reporter Badges

| Badge | Reports | Display |
|-------|---------|---------|
| New | 0–2 | 🆕 New |
| Regular | 3–10 | ⭐ Regular |
| Trusted | 11–50 | ⭐⭐ Trusted |
| Veteran | 51+ | 🏆 Veteran |

### Accuracy Score

```
Accuracy Score = Positive Feedback / Total Feedback
```

| Score | Indicator | Meaning |
|-------|-----------|---------|
| 80%+ | ✅ | Highly reliable |
| 50–79% | ⚠️ | Mixed accuracy |
| <50% | ❌ | Low reliability |

*Indicator only shows after 3+ feedback ratings*

### Feedback Rules

- Users can rate each sighting once (👍 or 👎)
- Users can change their rating (switches the vote)
- Cannot double-vote the same way
- Reporter cannot rate their own sightings
- Feedback updates in real-time on the alert message

---

## Alert Expiry Logic

| Time Since Report | Urgency | Display |
|-------------------|---------|---------|
| 0–5 mins | High | 🔴 |
| 5–15 mins | Medium | 🟡 |
| 15–30 mins | Low | 🟢 |
| >30 mins | Expired | Not shown in `/recent` |

---

## Zone Coverage (80 Zones)

### Central (16 zones)
Tanjong Pagar, Bugis, Orchard, Chinatown, Clarke Quay, Raffles Place, Marina Bay, City Hall, Dhoby Ghaut, Somerset, Tiong Bahru, Outram, Telok Ayer, Boat Quay, Robertson Quay, River Valley

### Central North (9 zones)
Novena, Toa Payoh, Bishan, Ang Mo Kio, Marymount, Caldecott, Thomson, Braddell, Lorong Chuan

### East (20 zones)
Tampines, Bedok, Paya Lebar, Katong, Pasir Ris, Changi, Simei, Eunos, Kembangan, Marine Parade, East Coast, Geylang, Aljunied, Kallang, Lavender, Joo Chiat, Siglap, Tai Seng, Ubi, MacPherson

### West (17 zones)
Jurong East, Jurong West, Clementi, Buona Vista, Boon Lay, Pioneer, Tuas, Queenstown, Commonwealth, HarbourFront, Telok Blangah, West Coast, Dover, Holland Village, Ghim Moh, Lakeside, Chinese Garden

### North (8 zones)
Woodlands, Yishun, Sembawang, Admiralty, Marsiling, Kranji, Canberra, Khatib

### North-East (10 zones)
Hougang, Sengkang, Punggol, Serangoon, Kovan, Potong Pasir, Bartley, Buangkok, Rivervale, Anchorvale

---

## Technical Architecture

### Current (Polling + Webhook)

```
┌─────────────────┐         ┌──────────────────────┐      ┌─────────────────┐
│   Telegram      │◄───────►│   Bot Server         │      │  Health Check   │
│   Users         │  API /  │   (Python)           │      │  HTTP Server    │
└─────────────────┘ Webhook └───────┬──────────────┘      │  GET /health    │
                                    │                      └─────────────────┘
                           ┌────────▼────────┐
                           │  SQLite (dev)   │     ┌─────────────────┐
                           │  PostgreSQL     │     │  Sentry         │
                           │  (production)   │     │  (error track)  │
                           └─────────────────┘     └─────────────────┘
```

Supports both polling (default, for development) and webhook mode (for production).
Set `WEBHOOK_URL` to enable webhook mode. Structured JSON logging available via `LOG_FORMAT=json`.

### Future (Scaled)

```
┌─────────────────┐         ┌─────────────────┐
│   Telegram      │◄───────►│   Bot Server    │
│   Users         │  Webhook │   (Python)      │
└─────────────────┘         └────────┬────────┘
                                     │
                            ┌────────▼────────┐
                            │   PostgreSQL    │
                            │   Database      │
                            └────────┬────────┘
                                     │
                            ┌────────▼────────┐
                            │   Redis Cache   │
                            │   (Rate Limits) │
                            └─────────────────┘
```

### Tech Stack

| Component | Technology |
|-----------|------------|
| Bot Framework | python-telegram-bot 21+ (async) |
| Language | Python 3.10+ |
| Config | python-dotenv |
| Database (dev) | SQLite via aiosqlite |
| Database (prod) | PostgreSQL via asyncpg (connection pooling) |
| Migrations | Alembic (versioned schema changes) |
| Logging | Structured JSON or human-readable text (`bot/logging_config.py`) |
| Error Tracking | Sentry (optional, via `sentry-sdk`) |
| Health Check | Asyncio HTTP server (`GET /health`) |
| Testing | pytest + pytest-asyncio (257 tests) |
| Linting | ruff (lint + format) |
| Type Checking | mypy |
| CI | GitHub Actions (lint, typecheck, test on 3.10/3.11/3.12) |
| Hosting | Local / Railway / Render / VPS |

### Database Schema

Data is stored in 6 tables with 5 indexes. Tables are created automatically on startup via `bot/database.py`. Schema changes are tracked via Alembic migrations in `alembic/versions/`.

```sql
-- User accounts, report counts, and warning tracking
users (telegram_id BIGINT PK, username TEXT, report_count INT, warnings INT DEFAULT 0, created_at TIMESTAMP)

-- Zone subscriptions (many-to-many)
subscriptions (telegram_id BIGINT, zone_name TEXT, created_at TIMESTAMP, PK(telegram_id, zone_name))

-- Warden sighting reports (with moderation flag)
sightings (id TEXT PK, zone TEXT, description TEXT, reported_at TIMESTAMP,
           reporter_id BIGINT, reporter_name TEXT, reporter_badge TEXT,
           lat REAL, lng REAL, feedback_positive INT, feedback_negative INT,
           flagged INT DEFAULT 0)

-- Feedback votes on sightings (FK cascades on sighting deletion)
feedback (sighting_id TEXT REFERENCES sightings(id) ON DELETE CASCADE,
         user_id BIGINT, vote TEXT, created_at TIMESTAMP, PK(sighting_id, user_id))

-- Admin audit log (Phase 8)
admin_actions (id INTEGER PK AUTOINCREMENT, admin_id BIGINT, action TEXT,
              target TEXT, detail TEXT, created_at TIMESTAMP)

-- Banned users (Phase 9)
banned_users (telegram_id BIGINT PK, banned_by BIGINT, reason TEXT, banned_at TIMESTAMP)
```

The database driver is selected automatically based on `DATABASE_URL`:
- No URL or `sqlite:///` prefix → SQLite (local file)
- `postgresql://` or `postgres://` prefix → PostgreSQL (connection pool, 2–10 connections)

---

## Spam Prevention & Moderation

1. **Rate Limiting**: Max 3 reports per user per hour
2. **Duplicate Detection**: GPS-aware — reports in the same zone within 5 mins are checked:
   - If both reports have GPS coordinates: duplicate only if within **200 meters** (Haversine distance). Reports further apart are allowed through, enabling multiple wardens in the same zone.
   - If either report lacks GPS: falls back to zone-level duplicate detection (same zone = duplicate).
   - Users without GPS receive a tip encouraging them to share location for better accuracy.
3. **Accuracy Tracking**: Low-accuracy reporters flagged with ❌
4. **Community Moderation**: Multiple 👎 ratings reduce trust
5. **Self-Rating Blocked**: Reporters cannot rate own sightings
6. **User Banning** (Phase 9): Admins can ban abusive users via `/admin ban`. Banned users cannot use any commands except `/start`. Bans clear subscriptions and notify the user.
7. **Content Moderation** (Phase 9): Admins can delete false sightings via `/admin delete`. Sightings are auto-flagged when negative feedback exceeds 70% (3+ votes). `/admin review` shows the moderation queue.
8. **Warning System** (Phase 9): Admins can warn users via `/admin warn`. After 3 warnings (configurable via `MAX_WARNINGS`), users are automatically banned.

---

## Growth Strategy

### Phase 1: Seed Network (Week 1)
- Personal network (friends, family, colleagues)
- Office building / condo groups
- `/share` command for easy forwarding

### Phase 2: Community Outreach (Week 2-3)
- Singapore driver Telegram groups
- Facebook groups (Singapore Drivers Unite, etc.)
- Reddit r/singapore
- HardwareZone forums

### Phase 3: Organic Growth
- Leaderboards for top reporters
- Incentivized sharing
- Target high-enforcement areas

---

## Roadmap

### MVP ✅
- [x] Zone subscriptions (80 zones, 6 regions)
- [x] Report flow (GPS + manual region→zone selection)
- [x] Alert broadcasting with feedback buttons
- [x] Feedback system (vote changing, self-rating prevention)
- [x] Reputation system (4-tier badges, accuracy scoring)
- [x] 80 zones with GPS coordinates
- [x] Share functionality with dynamic stats
- [x] User stats tracking

### Stability & UX ✅
- [x] Rate limiting (3 reports/hour)
- [x] GPS-aware duplicate detection (Haversine, 200m radius)
- [x] Multi-zone toggle subscription
- [x] ConversationHandler state machine (6 states, 300s timeout)
- [x] Native GPS share button

### Persistence ✅
- [x] Dual-driver database (SQLite / PostgreSQL)
- [x] Data persists across restarts
- [x] Accuracy from full history (SQL aggregates)
- [x] Scheduled cleanup (every 6 hours)

### Robustness ✅
- [x] Alert messages from structured DB data
- [x] Blocked user cleanup
- [x] Global error handler
- [x] Input sanitization (HTML, control chars)

### Bug Fixes (Phase 5) ✅
- [x] Timezone-aware datetime throughout
- [x] Collision-proof sighting IDs (UUID4)
- [x] Transaction-safe feedback updates
- [x] Rate limit timing fix
- [x] Foreign key constraints with cascading deletes
- [x] Proper Python packaging (relative imports)
- [x] Accuracy display fix, module-level ZONE_COORDS, share threshold

### Phase 6: Testing & CI ✅
- [x] `pyproject.toml` for packaging and tool configs (pytest, ruff, mypy)
- [x] pytest + pytest-asyncio test suite (105 tests, async auto mode)
- [x] Unit tests for pure functions (48 tests): `haversine_meters`, `get_reporter_badge`, `get_accuracy_indicator`, `sanitize_description`, `build_alert_message`, `generate_sighting_id`, zone data integrity
- [x] Database integration tests (57 tests): subscriptions, users, sightings, duplicate detection, rate limiting, feedback, accuracy, cleanup, driver detection
- [x] GitHub Actions CI pipeline: ruff lint/format, mypy type check, pytest across Python 3.10/3.11/3.12
- [x] Codebase lint cleanup: import sorting, unused variables, `contextlib.suppress` patterns

### Phase 7: Production Infrastructure ✅
- [x] Webhook mode for production (set `WEBHOOK_URL` to enable)
- [x] Health check endpoint (`GET /health` with JSON status)
- [x] Structured logging (JSON via `LOG_FORMAT=json`, text default)
- [x] Database migrations (Alembic with initial baseline migration)
- [x] Error tracking (Sentry, optional `sentry-sdk` dependency)
- [x] 22 new tests for Phase 7 features (127 total)

### Phase 8: Admin — Foundation & Visibility ✅
- [x] Admin authentication (`ADMIN_USER_IDS` env var, `admin_only` decorator — generic rejection for non-admins)
- [x] `/admin` help and `/admin help <command>` (brief + detailed help text)
- [x] `/admin stats` — global statistics dashboard (users, sightings, zones, feedback, top zones)
- [x] `/admin user <id or @username>` — user lookup (details, badge, accuracy, subscriptions, recent sightings)
- [x] `/admin zone <name>` — zone lookup (subscribers, sighting volume, top reporters, recent sightings)
- [x] Audit logging (`admin_actions` table, Alembic migration 002, `/admin log [count]`)
- [x] 43 new tests for all Phase 8 features (170 total)

### Phase 9: Admin — User Management & Moderation ✅
- [x] `/admin ban <id> [reason]`, `/admin unban <id>`, `/admin banlist`
- [x] Ban enforcement middleware (`ban_check` decorator on all user commands except `/start`)
- [x] `/admin delete <sighting_id> [confirm]` — two-step sighting deletion
- [x] `/admin review` — moderation queue (flagged sightings + low-accuracy reporters)
- [x] Auto-flag logic (sightings auto-flagged when >70% negative feedback, 3+ votes)
- [x] `/admin warn <id> [message]` — warning system with configurable auto-ban (MAX_WARNINGS=3)
- [x] User lookup shows ban status and warning count
- [x] Alembic migration 003, 47 new tests (217 total)

### Phase 10: Architecture, UX & Communication ✅
- [x] Documentation cleanup (README/spec consolidation)
- [x] Refactor `bot/main.py` into modules (`bot/zones.py`, `bot/utils.py`, `bot/handlers/`, `bot/services/`)
- [x] `/feedback <message>` — user-to-admin communication channel
- [x] `/admin announce all|zone <msg>` — admin-to-user broadcasts
- [x] UX discoverability (richer `/start` menu with inline keyboard actions)

### Phase 11: Admin — Operations
- [ ] `/admin maintenance on|off` — maintenance mode toggle
- [ ] `/admin purge sightings [days]` and `/admin purge user <id>` (GDPR)
- [ ] `/admin export stats` — CSV/JSON data export
- [ ] `/admin config [key] [value]` — view/adjust runtime settings

### Phase 12: Growth Features
- [ ] Leaderboards (weekly/monthly top reporters)
- [ ] Inline mode (`@parkwatch_bot Orchard` from any chat)
- [ ] Warden activity heatmaps by time/day
- [ ] Deep linking for referral tracking
- [ ] Multi-language support (i18n)

### Phase 13: Monetisation
- [ ] Freemium model (1 zone free, premium for all)
- [ ] Sponsored alerts from parking providers
- [ ] Business API for fleet managers

---

## Files

| File | Purpose |
|------|---------|
| `bot/main.py` | Application wiring, handler registration, lifecycle hooks, entrypoint |
| `bot/database.py` | Dual-driver database abstraction incl. admin + moderation + Phase 10 queries (SQLite/PostgreSQL) |
| `bot/zones.py` | Zone data: `ZONES` dict (80 zones, 6 regions), `ZONE_COORDS` coordinate table |
| `bot/utils.py` | Pure helpers: haversine, badges, accuracy, sanitization |
| `bot/handlers/user.py` | User commands: `/start`, `/subscribe`, `/unsubscribe`, `/myzones`, `/help`, `/mystats`, `/share`, `/feedback` |
| `bot/handlers/report.py` | Report flow: 6-state ConversationHandler, feedback handler, `/recent` |
| `bot/handlers/admin.py` | Admin system: `admin_only` decorator, `/admin` router, all subcommands incl. announce |
| `bot/services/notifications.py` | Alert broadcast with blocked-user cleanup |
| `bot/services/moderation.py` | `ban_check` decorator, `_check_auto_flag()` |
| `bot/ui/keyboards.py` | Keyboard builders: `build_zone_keyboard()` |
| `bot/ui/messages.py` | Message builders: `build_alert_message()` |
| `bot/health.py` | Health check HTTP server (asyncio, `GET /health`) |
| `bot/logging_config.py` | Structured logging configuration (text/JSON) |
| `config.py` | Environment config and bot settings (Phases 1–10, incl. `MAX_WARNINGS`) |
| `pyproject.toml` | Project metadata, dependencies, tool configs (pytest/ruff/mypy) |
| `requirements.txt` | Runtime dependencies (legacy compat for platforms without pyproject.toml) |
| `alembic.ini` | Alembic migration framework configuration |
| `alembic/env.py` | Alembic environment (reads DATABASE_URL from config.py) |
| `alembic/script.py.mako` | Alembic migration script template |
| `alembic/versions/001_initial_schema.py` | Baseline migration matching create_tables() |
| `alembic/versions/002_admin_actions_table.py` | Phase 8 migration: admin_actions audit log table |
| `alembic/versions/003_phase9_user_management.py` | Phase 9 migration: banned_users table, flagged/warnings columns |
| `tests/conftest.py` | Shared test fixtures (fresh SQLite DB per test) |
| `tests/test_unit.py` | Unit tests for pure functions (48 tests) |
| `tests/test_database.py` | Database integration tests (57 tests) |
| `tests/test_phase7.py` | Phase 7 infrastructure tests (22 tests) |
| `tests/test_phase8.py` | Phase 8 admin foundation tests (43 tests) |
| `tests/test_phase9.py` | Phase 9 user management & moderation tests (47 tests) |
| `tests/test_phase10.py` | Phase 10 tests: feedback, announce, start menu, UX (40 tests) |
| `.github/workflows/ci.yml` | GitHub Actions CI pipeline (lint + typecheck + test) |
| `.env.example` | Environment variable template (including Phase 9 vars) |
| `Procfile` | Heroku-style process declaration |
| `railway.toml` | Railway.app deployment config (with health check) |
| `runtime.txt` | Python version specification |
| `README.md` | Operator documentation (setup, config, deployment, commands) |
| `IMPROVEMENTS.md` | Code review and improvement plan |
| `parking_warden_bot_spec.md` | This file (product specification) |

---

*Last updated: February 2026 (Phase 10 complete — see IMPROVEMENTS.md)*

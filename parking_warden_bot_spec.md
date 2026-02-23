# ParkWatch SG — Complete Specification

## Overview

ParkWatch SG is a Telegram bot that crowdsources real-time parking warden sightings across Singapore. When a user spots a warden, they report it, and all users subscribed to that zone receive instant alerts.

**Core Value Proposition:** Save drivers from parking tickets by providing real-time, community-driven warden location alerts.

---

## User Commands

| Command | Description | Flow |
|---------|-------------|------|
| `/start` | Onboarding entrypoint with quick-action menu | Menu → region/zone selection (when subscribing) |
| `/subscribe` | Add more zones to subscriptions | Region → Zone selection |
| `/unsubscribe` | Remove zones from subscriptions | Zone list → Tap to remove |
| `/myzones` | View current subscribed zones | Display list |
| `/report` | Report a warden sighting | Location → Description → Confirm → Broadcast |
| `/recent` | View recent sightings (30 mins) | Display filtered list |
| `/mystats` | View reporter stats and accuracy | Display stats |
| `/share` | Generate invite message | Display shareable message |
| `/feedback <message>` | Send feedback to admins | Relay message, confirm to user |
| `/help` | Show all commands | Display help text |

## Admin Commands (Phases 8–11, including completed Phase 11 operations)

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
| `/admin maintenance on\|off` | 11 | Done | Toggle maintenance mode |
| `/admin config [key] [value]` | 11 | Done | View/adjust runtime settings |
| `/admin purge sightings [days]` | 11 | Done | Preview/confirm manual purge of old sightings |
| `/admin purge sightings zone <z> [days]` | 11 | Done | Preview/confirm zone-scoped sightings purge |
| `/admin purge user <user_id>` | 11 | Done | Preview/confirm GDPR-style user data purge |
| `/admin purge confirm` | 11 | Done | Execute pending purge operation |
| `/admin export stats [csv\|json]` | 11 | Done | Preview non-PII stats export |
| `/admin export stats [csv\|json] confirm` | 11 | Done | Generate export payload |

---

## User Flows

### Flow 1: Onboarding (`/start`)

```
User sends: /start
    │
    ▼
Bot: "Welcome to ParkWatch SG! 🚗
      I'll alert you when parking wardens are spotted nearby.

      What would you like to do?"
    │
    ▼
Bot shows quick-action menu (inline keyboard):
           [📍 Subscribe to Zones]
           [🚨 Report a Sighting]
           [📋 Recent Sightings]
           [📊 My Stats]
           [💬 Send Feedback]
           [❓ Help]
```

**Button behaviors (Approach C — Hybrid Edit-in-Place + Back Button):**

All buttons except Report and Subscribe edit the /start message in-place and show a `<< Back to Menu` button to return. This keeps interaction within a single message thread.

```
User taps: [📍 Subscribe to Zones]
    │
    ▼
Bot edits message → region selection keyboard (existing flow)
           [Central] [Central North] [East] [West] [North] [North-East]
    │
    ▼
User taps: [Central]  →  Zones  →  [✅ Done]
    │
    ▼
Bot: "✅ Subscribed to N zone(s): ...
      You'll now get alerts when wardens are spotted in these zones."
```

```
User taps: [🚨 Report a Sighting]
    │
    ▼
Bot: Deletes /start menu message
     Sends NEW message with report method choice:
     "📍 Where did you spot the warden?
      Share your location for the most accurate alert,
      or select a zone manually."
      [📍 Share Location]  [📝 Select Zone Manually]
    │
    ▼
(Enters full report ConversationHandler — see Flow 2/3)
```

```
User taps: [📋 Recent Sightings]
    │
    ▼
Bot edits message in-place → shows recent sightings
     (same content as /recent command):
     "📋 Recent sightings in your zones:
      🔴 Tanjong Pagar — 2 mins ago
         📝 Outside Maxwell Food Centre ..."

      [<< Back to Menu]
    │
    ▼
User taps: [<< Back to Menu]
    │
    ▼
Bot edits message → restores original /start quick-action menu
```

```
User taps: [📊 My Stats]
    │
    ▼
Bot edits message in-place → shows reporter stats
     (same content as /mystats command):
     "📊 Your Reporter Stats
      🏆 Badge: ⭐ Regular
      📝 Total reports: 8 ..."

      [<< Back to Menu]
```

```
User taps: [💬 Send Feedback]
    │
    ▼
Bot edits message in-place → shows feedback instructions:
     "💬 Send feedback to the admins by typing:
      /feedback Your message here

      Example: /feedback Love this bot! Could you add more zones?"

      [<< Back to Menu]
```

```
User taps: [❓ Help]
    │
    ▼
Bot edits message in-place → shows full help text
     (same content as /help command):
     "🚗 ParkWatch SG Commands

      Getting Started:
      /start — Main menu with quick actions
      /subscribe — Add more zones ..."

      [<< Back to Menu]
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
| Testing | pytest + pytest-asyncio (repository test suite) |
| Linting | ruff (lint + format) |
| Type Checking | mypy |
| CI | GitHub Actions (lint, typecheck, test on 3.10/3.11/3.12) |
| Hosting | Local / Railway / Render / VPS |

### Database Schema

Data is stored in 8 tables with 7 indexes. Tables are created automatically on startup via `bot/database.py`. Schema changes are tracked via Alembic migrations in `alembic/versions/`.

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

-- Runtime configuration overrides (Phase 11)
config_overrides (key TEXT PK, value TEXT NOT NULL, updated_by BIGINT NOT NULL, updated_at TIMESTAMP)

-- Rate limit tracking (Phase 11.5 — decoupled from admin_actions)
user_rate_limits (id INTEGER PK AUTOINCREMENT, user_id BIGINT, action TEXT, created_at TIMESTAMP)
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

## Roadmap & Files

Phases 1–11.5 are complete (MVP through admin operations and tech debt hardening). See [`IMPROVEMENTS.md`](IMPROVEMENTS.md) for the full improvement plan (Phases 12–15) and project file reference.

*Last updated: February 2026 (Phases 1–11.5 complete; roadmap aligned through Phase 15)*

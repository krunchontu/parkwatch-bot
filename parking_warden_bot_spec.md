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
| `/help` | Show all commands | Display help text |

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

### Current

```
┌─────────────────┐         ┌─────────────────┐
│   Telegram      │◄───────►│   Bot Server    │
│   Users         │   API   │   (Python)      │
└─────────────────┘         └────────┬────────┘
                                     │
                            ┌────────▼────────┐
                            │  SQLite (dev)   │
                            │  PostgreSQL     │
                            │  (production)   │
                            └─────────────────┘
```

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
| Hosting | Local / Railway / Render / VPS |

### Database Schema

Data is stored in 4 tables with 4 indexes. Tables are created automatically on startup via `bot/database.py`.

```sql
-- User accounts and report counts
users (telegram_id BIGINT PK, username TEXT, report_count INT, created_at TIMESTAMP)

-- Zone subscriptions (many-to-many)
subscriptions (telegram_id BIGINT, zone_name TEXT, created_at TIMESTAMP, PK(telegram_id, zone_name))

-- Warden sighting reports
sightings (id TEXT PK, zone TEXT, description TEXT, reported_at TIMESTAMP,
           reporter_id BIGINT, reporter_name TEXT, reporter_badge TEXT,
           lat REAL, lng REAL, feedback_positive INT, feedback_negative INT)

-- Feedback votes on sightings (FK cascades on sighting deletion)
feedback (sighting_id TEXT REFERENCES sightings(id) ON DELETE CASCADE,
         user_id BIGINT, vote TEXT, created_at TIMESTAMP, PK(sighting_id, user_id))
```

The database driver is selected automatically based on `DATABASE_URL`:
- No URL or `sqlite:///` prefix → SQLite (local file)
- `postgresql://` or `postgres://` prefix → PostgreSQL (connection pool, 2–10 connections)

---

## Spam Prevention

1. **Rate Limiting**: Max 3 reports per user per hour
2. **Duplicate Detection**: GPS-aware — reports in the same zone within 5 mins are checked:
   - If both reports have GPS coordinates: duplicate only if within **200 meters** (Haversine distance). Reports further apart are allowed through, enabling multiple wardens in the same zone.
   - If either report lacks GPS: falls back to zone-level duplicate detection (same zone = duplicate).
   - Users without GPS receive a tip encouraging them to share location for better accuracy.
3. **Accuracy Tracking**: Low-accuracy reporters flagged with ❌
4. **Community Moderation**: Multiple 👎 ratings reduce trust
5. **Self-Rating Blocked**: Reporters cannot rate own sightings

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

### Phase 6: Testing & CI
- [ ] pytest test suite
- [ ] GitHub Actions CI pipeline

### Phase 7: Production Readiness
- [ ] Webhook mode
- [ ] Health check endpoint
- [ ] Database migrations (Alembic)
- [ ] Admin commands

### Phase 8: Growth
- [ ] Leaderboards
- [ ] Inline mode
- [ ] Heatmaps
- [ ] Deep linking / referral tracking
- [ ] Multi-language (i18n)

### Phase 9: Monetisation
- [ ] Freemium model
- [ ] Sponsored alerts
- [ ] Business API

---

## Files

| File | Purpose |
|------|---------|
| `bot/main.py` | Bot logic, handlers, conversation flow (~1425 lines) |
| `bot/database.py` | Dual-driver database abstraction (~550 lines) |
| `config.py` | Environment config and bot settings |
| `requirements.txt` | Dependencies (`python-telegram-bot`, `python-dotenv`, `aiosqlite`, `asyncpg`) |
| `.env.example` | Environment variable template |
| `Procfile` | Heroku-style process declaration |
| `railway.toml` | Railway.app deployment config |
| `runtime.txt` | Python version specification |
| `README.md` | User-facing documentation |
| `IMPROVEMENTS.md` | Code review and improvement plan |
| `parking_warden_bot_spec.md` | This file (product specification) |

---

*Last updated: February 2026*

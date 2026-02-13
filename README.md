# ParkWatch SG Bot 🚗

Crowdsourced parking warden alerts for Singapore drivers. Get notified when wardens are spotted in your area — never get a parking ticket again.

---

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Commands Reference](#commands-reference)
- [How It Works](#how-it-works)
- [Zone Coverage](#zone-coverage)
- [Reputation System](#reputation-system)
- [Technical Details](#technical-details)
- [Development](#development)
- [Deployment](#deployment)
- [Roadmap](#roadmap)

---

## Features

### 🚨 Real-time Alerts
- Instant notifications when wardens are spotted in your subscribed zones
- Alerts include location description, GPS coordinates, and reporter reputation
- Urgency indicators based on how recent the sighting is

### 📍 Comprehensive Coverage
- **80 zones** across Singapore
- 6 regions: Central, Central North, East, West, North, North-East
- Auto-detects nearest zone from GPS location share

### 📊 Feedback & Trust System
- Rate alerts as 👍 Accurate or 👎 False alarm
- Reporter accuracy scores calculated from community feedback
- Visual indicators help identify reliable vs unreliable reporters

### 🏆 Gamification
- Badge progression from 🆕 New to 🏆 Veteran
- Track your stats with `/mystats`
- Accuracy ratings build your reputation

### 🛡️ Smart Duplicate Detection
- GPS-aware: reports within 200m in the same zone are grouped as duplicates
- Multiple wardens in the same zone are allowed when GPS shows they're far apart
- Falls back to zone-level detection when GPS is unavailable

### 📤 Easy Sharing
- Built-in `/share` command generates invite message
- Designed for viral growth through driver communities

---

## Quick Start

### Prerequisites
- Python 3.10+ (tested on 3.10, 3.11, 3.12)
- Telegram account
- Bot token from [@BotFather](https://t.me/BotFather)

### Installation

```bash
# 1. Clone or unzip the project
cd parkwatch-bot

# 2. Install dependencies
pip install -r requirements.txt

# Or install with dev tools (pytest, ruff, mypy):
pip install -e ".[dev]"

# 3. Create environment file
cp .env.example .env

# 4. Add your bot token to .env
# TELEGRAM_BOT_TOKEN=your_token_here

# 5. Run the bot
python -m bot.main
```

You should see:
```
2026-XX-XX XX:XX:XX - __main__ - INFO - 🚗 ParkWatch SG Bot starting...
```

### Get Your Bot Token

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Follow prompts to name your bot
4. Copy the token and add to your `.env` file

---

## Commands Reference

| Command | Description |
|---------|-------------|
| `/start` | Begin onboarding — select zones to subscribe |
| `/subscribe` | Add more zones to your subscriptions |
| `/unsubscribe` | Remove zones from your subscriptions |
| `/myzones` | View your current subscribed zones |
| `/report` | Report a warden sighting (GPS or manual) |
| `/recent` | View recent sightings in your zones (last 30 mins) |
| `/mystats` | View your reporter stats, badge, and accuracy |
| `/share` | Generate invite message to share with friends |
| `/help` | Show all commands and tips |

---

## How It Works

### For Users Receiving Alerts

1. **Subscribe** to zones where you frequently park (`/start` or `/subscribe`)
2. **Receive alerts** when someone reports a warden in your zone
3. **Rate the alert** using 👍/👎 buttons to help build trust
4. **Check recent sightings** with `/recent` before parking

### For Users Reporting Sightings

1. Spot a warden → Use `/report`
2. **Share location** (GPS) or **select zone manually**
3. **Add description** (e.g., "outside Maxwell Food Centre")
4. **Confirm** — duplicate check runs (GPS-aware: within 200m = duplicate, further apart = allowed)
5. **Alert broadcasts** to all zone subscribers
6. **Earn reputation** as your reports get positive feedback

### Alert Message Format

```
🚨 WARDEN ALERT — Tanjong Pagar
🕐 Spotted: 2:30 PM
📝 Location: Outside Maxwell Food Centre
🌐 GPS: 1.276432, 103.846021
👤 Reporter: ⭐ Regular ✅

⏰ Extend your parking now!

━━━━━━━━━━━━━━━━━━━━━
📊 Feedback: 👍 5 / 👎 1
Thanks for your feedback!

[👍 Accurate (5)] [👎 False alarm (1)]
```

### Recent Sightings Display

```
📋 Recent sightings in your zones:

🔴 Tanjong Pagar — 2 mins ago
   📝 Outside Maxwell Food Centre
   🌐 GPS: 1.276432, 103.846021
   👤 ⭐ Regular ✅
   📊 Feedback: 👍 5 / 👎 1

🟡 Bugis — 12 mins ago
   📝 Near Bugis Junction carpark
   👤 🆕 New
```

Urgency indicators:
- 🔴 0–5 mins ago (high urgency — warden likely still there)
- 🟡 5–15 mins ago (medium urgency)
- 🟢 15–30 mins ago (low urgency — may have moved on)

---

## Zone Coverage

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

## Reputation System

### Reporter Badges

Badges are earned by submitting reports:

| Badge | Reports Required |
|-------|------------------|
| 🆕 New | 0–2 reports |
| ⭐ Regular | 3–10 reports |
| ⭐⭐ Trusted | 11–50 reports |
| 🏆 Veteran | 51+ reports |

### Accuracy Score

Calculated from community feedback on your reports:

```
Accuracy = Positive Feedback / Total Feedback
```

| Indicator | Score | Meaning |
|-----------|-------|---------|
| ✅ | 80%+ | Highly reliable reporter |
| ⚠️ | 50–79% | Mixed accuracy |
| ❌ | <50% | Low reliability (possible spammer) |

*Note: Accuracy indicator only shows after receiving 3+ ratings*

### My Stats Example

```
📊 Your Reporter Stats

🏆 Badge: ⭐ Regular
📝 Total reports: 8

Accuracy Rating:
👍 Positive: 15
👎 Negative: 3

✨ Accuracy score: 83% ✅

Badge Progression:
📈 3 more reports for ⭐⭐ Trusted
```

---

## Technical Details

### Architecture

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

### Tech Stack

| Component | Technology |
|-----------|------------|
| Bot Framework | python-telegram-bot 21+ (async) |
| Language | Python 3.10+ |
| Config | python-dotenv |
| Database (dev) | SQLite via aiosqlite |
| Database (prod) | PostgreSQL via asyncpg (connection pooling) |
| Hosting | Local / Railway / Render / VPS |

### Project Structure

```
parkwatch-bot/
├── bot/
│   ├── __init__.py              # Package marker
│   ├── main.py                  # Bot logic, handlers, conversation flow (~1400 lines)
│   └── database.py              # Dual-driver DB abstraction (~550 lines)
├── tests/
│   ├── __init__.py              # Test package marker
│   ├── conftest.py              # Shared fixtures (fresh SQLite DB per test)
│   ├── test_unit.py             # Unit tests for pure functions (48 tests)
│   └── test_database.py         # Database integration tests (57 tests)
├── .github/
│   └── workflows/
│       └── ci.yml               # GitHub Actions CI (lint + typecheck + test)
├── config.py                    # Environment configuration & bot settings
├── pyproject.toml               # Project metadata, deps, tool configs
├── requirements.txt             # Runtime dependencies (legacy compat)
├── .env.example                 # Environment variable template
├── Procfile                     # Heroku-style process declaration
├── railway.toml                 # Railway.app deployment config
├── runtime.txt                  # Python version specification
├── parking_warden_bot_spec.md   # Full product specification
├── IMPROVEMENTS.md              # Code review & improvement plan
└── README.md                    # This file
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | Yes |
| `DATABASE_URL` | PostgreSQL connection string (SQLite used if omitted) | No |
| `DATABASE_PRIVATE_URL` | Railway internal DB URL (takes priority over `DATABASE_URL`) | No |
| `SIGHTING_RETENTION_DAYS` | Days to retain sighting data (default: 30) | No |
| `FEEDBACK_WINDOW_HOURS` | Hours feedback buttons remain active (default: 24) | No |

### Bot Settings (`config.py`)

| Setting | Default | Description |
|---------|---------|-------------|
| `SIGHTING_EXPIRY_MINUTES` | 30 | How long sightings remain active |
| `MAX_REPORTS_PER_HOUR` | 3 | Rate limit per user |
| `DUPLICATE_WINDOW_MINUTES` | 5 | Time window for duplicate detection |
| `DUPLICATE_RADIUS_METERS` | 200 | GPS radius for duplicate detection (Haversine) |
| `SIGHTING_RETENTION_DAYS` | 30 | Days to retain sighting data |
| `FEEDBACK_WINDOW_HOURS` | 24 | Hours feedback buttons remain active |

### Database Schema

Data is stored in 4 tables with 4 indexes. Tables are created automatically on startup.

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

-- Indexes
idx_sightings_zone_time ON sightings(zone, reported_at)
idx_sightings_reporter ON sightings(reporter_id)
idx_subscriptions_zone ON subscriptions(zone_name)
idx_feedback_sighting ON feedback(sighting_id)
```

**Local development** uses SQLite (`parkwatch.db` auto-created). **Production** uses PostgreSQL — just set `DATABASE_URL` and the database driver switches automatically.

---

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run only unit tests
pytest tests/test_unit.py

# Run only database tests
pytest tests/test_database.py
```

**Test suite summary** (105 tests):
- **48 unit tests** — pure functions (`haversine_meters`, `get_reporter_badge`, `get_accuracy_indicator`, `sanitize_description`, `build_alert_message`, `generate_sighting_id`) plus zone data integrity
- **57 integration tests** — database CRUD, subscriptions, sightings, feedback, accuracy, rate limiting, cleanup, and driver detection

### Linting & Type Checking

```bash
# Lint with ruff
ruff check .

# Check formatting
ruff format --check .

# Auto-fix lint issues
ruff check --fix .

# Apply formatting
ruff format .

# Type check
mypy bot/ config.py
```

### CI Pipeline

GitHub Actions runs automatically on every push/PR to `main`:
1. **Lint** — `ruff check` + `ruff format --check`
2. **Type Check** — `mypy bot/ config.py`
3. **Test** — `pytest -v` across Python 3.10, 3.11, 3.12

See `.github/workflows/ci.yml` for the full pipeline configuration.

---

## Deployment

### Local Development

```bash
python -m bot.main
```

Bot runs in foreground. Press Ctrl+C to stop.

### Production Deployment

#### Option 1: Railway (Recommended for beginners)

1. Push code to GitHub
2. Sign up at [Railway](https://railway.app)
3. Create new project → Deploy from GitHub repo
4. Add a PostgreSQL database service to the project
5. Add environment variable: `TELEGRAM_BOT_TOKEN`
6. Deploy — Railway auto-injects `DATABASE_URL` and handles the rest

#### Option 2: Render

1. Push code to GitHub
2. Sign up at [Render](https://render.com)
3. Create a PostgreSQL database (or skip for SQLite)
4. Create new **Background Worker** (not Web Service)
5. Connect your GitHub repo
6. Set build command: `pip install -r requirements.txt`
7. Set start command: `python -m bot.main`
8. Add environment variables: `TELEGRAM_BOT_TOKEN`, `DATABASE_URL` (from step 3)

#### Option 3: DigitalOcean / VPS

```bash
# SSH into your server
ssh user@your-server

# Clone repository
git clone https://github.com/yourusername/parkwatch-bot.git
cd parkwatch-bot

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "TELEGRAM_BOT_TOKEN=your_token_here" > .env

# Option A: Run with screen (keeps running after disconnect)
screen -S parkwatch
python -m bot.main
# Press Ctrl+A, then D to detach

# Option B: Run with systemd (auto-restart on crash)
# Create /etc/systemd/system/parkwatch.service
```

#### Systemd Service File

```ini
[Unit]
Description=ParkWatch SG Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/parkwatch-bot
ExecStart=/usr/bin/python3 -m bot.main
Restart=always
RestartSec=10
Environment=TELEGRAM_BOT_TOKEN=your_token_here

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable parkwatch
sudo systemctl start parkwatch
sudo systemctl status parkwatch
```

---

## Roadmap

### MVP ✅
- [x] Zone subscription system (80 zones, 6 regions)
- [x] Report flow (GPS + manual region→zone selection)
- [x] Location descriptions with input sanitization
- [x] Alert broadcasting to subscribers
- [x] Feedback system (👍/👎 with vote changing)
- [x] Reporter reputation (4-tier badges + accuracy score)
- [x] Urgency indicators on recent sightings
- [x] Share/invite functionality
- [x] User stats tracking

### Stability & UX ✅
- [x] Rate limiting (3 reports/hour per user)
- [x] GPS-aware duplicate detection (Haversine, 200m radius)
- [x] Self-rating prevention (server-side)
- [x] Multi-zone toggle subscription (keyboard stays open)
- [x] ConversationHandler state machine for report flow
- [x] Native GPS share button (`request_location=True`)

### Persistence ✅
- [x] Dual-driver database (SQLite dev / PostgreSQL prod)
- [x] Data persists across bot restarts
- [x] Accuracy scores from full history (SQL aggregates)
- [x] Scheduled cleanup job (every 6 hours)
- [x] Feedback window expiry (24h configurable)

### Robustness ✅
- [x] Alert messages rebuilt from structured DB data
- [x] Blocked user detection and subscription cleanup
- [x] Global error handler with user notification
- [x] Broadcast failure reporting to reporter

### Bug Fixes (Phase 5) ✅
- [x] Timezone-aware datetime throughout (`datetime.now(timezone.utc)`)
- [x] Collision-proof sighting IDs (UUID4)
- [x] Transaction-safe feedback updates (`Database.apply_feedback()`)
- [x] Rate limit timing fix (`.total_seconds()`)
- [x] Foreign key constraints with cascading deletes
- [x] Proper Python packaging (relative imports, `python -m bot.main`)
- [x] Accuracy display fix ("No ratings yet" for zero feedback)
- [x] Module-level ZONE_COORDS
- [x] Share message threshold (no "0+" on fresh installs)

### Testing & CI (Phase 6) ✅
- [x] `pyproject.toml` with project metadata and tool configs
- [x] pytest + pytest-asyncio test suite (105 tests)
- [x] Unit tests for pure functions (48 tests across 8 test classes)
- [x] Database integration tests (57 tests across 10 test classes)
- [x] GitHub Actions CI pipeline (ruff lint + mypy type check + pytest across 3.10/3.11/3.12)
- [x] Lint compliance: import sorting, unused variable cleanup, `contextlib.suppress` patterns

### Next: Production Infrastructure (Phase 7)
- [ ] Webhook mode for production
- [ ] Health check endpoint
- [ ] Structured logging (JSON)
- [ ] Database migrations (Alembic)
- [ ] Error tracking (Sentry)

### Future: Admin — Foundation & Visibility (Phase 8)
- [ ] Admin authentication (`ADMIN_USER_IDS` env var, `admin_only` decorator)
- [ ] `/admin` help command
- [ ] `/admin stats` — global statistics dashboard
- [ ] `/admin user <id>` / `/admin zone <name>` — lookup commands
- [ ] Audit logging (`admin_actions` table, `/admin log`)

### Future: Admin — User Management & Moderation (Phase 9)
- [ ] `/admin ban`, `/admin unban`, `/admin banlist`
- [ ] Ban enforcement middleware
- [ ] `/admin delete <sighting_id>` — remove false/spam sightings
- [ ] `/admin review` — moderation queue for flagged sightings
- [ ] `/admin warn <id>` — warning system with auto-ban escalation

### Future: Admin — Broadcast & Operations (Phase 10)
- [ ] `/admin broadcast` — message all users (with confirmation + delivery report)
- [ ] Targeted broadcast by zone or region
- [ ] `/admin maintenance on|off` — maintenance mode
- [ ] `/admin purge` — manual data cleanup + GDPR user deletion
- [ ] `/admin export stats` — CSV/JSON data export
- [ ] `/admin config` — view/adjust runtime settings without restart

### Future: Growth Features (Phase 11)
- [ ] Weekly/monthly leaderboard
- [ ] Inline mode for cross-chat queries
- [ ] Warden activity heatmaps by time/day
- [ ] Deep linking for referral tracking
- [ ] Multi-language support (i18n)

### Future: Monetisation (Phase 12)
- [ ] Freemium (1 zone free, premium for all zones)
- [ ] Sponsored alerts from parking providers
- [ ] Business API for fleet managers

---

## Troubleshooting

### Bot doesn't respond

1. Check that `TELEGRAM_BOT_TOKEN` is set correctly in `.env`
2. Ensure the `.env` file is in the `parkwatch-bot/` directory
3. Verify bot is running: you should see "ParkWatch SG Bot starting..."

### Module not found error

```bash
# Make sure you're in the right directory
cd parkwatch-bot
python -m bot.main
```

### asyncpg build error on Windows

asyncpg requires a C compiler to build on Windows. Options:
1. Install [Microsoft Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
2. Use WSL (Windows Subsystem for Linux)
3. For local dev only, asyncpg is not needed — SQLite is used automatically when `DATABASE_URL` is not set

### Rate limiting

If you're testing rapidly, Telegram may rate-limit. Wait a few minutes and try again.

---

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Install dev dependencies: `pip install -e ".[dev]"`
4. Make your changes
5. Run the checks: `ruff check . && mypy bot/ config.py && pytest`
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request — CI will run automatically

---

## License

MIT License — free to use, modify, and distribute.

---

## Acknowledgements

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) — Excellent Telegram Bot API wrapper
- Singapore drivers community — For the inspiration

---

Built with ❤️ for Singapore drivers tired of parking tickets.

**Stop getting summons. Start using ParkWatch SG.**

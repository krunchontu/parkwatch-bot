# ParkWatch SG Bot 🚗

Crowdsourced parking warden alerts for Singapore drivers. Get notified when wardens are spotted in your area — never get a parking ticket again.

**80 zones** across 6 regions · **real-time alerts** · **GPS-aware duplicate detection** · **community feedback & reputation** · **admin moderation suite**

---

## Table of Contents

- [Quick Start](#quick-start)
- [Commands](#commands)
- [Configuration](#configuration)
- [Development](#development)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

---

## Quick Start

### Prerequisites
- Python 3.10+ (tested on 3.10, 3.11, 3.12)
- Telegram account
- Bot token from [@BotFather](https://t.me/BotFather)

### Installation

```bash
cd parkwatch-bot
pip install -r requirements.txt       # runtime only
pip install -e ".[dev]"               # with dev tools (pytest, ruff, mypy)

# Configure
cp .env.example .env
# Edit .env — set TELEGRAM_BOT_TOKEN=your_token_here

# Run
python -m bot.main
```

You should see:
```
2026-XX-XX XX:XX:XX - bot.main - INFO - ParkWatch SG Bot v1.3.0 starting in polling mode
2026-XX-XX XX:XX:XX - bot.health - INFO - Health check server started on port 8080 (GET /health)
```

### Get Your Bot Token

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Follow prompts to name your bot
4. Copy the token and add to your `.env` file

---

## Commands

### User Commands

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

### Admin Commands

Require `ADMIN_USER_IDS` to be set. Non-admin users receive a generic "Unknown command" response.

| Command | Description |
|---------|-------------|
| `/admin` | Show all admin commands |
| `/admin stats` | Global statistics dashboard |
| `/admin user <id or @username>` | Look up user details and activity |
| `/admin zone <zone_name>` | Look up zone activity and stats |
| `/admin log [count]` | View admin actions audit log (default: 20, max: 100) |
| `/admin ban <user_id> [reason]` | Ban a user (clears subscriptions, notifies user) |
| `/admin unban <user_id>` | Remove a user's ban and reset warnings |
| `/admin banlist` | List all currently banned users |
| `/admin warn <user_id> [message]` | Send a warning (auto-ban after 3 warnings) |
| `/admin delete <sighting_id> [confirm]` | Delete a sighting (two-step confirmation) |
| `/admin review` | View moderation queue of flagged sightings |
| `/admin help [command]` | Detailed help for a specific admin command |

For detailed user flows, message formats, reputation rules, and zone lists, see [`parking_warden_bot_spec.md`](parking_warden_bot_spec.md).

---

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | Yes | — |
| `DATABASE_URL` | PostgreSQL connection string (SQLite if omitted) | No | SQLite |
| `DATABASE_PRIVATE_URL` | Railway internal DB URL (takes priority) | No | — |
| `WEBHOOK_URL` | Public URL for webhook mode (omit for polling) | No | — |
| `PORT` | Webhook listener port | No | `8443` |
| `HEALTH_CHECK_ENABLED` | Enable the health check HTTP server | No | `true` |
| `HEALTH_CHECK_PORT` | Health check server port | No | `$PORT` or `8080` |
| `LOG_FORMAT` | `text` (human-readable) or `json` (structured) | No | `text` |
| `SENTRY_DSN` | Sentry error tracking DSN | No | — |
| `ADMIN_USER_IDS` | Comma-separated admin Telegram user IDs | No | `""` |
| `MAX_WARNINGS` | Warnings before auto-ban (0 to disable) | No | `3` |
| `SIGHTING_RETENTION_DAYS` | Days to retain sighting data | No | `30` |
| `FEEDBACK_WINDOW_HOURS` | Hours feedback buttons remain active | No | `24` |

### Bot Settings (`config.py`)

| Setting | Default | Description |
|---------|---------|-------------|
| `SIGHTING_EXPIRY_MINUTES` | 30 | How long sightings appear in `/recent` |
| `MAX_REPORTS_PER_HOUR` | 3 | Rate limit per user |
| `DUPLICATE_WINDOW_MINUTES` | 5 | Time window for duplicate detection |
| `DUPLICATE_RADIUS_METERS` | 200 | GPS radius for duplicate detection (Haversine) |
| `BOT_VERSION` | 1.3.0 | Version reported in health check & Sentry |

---

## Development

### Project Structure

```
parkwatch-bot/
├── bot/
│   ├── __init__.py              # Package marker
│   ├── main.py                  # Bot logic, handlers, conversation flow
│   ├── database.py              # Dual-driver DB abstraction (SQLite/PostgreSQL)
│   ├── health.py                # Health check HTTP server (GET /health)
│   └── logging_config.py        # Structured logging (text/JSON modes)
├── tests/                       # 217 tests (unit, integration, infrastructure)
├── alembic/                     # Database migration scripts (3 migrations)
├── config.py                    # Environment configuration
├── pyproject.toml               # Project metadata, deps, tool configs
├── requirements.txt             # Runtime dependencies
└── .env.example                 # Environment variable template
```

### Running Tests

```bash
pip install -e ".[dev]"

pytest                        # all 217 tests
pytest -v                     # verbose output
pytest tests/test_unit.py     # unit tests only (48 tests)
pytest tests/test_database.py # integration tests only (57 tests)
```

### Linting & Type Checking

```bash
ruff check .                  # lint
ruff format --check .         # format check
mypy bot/ config.py           # type check
```

### CI Pipeline

GitHub Actions runs on every push/PR to `master`: lint → type check → test (Python 3.10, 3.11, 3.12). See `.github/workflows/ci.yml`.

---

## Deployment

### Polling vs Webhook

| | Polling (default) | Webhook |
|---|---|---|
| **How it works** | Bot polls Telegram for updates | Telegram pushes updates to your server |
| **Config** | No extra config needed | Set `WEBHOOK_URL` |
| **Best for** | Local dev, VPS | Railway, Render, Kubernetes |
| **Requires** | Outbound internet access | Public HTTPS URL |

### Health Check

A lightweight HTTP server runs alongside the bot (enabled by default) and responds to `GET /health`:

```json
{"status": "ok", "version": "1.3.0", "mode": "polling", "timestamp": "2026-02-13T12:00:00+00:00"}
```

### Structured Logging

Set `LOG_FORMAT=json` for JSON output suitable for log aggregation (Datadog, ELK, CloudWatch). Default is `text`.

### Error Tracking (Sentry)

```bash
pip install ".[sentry]"
# Set SENTRY_DSN in .env
```

Optional — bot works without it.

### Database Migrations (Alembic)

```bash
alembic upgrade head          # run migrations
alembic current               # check version
alembic revision -m "desc"    # create new migration
```

`create_tables()` is retained as fallback for fresh installs without Alembic.

### Railway (Recommended)

1. Push to GitHub → Create Railway project → Deploy from repo
2. Add PostgreSQL service
3. Set env vars: `TELEGRAM_BOT_TOKEN`, `WEBHOOK_URL` (your Railway app URL)
4. Deploy — Railway injects `DATABASE_URL` and `PORT`; health check pre-configured

### Render

1. Push to GitHub → Create **Background Worker** (polling) or **Web Service** (webhook)
2. Build: `pip install -r requirements.txt` · Start: `python -m bot.main`
3. Set env vars: `TELEGRAM_BOT_TOKEN`, `DATABASE_URL`, optionally `WEBHOOK_URL`

### VPS (DigitalOcean, etc.)

```bash
git clone <repo> && cd parkwatch-bot
pip install -r requirements.txt
echo "TELEGRAM_BOT_TOKEN=your_token" > .env
python -m bot.main              # foreground
# Or use screen/tmux/systemd for background persistence
```

<details>
<summary>systemd service file</summary>

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
sudo systemctl enable parkwatch && sudo systemctl start parkwatch
```

</details>

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Bot doesn't respond | Check `TELEGRAM_BOT_TOKEN` in `.env`; verify `.env` is in project root |
| `ModuleNotFoundError` | Run from project root: `python -m bot.main` |
| asyncpg build error (Windows) | Use WSL, or omit `DATABASE_URL` to use SQLite locally |
| Rate limiting during testing | Wait a few minutes — Telegram API rate limits |

---

## Contributing

1. Fork → branch (`feature/...`) → `pip install -e ".[dev]"`
2. Make changes → `ruff check . && mypy bot/ config.py && pytest`
3. Commit → push → open PR (CI runs automatically)

---

## Further Reading

- [`parking_warden_bot_spec.md`](parking_warden_bot_spec.md) — Product specification: user flows, message formats, reputation system, zone coverage, growth strategy
- [`IMPROVEMENTS.md`](IMPROVEMENTS.md) — Code review findings and improvement roadmap (Phases 1–13)

---

MIT License — free to use, modify, and distribute.

Built with ❤️ for Singapore drivers. **Stop getting summons. Start using ParkWatch SG.**

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

### 📤 Easy Sharing
- Built-in `/share` command generates invite message
- Designed for viral growth through driver communities

---

## Quick Start

### Prerequisites
- Python 3.10+ (tested on 3.14)
- Telegram account
- Bot token from [@BotFather](https://t.me/BotFather)

### Installation

```bash
# 1. Clone or unzip the project
cd parkwatch-bot

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create environment file
cp .env.example .env

# 4. Add your bot token to .env
# TELEGRAM_BOT_TOKEN=your_token_here

# 5. Run the bot
python bot/main.py
```

You should see:
```
2024-XX-XX XX:XX:XX - __main__ - INFO - 🚗 ParkWatch SG Bot starting...
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
4. **Confirm** — alert broadcasts to all zone subscribers
5. **Earn reputation** as your reports get positive feedback

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
                            │   In-Memory     │
                            │   Storage       │
                            │   (MVP)         │
                            └─────────────────┘
```

### Tech Stack

| Component | Technology |
|-----------|------------|
| Bot Framework | python-telegram-bot 21+ |
| Language | Python 3.10+ |
| Config | python-dotenv |
| Storage | In-memory (MVP) |

### Project Structure

```
parkwatch-bot/
├── bot/
│   ├── __init__.py
│   ├── main.py          # All bot logic (MVP single file)
│   ├── handlers/        # (Future: split handlers)
│   ├── services/        # (Future: business logic)
│   ├── models/          # (Future: database models)
│   └── utils/           # (Future: helpers)
├── config.py            # Environment configuration
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
└── README.md            # This file
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | Yes |
| `DATABASE_URL` | PostgreSQL connection string | No (future) |

### Data Structures (In-Memory)

```python
# User subscriptions: telegram_id -> set of zone names
user_subscriptions = {
    123456789: {"Tanjong Pagar", "Bugis"},
    987654321: {"Orchard", "Somerset"}
}

# Sightings: list of report objects
recent_sightings = [
    {
        'id': '1707123456_1234',
        'zone': 'Tanjong Pagar',
        'description': 'Outside Maxwell Food Centre',
        'time': datetime(2024, 2, 5, 14, 30),
        'reporter_id': 123456789,
        'reporter_name': 'john_doe',
        'reporter_badge': '⭐ Regular',
        'lat': 1.2764,
        'lng': 103.8460,
        'feedback_positive': 5,
        'feedback_negative': 1
    }
]

# User stats: telegram_id -> stats object
user_stats = {
    123456789: {
        'report_count': 15,
        'username': 'john_doe',
        'accuracy_score': 0.85,
        'total_feedback': 20
    }
}

# Feedback tracking: sighting_id -> {user_id: 'positive'/'negative'}
sighting_feedback = {
    '1707123456_1234': {
        111111: 'positive',
        222222: 'positive',
        333333: 'negative'
    }
}
```

---

## Deployment

### Local Development

```bash
python bot/main.py
```

Bot runs in foreground. Press Ctrl+C to stop.

### Production Deployment

#### Option 1: Railway (Recommended for beginners)

1. Push code to GitHub
2. Sign up at [Railway](https://railway.app)
3. Create new project → Deploy from GitHub repo
4. Add environment variable: `TELEGRAM_BOT_TOKEN`
5. Deploy — Railway handles the rest

#### Option 2: Render

1. Push code to GitHub
2. Sign up at [Render](https://render.com)
3. Create new **Background Worker** (not Web Service)
4. Connect your GitHub repo
5. Set build command: `pip install -r requirements.txt`
6. Set start command: `python bot/main.py`
7. Add environment variable: `TELEGRAM_BOT_TOKEN`

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
python bot/main.py
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
ExecStart=/usr/bin/python3 bot/main.py
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

### MVP (Current) ✅
- [x] Zone subscription system (80 zones)
- [x] Report flow (GPS + manual selection)
- [x] Location descriptions
- [x] Alert broadcasting to subscribers
- [x] Feedback system (👍/👎 buttons)
- [x] Reporter reputation (badges + accuracy score)
- [x] Urgency indicators on recent sightings
- [x] Share/invite functionality
- [x] User stats tracking

### Phase 2: Persistence
- [ ] PostgreSQL database integration
- [ ] Data persists across bot restarts
- [ ] Historical sighting analytics
- [ ] User preferences storage

### Phase 3: Growth Features
- [ ] Weekly/monthly leaderboard
- [ ] Warden activity heatmaps by time/day
- [ ] ML prediction for high-risk times/areas
- [ ] Direct link to extend parking in Parking.sg

### Phase 4: Monetisation
- [ ] Freemium (1 zone free, premium for all zones)
- [ ] Sponsored alerts from parking providers
- [ ] Business API for fleet managers

---

## Troubleshooting

### Bot doesn't respond

1. Check that `TELEGRAM_BOT_TOKEN` is set correctly in `.env`
2. Ensure the `.env` file is in the `parkwatch-bot/` directory
3. Verify bot is running: you should see "🚗 ParkWatch SG Bot starting..."

### Module not found error

```bash
# Make sure you're in the right directory
cd parkwatch-bot
python bot/main.py
```

### asyncpg build error on Windows

The MVP doesn't need asyncpg. If you see this error, check that `requirements.txt` only contains:
```
python-telegram-bot>=21.0
python-dotenv==1.0.0
```

### Rate limiting

If you're testing rapidly, Telegram may rate-limit. Wait a few minutes and try again.

---

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

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

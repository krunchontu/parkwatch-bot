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
Bot shows: All zones as buttons
           [Tanjong Pagar] [Bugis] [Orchard] ...
    │
    ▼
User taps: [Queenstown]
    │
    ▼
Bot: "📍 Zone: Queenstown
      
      📝 Send a short description of the location:
      (e.g., 'outside Maxwell Food Centre')
      
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

### Current (MVP)

```
┌─────────────────┐         ┌─────────────────┐
│   Telegram      │◄───────►│   Bot Server    │
│   Users         │   API   │   (Python)      │
└─────────────────┘         └────────┬────────┘
                                     │
                            ┌────────▼────────┐
                            │   In-Memory     │
                            │   Storage       │
                            └─────────────────┘
```

### Future (Production)

```
┌─────────────────┐         ┌─────────────────┐
│   Telegram      │◄───────►│   Bot Server    │
│   Users         │   API   │   (Python)      │
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
| Bot Framework | python-telegram-bot 21+ |
| Language | Python 3.10+ |
| Config | python-dotenv |
| Storage | In-memory (MVP) → PostgreSQL (future) |
| Hosting | Local / Railway / Render / VPS |

### Data Structures

```python
# User subscriptions
user_subscriptions = {
    telegram_id: set(zone_names)
}

# Sightings
recent_sightings = [
    {
        'id': str,              # Unique ID
        'zone': str,            # Zone name
        'description': str,     # Optional location details
        'time': datetime,       # When reported
        'reporter_id': int,     # Telegram user ID
        'reporter_name': str,   # Username/name
        'reporter_badge': str,  # Badge at time of report
        'lat': float,           # GPS latitude (optional)
        'lng': float,           # GPS longitude (optional)
        'feedback_positive': int,
        'feedback_negative': int
    }
]

# User stats
user_stats = {
    telegram_id: {
        'report_count': int,
        'username': str,
        'accuracy_score': float,  # 0.0 to 1.0
        'total_feedback': int
    }
}

# Feedback tracking (prevents double-voting)
sighting_feedback = {
    sighting_id: {
        user_id: 'positive' | 'negative'
    }
}
```

---

## Spam Prevention

1. **Rate Limiting**: Max 3 reports per user per hour
2. **Duplicate Detection**: Same zone reports within 5 mins grouped
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
- [x] Zone subscriptions
- [x] Report flow (GPS + manual)
- [x] Alert broadcasting
- [x] Feedback system
- [x] Reputation system
- [x] 80 zones
- [x] Share functionality
- [x] User stats

### Phase 2: Persistence
- [ ] PostgreSQL database
- [ ] Data persistence
- [ ] Historical analytics

### Phase 3: Growth
- [ ] Leaderboards
- [ ] Heatmaps
- [ ] ML predictions
- [ ] Parking.sg integration

### Phase 4: Monetisation
- [ ] Freemium model
- [ ] Sponsored alerts
- [ ] Business API

---

## Files

| File | Purpose |
|------|---------|
| `bot/main.py` | All bot logic |
| `config.py` | Environment config |
| `requirements.txt` | Dependencies |
| `.env.example` | Environment template |
| `README.md` | Documentation |

---

*Last updated: February 2025*

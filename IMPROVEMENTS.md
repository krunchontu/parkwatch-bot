# ParkWatch SG — Code Review & Improvement Plan

## Audit Summary

**Date:** 2026-02-11
**Scope:** Full code review against `parking_warden_bot_spec.md` and `README.md`
**Files reviewed:** `bot/main.py`, `config.py`, `requirements.txt`, `.env.example`

---

## Findings: Documentation vs Code Alignment

### Documented but NOT Implemented

| # | Feature | Where Documented | Code Status |
|---|---------|-----------------|-------------|
| 1 | Rate limiting (3 reports/hour) | Spec (Spam Prevention), `config.py:10` | `MAX_REPORTS_PER_HOUR` defined but never enforced in `main.py` |
| 2 | Duplicate detection (same zone within 5 mins) | Spec (Spam Prevention) | Not implemented |
| 3 | Self-rating prevention | Spec (Feedback Rules) | No server-side check in `handle_feedback()`. Broadcast excludes reporter (`main.py:538`) but no guard in the handler itself |
| 4 | Sighting expiry from config | `config.py:9` | Code hardcodes `timedelta(minutes=30)` at `main.py:695` instead of using `SIGHTING_EXPIRY_MINUTES` |

### Spec/README vs Code Mismatches

| # | Issue | Expected (Docs) | Actual (Code) |
|---|-------|-----------------|---------------|
| 1 | Manual zone report selection | Region -> Zone (two-step) | Flat list of all 80 zones (`handle_report_manual`, line 356) |
| 2 | Multi-zone subscription | Select multiple zones per interaction | Toggle one zone then message closes; must re-run `/subscribe` for each zone |
| 3 | Share Location button | Triggers GPS sharing | Shows text instructions to use attachment button (Telegram API limitation, but undocumented) |
| 4 | Location handler scope | Only active during report flow | Catches ANY location message at any time (`main.py:937`) |

---

## Findings: The Good

1. **Feature completeness** — All 9 commands implemented: `/start`, `/subscribe`, `/unsubscribe`, `/myzones`, `/report`, `/recent`, `/mystats`, `/share`, `/help`
2. **Feedback system** — Vote changing, double-vote prevention, real-time count updates on alert messages
3. **Zone data** — All 80 zones with GPS coordinates; zones match across spec, README, and code
4. **Callback routing** — Centralized `handle_callback` dispatcher (line 902)
5. **Documentation quality** — README covers setup, deployment (Railway/Render/VPS/systemd), troubleshooting, roadmap
6. **Secrets management** — `.env` + `.env.example` + `.gitignore` exclusion

---

## Findings: The Bad

1. **No rate limiting** — Config defines `MAX_REPORTS_PER_HOUR = 3` but code never checks it; unlimited spam possible
2. **No duplicate detection** — Same zone can be reported N times in a minute, subscribers get N separate alerts
3. **One-zone-at-a-time subscription** — Each selection closes the keyboard; subscribing to 5 zones = 5x `/subscribe`
4. **80-zone flat list** — `handle_report_manual` shows all zones as individual buttons with no grouping
5. **Unreliable accuracy scores** — `calculate_accuracy_score()` only iterates `recent_sightings` (capped at 100); old data lost
6. **Imports inside functions** — `datetime`, `time`, `random`, `math` imported inside function bodies instead of module top
7. **No description sanitization** — Only truncated to 100 chars, no further validation

---

## Findings: The Ugly

1. **All data lost on restart** — In-memory storage; any crash/restart wipes subscriptions, stats, sightings, feedback
2. **Fragile message text parsing** — `handle_feedback()` splits message text by newlines and string-matches to update feedback counts (lines 648-676); breaks if format changes
3. **Euclidean distance for GPS** — Ignores Earth's curvature; works for Singapore's scale but inaccurate at zone boundaries
4. **No conversation state machine** — Uses `context.user_data` flags; no `ConversationHandler`. Starting `/report` then `/start` then typing text could be misinterpreted
5. **No expired sighting cleanup for feedback** — Sightings evicted from 100-item list leave stale feedback buttons active
6. **Silent broadcast failures** — Failed sends logged but reporter sees success count that only reflects successes

---

## Improvement Plan

### Phase 1: Critical Fixes (Code-Doc Alignment & Stability)

Make the code match what the documentation already promises.

- [x] **1.1** Move top-level imports (`datetime`, `time`, `random`, `math`) to module top
- [x] **1.2** Use `config.SIGHTING_EXPIRY_MINUTES` instead of hardcoded 30
- [x] **1.3** Implement rate limiting (3 reports/user/hour) using `MAX_REPORTS_PER_HOUR`
- [x] **1.4** Implement duplicate detection (same zone within 5 mins)
- [x] **1.5** Add server-side self-rating prevention in `handle_feedback()`
- [x] **1.6** Guard `handle_location` so it only triggers during active report flow

### Phase 2: UX Improvements

Fix the user-facing friction points.

- [x] **2.1** Multi-zone subscription — keep keyboard open after each selection, add "Done" button
- [x] **2.2** Region-then-zone selection for manual report (match subscribe flow)
- [x] **2.3** Replace `ConversationHandler` for report flow (proper state machine)
- [x] **2.4** Improve Share Location flow — better instructions or use `KeyboardButton(request_location=True)`

### Phase 3: Data Persistence

Move from in-memory to durable storage.

- [x] **3.1** Choose and integrate database (SQLite for dev, PostgreSQL for prod)
- [x] **3.2** Design schema: `users`, `subscriptions`, `sightings`, `feedback` (4 tables + 4 indexes)
- [x] **3.3** Migrate all in-memory stores to database
- [x] **3.4** Proper accuracy score calculation from full history
- [x] **3.5** Sighting expiry/cleanup as scheduled job (every 6 hours)

### Phase 4: Robustness & Code Quality

Harden the bot for real-world usage.

- [ ] **4.1** Replace string-based message editing with stored sighting data for feedback updates
- [ ] **4.2** Use Haversine formula for GPS distance calculation
- [ ] **4.3** Add input sanitization for descriptions
- [ ] **4.4** Handle broadcast failures — retry logic or notify reporter of partial delivery
- [ ] **4.5** Clean up stale feedback buttons on expired sightings
- [ ] **4.6** Add error handling and graceful degradation throughout

### Phase 5: Growth Features (from Roadmap)

- [ ] **5.1** Leaderboard (weekly/monthly top reporters)
- [ ] **5.2** Warden activity heatmaps by time/day
- [ ] **5.3** ML prediction for high-risk times/areas
- [ ] **5.4** Freemium model (1 zone free, premium for all)

---

## File Reference

| File | Lines | Purpose |
|------|-------|---------|
| `bot/main.py` | ~1050 | All bot logic (handlers, DB integration, routing) |
| `bot/database.py` | ~444 | Dual-driver database abstraction (SQLite/PostgreSQL) |
| `config.py` | 13 | Environment config (`TELEGRAM_BOT_TOKEN`, `DATABASE_URL`, settings) |
| `requirements.txt` | 4 | `python-telegram-bot`, `python-dotenv`, `aiosqlite`, `asyncpg` |
| `.env.example` | 5 | Template for environment variables |
| `parking_warden_bot_spec.md` | 553 | Full specification with user flows |
| `README.md` | 505 | User-facing documentation |

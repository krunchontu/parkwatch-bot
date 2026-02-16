# Phase 11 Implementation Checklist (Mechanical Execution Order)

Goal: deliver Phase 11 exactly in dependency order with fail-fast behavior and complete docs/tests.

Canonical order from roadmap: **11.3 Runtime Config → 11.1 Maintenance Mode → 11.2 Data Management → 11.4 Testing closeout**.

---

## 0) Preflight + branch hygiene (no feature code yet)

1. Read `memlog/progress.md` and confirm next step is Phase 11.3.
2. Create a working branch and lock scope to Phase 11 only.
3. Run baseline checks and store results in `memlog/track-changes.md`.

**Commands (baseline):**
- `python -m pytest -q`
- `ruff check .`
- `ruff format --check .`
- `mypy .`

**Exit gate:** baseline failures are understood and recorded before any implementation.

---

## 1) 11.3 Runtime Configuration (must land first)

### 1.1 Migration + schema

**File order**
1. `alembic/versions/004_phase11_config_overrides.py` (new)
2. `bot/database.py` (`create_tables()` fallback parity for non-migrated local SQLite)

**Changes**
- Add `config_overrides` table:
  - `key TEXT PRIMARY KEY`
  - `value TEXT NOT NULL`
  - `updated_by BIGINT NOT NULL`
  - `updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP`
- Add index on `updated_at` for quick listing.

**Exit gate**
- Migration upgrades and downgrades cleanly.
- New table visible in both Alembic path and `create_tables()` fallback.

### 1.2 Runtime settings service (single source of truth)

**File order**
3. `bot/services/runtime_settings.py` (new)
4. `bot/services/__init__.py` (export service/types)

**Changes**
- Implement strict typed registry with defaults sourced from `config.py` values.
- Provide allowlist of mutable keys exactly from roadmap:
  - `MAX_REPORTS_PER_HOUR`
  - `DUPLICATE_WINDOW_MINUTES`
  - `DUPLICATE_RADIUS_METERS`
  - `SIGHTING_EXPIRY_MINUTES`
  - `SIGHTING_RETENTION_DAYS`
  - `FEEDBACK_WINDOW_HOURS`
  - `MAX_WARNINGS`
  - `MAINTENANCE_MODE`
  - `MAINTENANCE_MESSAGE`
- Forbid mutation of sensitive/static keys (`TELEGRAM_BOT_TOKEN`, `DATABASE_URL`, `DATABASE_PRIVATE_URL`, `ADMIN_USER_IDS`, webhook/network settings) by design: these keys are absent from mutable registry and reject with explicit error.
- Implement fail-fast parse/cast validators per key type (int/bool/float/str) with explicit error messages.
- Read path:
  - `get(key)` returns effective typed value (override if present, else default).
  - `get_many(keys)` for efficient multi-read.
- Write path:
  - `set_override(key, raw_value, actor_id)` with validation and old→new capture.
  - `reset_override(key, actor_id)` removing override and returning effective default.

**Exit gate**
- No handler/job reads mutable settings directly from module constants after refactor.
- Invalid key/value combinations fail immediately with user-safe error text and logged details.

### 1.3 Database methods for runtime config + auditing

**File order**
5. `bot/database.py`

**Changes**
- Add methods:
  - `get_config_override(key)`
  - `get_all_config_overrides()`
  - `upsert_config_override(key, value, updated_by, updated_at)`
  - `delete_config_override(key)`
- Ensure `/admin config` audit entries store old→new, actor, timestamp in `admin_actions.detail`.

**Exit gate**
- DB methods are driver-safe (SQLite/PostgreSQL parity).
- Audit entries contain deterministic structured detail.

### 1.4 Admin command surface for runtime config

**File order**
6. `bot/handlers/admin.py`
7. `bot/main.py` (if command wiring updates are needed)

**Changes**
- Add subcommands:
  - `/admin config` (list effective runtime settings + source default/override)
  - `/admin config <key> <value>` (validate/cast/set)
  - `/admin config reset <key>` (remove override; show effective default)
- Update `ADMIN_COMMANDS_HELP` and `ADMIN_COMMANDS_DETAILED`.
- Keep unauthorized behavior unchanged (`admin_only`).

**Exit gate**
- All config mutations are persisted, audited, and reflected immediately in read paths.

---

## 2) 11.1 Maintenance Mode (built on runtime config)

### 2.1 Maintenance state + guards

**File order**
8. `bot/services/maintenance.py` (new)
9. `bot/services/__init__.py`
10. `bot/handlers/user.py`
11. `bot/handlers/report.py`
12. `bot/main.py`
13. `bot/services/moderation.py` (if shared decorators are expanded)

**Changes**
- Implement `is_maintenance_enabled()` + message resolver using runtime settings service.
- Add user-facing guard decorator for non-admin flows:
  - block user commands and inline queries during maintenance.
  - admin commands stay available.
- Explicitly cancel active `/report` conversations during maintenance with cleanup + clear reason message.

**Exit gate**
- No user command bypasses maintenance.
- Report flow cancellation is deterministic and leaves no stale state.

### 2.2 Scheduler + health integration

**File order**
14. `bot/main.py` (`cleanup_job` and any scheduled jobs)
15. `bot/health.py`
16. `bot/handlers/admin.py` (`/admin stats` maintenance visibility)

**Changes**
- Soft-pause scheduled jobs by checking maintenance flag inside each job.
- Update `/health` payload to:
  - `status: "degraded"` when maintenance is on
  - include maintenance flag/message
- Add maintenance status section to `/admin stats` output.

**Exit gate**
- Health endpoint accurately reflects maintenance state.
- Jobs skip safely and log skip reason.

### 2.3 Admin maintenance commands

**File order**
17. `bot/handlers/admin.py`

**Changes**
- `/admin maintenance on [message]`
- `/admin maintenance off`
- Optional announce path: `/admin maintenance on --announce <msg>` with preview+confirm flow.
- Log all actions in audit trail.

**Exit gate**
- Toggle persists across restart (override-backed).
- Command UX is two-step where required (announce).

---

## 3) 11.2 Data Management

### 3.1 Purge sightings (manual, separate from retention job)

**File order**
18. `bot/database.py`
19. `bot/handlers/admin.py`

**Changes**
- `/admin purge sightings [days]` (ad-hoc manual purge)
- `/admin purge sightings zone <zone_name> [days]`
- Explicitly separate command code path from scheduled retention cleanup.
- Preview + confirm required before execution.

**Exit gate**
- Manual purge does not alter scheduled cleanup configuration or cadence.

### 3.2 GDPR-complete user purge + counter integrity

**File order**
20. `bot/database.py`
21. `bot/handlers/admin.py`

**Changes**
- `/admin purge user <user_id>` removes:
  - user row
  - subscriptions
  - sightings
  - feedback received
  - feedback given
  - bans
  - warnings
  - admin-action references as policy dictates
- Recalculate affected sighting feedback counters transactionally when deleting feedback given by purged user.
- Preview + confirm required.

**Exit gate**
- No orphan records remain.
- Denormalized counters match recomputed totals post-purge.

### 3.3 Export stats

**File order**
22. `bot/database.py`
23. `bot/handlers/admin.py`

**Changes**
- `/admin export stats [csv|json]`
- Default CSV; optional JSON.
- Exclude personal data by default.
- Preview + confirm before generation.

**Exit gate**
- Output format deterministic and safe for operators.

---

## 4) 11.4 Testing (must pass before phase close)

**File order**
24. `tests/test_phase11_runtime_config.py` (new)
25. `tests/test_phase11_maintenance.py` (new)
26. `tests/test_phase11_data_management.py` (new)
27. `tests/test_phase11_migration.py` (new)

**Coverage matrix**
- Runtime settings:
  - allowlist enforcement
  - disallowed key mutation
  - type casting success/failure
  - reset semantics
  - old→new audit detail
- Maintenance:
  - user command blocking
  - admin command allowed
  - report conversation cancellation and state cleanup
  - inline blocking
  - scheduled-job skip behavior
  - `/health` degraded payload
- Data management:
  - purge preview/confirm handshake
  - purge sightings global + by zone
  - purge user completeness
  - transactional feedback counter recomputation
  - CSV/JSON export generation + privacy defaults
- Migration:
  - upgrade creates `config_overrides`
  - downgrade removes it cleanly

**Exit gate**
- New tests pass on SQLite local path.
- Existing suite remains green.

---

## 5) Documentation + memlog closure (required for quality)

**File order**
28. `README.md` (admin command docs + operations notes)
29. `parking_warden_bot_spec.md` (mark Phase 11 items completed with exact command behavior)
30. `IMPROVEMENTS.md` (check off 11.x/11.4 items + outcome notes)
31. `memlog/track-changes.md` (diff summary, rationale, validation)
32. `memlog/progress.md` (phase transition + next steps)
33. `memlog/errors.md` (only if issues occurred)

**Docs acceptance criteria**
- README command examples match exact parser behavior.
- Spec and improvements docs stay synchronized.
- memlog includes what changed, why, and how validated.

---

## 6) Final verification + release checklist

1. Run full quality gate:
   - `ruff check .`
   - `ruff format --check .`
   - `mypy .`
   - `python -m pytest -q`
2. Run targeted Phase 11 tests independently.
3. Confirm no TODOs left in new code.
4. Update changelog/memlog one final time.
5. Prepare PR summary with:
   - dependency-ordered implementation proof
   - test matrix/results
   - rollback notes (migration downgrade + override reset commands)

**Final exit gate:**
- All Phase 11 checklist items are complete, tested, and documented with no roadmap drift.

<!-- NEXT ACTION -->
1. Save all current changes
2. Paste THIS message to resume workflow
3. Confirm by stating: "Proceed to Phase 11.3 implementation"

✅ Completed: Phase 11 mechanical execution checklist authored
➡️ Next Task: Implement Phase 11.3 runtime configuration in code

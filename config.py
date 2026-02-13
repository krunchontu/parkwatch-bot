import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Railway injects DATABASE_PRIVATE_URL for internal networking (faster, no egress cost).
# Fall back to DATABASE_URL for compatibility with other platforms.
DATABASE_URL = os.getenv("DATABASE_PRIVATE_URL") or os.getenv("DATABASE_URL")

# Bot settings
SIGHTING_EXPIRY_MINUTES = 30
MAX_REPORTS_PER_HOUR = 3
DUPLICATE_WINDOW_MINUTES = 5
DUPLICATE_RADIUS_METERS = 200
SIGHTING_RETENTION_DAYS = int(os.getenv("SIGHTING_RETENTION_DAYS", "30"))
FEEDBACK_WINDOW_HOURS = int(os.getenv("FEEDBACK_WINDOW_HOURS", "24"))

# --- Phase 7: Production Infrastructure ---

# Webhook mode: set WEBHOOK_URL to enable (e.g. "https://myapp.up.railway.app")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", "8443"))

# Health check endpoint (runs on a separate lightweight HTTP server)
HEALTH_CHECK_ENABLED = os.getenv("HEALTH_CHECK_ENABLED", "true").lower() in ("true", "1", "yes")
HEALTH_CHECK_PORT = int(os.getenv("HEALTH_CHECK_PORT", os.getenv("PORT", "8080")))

# Structured logging: "text" (human-readable, default) or "json" (for log aggregation)
LOG_FORMAT = os.getenv("LOG_FORMAT", "text")

# Sentry error tracking: set DSN to enable (e.g. "https://key@o0.ingest.sentry.io/0")
SENTRY_DSN = os.getenv("SENTRY_DSN")

# --- Phase 8: Admin Foundation ---

# Admin authentication: comma-separated Telegram user IDs authorized as admins
ADMIN_USER_IDS: set[int] = set()
_admin_ids_raw = os.getenv("ADMIN_USER_IDS", "")
if _admin_ids_raw.strip():
    for _id in _admin_ids_raw.split(","):
        _id = _id.strip()
        if _id.isdigit():
            ADMIN_USER_IDS.add(int(_id))

# Bot version (for health check and Sentry release tracking)
BOT_VERSION = "1.2.0"

import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Bot settings
SIGHTING_EXPIRY_MINUTES = 30
MAX_REPORTS_PER_HOUR = 3
SIGHTING_RETENTION_DAYS = int(os.getenv("SIGHTING_RETENTION_DAYS", "30"))

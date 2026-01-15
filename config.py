import os

# ===============================
# TELEGRAM BOT CONFIG
# ===============================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN not set in Railway environment variables")


# ===============================
# ADMINS
# ===============================
# Replace with your real Telegram user IDs
# Example: {123456789, 987654321}
ADMIN_IDS = {
    int(x)
    for x in os.getenv("ADMIN_IDS", "123456789").split(",")
}


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ===============================
# DATABASE
# ===============================
# Railway persistent volume path (optional override)
DB_PATH = os.getenv("DB_PATH", "data.db")


# ===============================
# BOT SETTINGS
# ===============================
BOT_NAME = os.getenv("BOT_NAME", "MyTelegramBot")
START_COINS = int(os.getenv("START_COINS", 10))
DAILY_REWARD = int(os.getenv("DAILY_REWARD", 5))

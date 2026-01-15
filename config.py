import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Add your real Telegram user IDs here
ADMIN_IDS = {
    8359504121,
}

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment variables")

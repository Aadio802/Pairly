from aiogram import Router
from aiogram.types import Message
from datetime import datetime, timedelta

from database import (
    is_premium,
    add_premium,
    get_sunflowers,
    add_sunflowers,
)

router = Router()

TEMP_PREMIUM_COST = 50      # sunflowers
TEMP_PREMIUM_DAYS = 3
TEMP_PREMIUM_COOLDOWN = 15  # days

# in-memory cooldown tracker (persist later if needed)
temp_premium_last_used = {}  # user_id -> datetime


def days_left(until: str | None) -> int:
    if not until:
        return 0
    return max(0, (datetime.fromisoformat(until) - datetime.utcnow()).days)


@router.message(commands=["premium"])
async def premium_status(message: Message):
    user_id = message.from_user.id
    premium = await is_premium(user_id)

    if premium:
        await message.reply(
            "✨ <b>You are a Premium user</b>\n\n"
            "Benefits:\n"
            "• Priority matching\n"
            "• Better partners\n"
            "• Limited link sharing\n"
            "• Pets access\n"
            "• Games access"
        )
    else:
        await message.reply(
            "💎 <b>Pairly Premium</b>\n\n"
            "Benefits:\n"
            "• Priority matching\n"
            "• Better partners\n"
            "• Limited link sharing\n"
            "• Pets access\n"
            "• Games access\n"
            "• Gardens (paid premium only)\n\n"
            "Use Telegram Stars to upgrade\n"
            "or buy <b>3-day temporary premium</b> using 🌻 sunflowers."
        )


@router.message(commands=["temp_premium"])
async def buy_temp_premium(message: Message):
    user_id = message.from_user.id

    last_used = temp_premium_last_used.get(user_id)
    if last_used and datetime.utcnow() - last_used < timedelta(days=TEMP_PREMIUM_COOLDOWN):
        await message.reply("⏳ You can buy temporary premium again later.")
        return

    balance = await get_sunflowers(user_id)
    if balance < TEMP_PREMIUM_COST:
        await message.reply("❌ Not enough 🌻 sunflowers.")
        return

    # deduct from games bucket (non-decaying)
    await add_sunflowers(user_id, -TEMP_PREMIUM_COST, source="game")
    await add_premium(user_id, TEMP_PREMIUM_DAYS, temporary=True)

    temp_premium_last_used[user_id] = datetime.utcnow()

    await message.reply(
        "✅ <b>Temporary Premium Activated!</b>\n\n"
        "Duration: 3 days\n"
        "Cooldown: 15 days\n\n"
        "Enjoy your perks ✨"
    )


@router.message(commands=["how"])
async def how_it_works(message: Message):
    await message.reply(
        "🌻 <b>How Pairly Works</b>\n\n"
        "<b>Sunflowers</b>\n"
        "• Earn from games, streaks, ratings\n"
        "• Spend on pets & temporary premium\n\n"
        "<b>Streaks 🔥</b>\n"
        "• Active daily chatting builds streaks\n"
        "• Losing streak removes only streak 🌻\n\n"
        "<b>Pets 🐾</b>\n"
        "• Protect your streak\n"
        "• Disappear after use\n\n"
        "<b>Games 🎮</b>\n"
        "• Play inside chats\n"
        "• Bet 🌻, winner takes more\n\n"
        "<b>Premium 💎</b>\n"
        "• Priority matching\n"
        "• Better partners\n"
        "• Link sharing\n"
        "• Gardens (paid only)\n\n"
        "Anonymous chats are monitored for safety 👁️"
    )

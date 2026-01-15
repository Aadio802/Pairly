import os
import asyncio
import time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import (
    init_db,
    ensure_user,
    get_rating_stats,
    add_rating,
    save_cooldown
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

queue = []
chat_pairs = {}
pending_rating = {}

# =========================
# START
# =========================

@dp.message(Command("start"))
async def start(message: types.Message):
    await ensure_user(message.from_user.id)
    await message.answer(
        "👋 Welcome to Pairly\n\n"
        "You can talk to strangers anonymously.\n"
        "You may encounter unfiltered content.\n\n"
        "🌟 Premium gives:\n"
        "• Better matches\n"
        "• High-rated partners\n"
        "• Gender preference\n"
        "• Link sharing\n\n"
        "🌻 Earn Sunflowers by:\n"
        "• Good ratings\n"
        "• Streaks\n"
        "• Games\n\n"
        "By using /find or /next you agree to the rules."
    )

# =========================
# FIND MATCH
# =========================

@dp.message(Command("find"))
async def find(message: types.Message):
    uid = message.from_user.id
    await ensure_user(uid)

    if uid in chat_pairs:
        await message.answer("❌ You are already in a chat.")
        return

    if uid in queue:
        await message.answer("⏳ Already searching...")
        return

    if queue:
        partner = queue.pop(0)

        chat_pairs[uid] = partner
        chat_pairs[partner] = uid

        await send_match(uid, partner)
        await send_match(partner, uid)

    else:
        queue.append(uid)
        await message.answer("🔍 Searching for a stranger...")

async def send_match(user, partner):
    stats = await get_rating_stats(partner)
    if stats:
        avg, count = stats
        rating_text = f"⭐ {avg} rated by {count} people"
    else:
        rating_text = "⭐ New user (not rated yet)"

    await bot.send_message(
        user,
        f"✅ Connected to a stranger!\n{rating_text}"
    )

# =========================
# NEXT
# =========================

@dp.message(Command("next"))
async def next_chat(message: types.Message):
    uid = message.from_user.id

    if uid not in chat_pairs:
        await message.answer("❌ You're not in a chat.")
        return

    partner = chat_pairs.pop(uid)
    chat_pairs.pop(partner, None)

    await ask_rating(uid, partner)
    await ask_rating(partner, uid)

    await find(message)

# =========================
# STOP
# =========================

@dp.message(Command("stop"))
async def stop_chat(message: types.Message):
    uid = message.from_user.id

    if uid not in chat_pairs:
        await message.answer("❌ You're not in a chat.")
        return

    partner = chat_pairs.pop(uid)
    chat_pairs.pop(partner, None)

    await ask_rating(uid, partner)
    await ask_rating(partner, uid)

    await message.answer("👋 Chat ended.")

# =========================
# RELAY
# =========================

@dp.message()
async def relay(message: types.Message):
    uid = message.from_user.id
    if uid in chat_pairs:
        await bot.send_message(chat_pairs[uid], message.text)

# =========================
# RATING SYSTEM
# =========================

async def ask_rating(user, partner):
    pending_rating[user] = partner

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1️⃣", callback_data="rate_1"),
            InlineKeyboardButton(text="2️⃣", callback_data="rate_2"),
            InlineKeyboardButton(text="3️⃣", callback_data="rate_3"),
            InlineKeyboardButton(text="4️⃣", callback_data="rate_4"),
            InlineKeyboardButton(text="5️⃣", callback_data="rate_5"),
        ]
    ])

    await bot.send_message(
        user,
        "⭐ Please rate your last partner:",
        reply_markup=kb
    )

@dp.callback_query(lambda c: c.data.startswith("rate_"))
async def handle_rating(call: types.CallbackQuery):
    user = call.from_user.id

    if user not in pending_rating:
        await call.answer("Rating expired.", show_alert=True)
        return

    rating = int(call.data.split("_")[1])
    partner = pending_rating.pop(user)

    await add_rating(user, partner, rating)
    await save_cooldown(user, partner)

    await call.message.edit_text(
        "✅ Thanks for your rating!\n"
        "Your feedback helps improve matches."
    )
    await call.answer()

# =========================
# MAIN
# =========================

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

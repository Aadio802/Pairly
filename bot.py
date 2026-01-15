import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import (
    init_db,
    ensure_user,
    set_gender,
    get_gender,
    save_cooldown,
    recently_matched,
    add_rating,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# =========================
# MEMORY STATE
# =========================
queue = []
chat_pairs = {}
searching = set()
pending_ratings = {}  # user_id -> partner_id

# =========================
# START
# =========================
@dp.message(Command("start"))
async def start(message: types.Message):
    await ensure_user(message.from_user.id)
    await message.answer(
        "👋 Welcome to Pairly\n\n"
        "Chat anonymously with strangers.\n"
        "Admins monitor chats.\n\n"
        "🌟 Premium:\n"
        "• Better matches\n"
        "• High-rated users\n"
        "• Gender preference\n"
        "• Link sharing\n\n"
        "Set gender:\n"
        "/male or /female\n\n"
        "Use /find to start."
    )

# =========================
# GENDER
# =========================
@dp.message(Command("male"))
async def male(message: types.Message):
    await set_gender(message.from_user.id, "male")
    await message.answer("✅ Gender set to Male.")

@dp.message(Command("female"))
async def female(message: types.Message):
    await set_gender(message.from_user.id, "female")
    await message.answer("✅ Gender set to Female.")

# =========================
# FIND / NEXT
# =========================
@dp.message(Command("find"))
@dp.message(Command("next"))
async def find(message: types.Message):
    uid = message.from_user.id

    if uid in chat_pairs:
        await message.answer("⚠️ You're already in a chat.")
        return

    if uid in searching:
        await message.answer("⏳ Already searching...")
        return

    if not await get_gender(uid):
        await message.answer("❗ Set gender first: /male or /female")
        return

    partner = None
    for u in queue:
        if u != uid and not await recently_matched(uid, u):
            partner = u
            queue.remove(u)
            break

    if partner:
        chat_pairs[uid] = partner
        chat_pairs[partner] = uid
        searching.discard(uid)
        searching.discard(partner)

        await bot.send_message(uid, "🔗 Connected to a stranger!")
        await bot.send_message(partner, "🔗 Connected to a stranger!")
    else:
        queue.append(uid)
        searching.add(uid)
        await message.answer("🔍 Searching for a partner...")

# =========================
# STOP (ENDS CHAT + RATE)
# =========================
@dp.message(Command("stop"))
async def stop(message: types.Message):
    uid = message.from_user.id

    if uid not in chat_pairs:
        await message.answer("⚠️ You're not in a chat.")
        return

    partner = chat_pairs.pop(uid)
    chat_pairs.pop(partner, None)

    await save_cooldown(uid, partner)
    await save_cooldown(partner, uid)

    pending_ratings[uid] = partner
    pending_ratings[partner] = uid

    await bot.send_message(partner, "❌ Stranger left the chat.")
    await message.answer("❌ Chat ended.\n\nPlease rate your partner:")

    await send_rating_buttons(uid)
    await send_rating_buttons(partner)

# =========================
# RATING BUTTONS
# =========================
async def send_rating_buttons(user_id):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⭐1", callback_data="rate_1"),
                InlineKeyboardButton(text="⭐2", callback_data="rate_2"),
                InlineKeyboardButton(text="⭐3", callback_data="rate_3"),
                InlineKeyboardButton(text="⭐4", callback_data="rate_4"),
                InlineKeyboardButton(text="⭐5", callback_data="rate_5"),
            ]
        ]
    )
    await bot.send_message(user_id, "Rate your experience:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("rate_"))
async def handle_rating(callback: types.CallbackQuery):
    rater = callback.from_user.id

    if rater not in pending_ratings:
        await callback.answer("⚠️ Rating already submitted.", show_alert=True)
        return

    rating = int(callback.data.split("_")[1])
    rated_user = pending_ratings.pop(rater)

    await add_rating(rated_user, rating)

    await callback.message.edit_text("✅ Thanks for rating!")
    await callback.answer()

# =========================
# RELAY CHAT MESSAGES
# =========================
@dp.message()
async def relay(message: types.Message):
    uid = message.from_user.id
    if uid in chat_pairs:
        await bot.send_message(chat_pairs[uid], message.text)

# =========================
# MAIN
# =========================
async def main():
    await init_db()
    print("🤖 Pairly started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

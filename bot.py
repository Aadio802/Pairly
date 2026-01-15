import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import aiosqlite

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not found in environment variables")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# =========================
# GLOBAL STATE (TEMP)
# =========================

search_queue = []
active_chats = {}        # user_id -> partner_id
user_searching = set()   # users currently searching

# =========================
# DATABASE INIT (MINIMAL)
# =========================

async def init_db():
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            gender TEXT,
            first_start INTEGER DEFAULT 1
        )
        """)
        await db.commit()

# =========================
# HELPERS
# =========================

async def is_first_start(user_id: int) -> bool:
    async with aiosqlite.connect("bot.db") as db:
        cur = await db.execute("SELECT first_start FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return row is None or row[0] == 1

async def mark_started(user_id: int):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("""
        INSERT INTO users (user_id, first_start)
        VALUES (?, 0)
        ON CONFLICT(user_id) DO UPDATE SET first_start=0
        """, (user_id,))
        await db.commit()

async def set_gender(user_id: int, gender: str):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("""
        INSERT INTO users (user_id, gender)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET gender=?
        """, (user_id, gender, gender))
        await db.commit()

# =========================
# /START
# =========================

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = message.from_user.id

    if await is_first_start(user_id):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="♂ Male", callback_data="gender_male"),
             InlineKeyboardButton(text="♀ Female", callback_data="gender_female")]
        ])

        await message.answer(
            "👋 Welcome to Pairly\n\n"
            "Here you can talk to strangers anonymously.\n"
            "You may encounter unfiltered content. Admins monitor chats.\n\n"
            "🌟 Premium gives:\n"
            "• Better matches\n"
            "• High-rated partners\n"
            "• Gender preference\n"
            "• Link sharing\n"
            "• Faster matching\n\n"
            "🌻 Earn Sunflowers by:\n"
            "• Good ratings\n"
            "• Maintaining streaks\n"
            "• Playing games\n\n"
            "By using /find or /next you agree to the rules.\n\n"
            "Please select your gender:",
            reply_markup=kb
        )
        await mark_started(user_id)
    else:
        await find_partner(message)

# =========================
# GENDER CALLBACK
# =========================

@dp.callback_query(F.data.startswith("gender_"))
async def gender_callback(cb: types.CallbackQuery):
    gender = cb.data.split("_")[1]
    await set_gender(cb.from_user.id, gender)
    await cb.message.edit_text(
        f"✅ Gender set to {gender.capitalize()}\n\n"
        "Use /find to start chatting."
    )
    await cb.answer()

# =========================
# MATCHMAKING CORE
# =========================

async def find_partner(message: types.Message):
    uid = message.from_user.id

    if uid in active_chats:
        await message.answer("❗ You are already in a chat.")
        return

    if uid in user_searching:
        await message.answer("🔄 Already searching for a partner...")
        return

    user_searching.add(uid)

    if search_queue:
        partner = search_queue.pop(0)

        if partner == uid:
            user_searching.discard(uid)
            await message.answer("⚠️ Please try again.")
            return

        active_chats[uid] = partner
        active_chats[partner] = uid

        user_searching.discard(uid)
        user_searching.discard(partner)

        await bot.send_message(uid, "✅ Connected to a stranger!")
        await bot.send_message(partner, "✅ Connected to a stranger!")

    else:
        search_queue.append(uid)
        await message.answer("🔍 Searching for a partner...")

# =========================
# /FIND & /NEXT
# =========================

@dp.message(Command("find"))
async def find_cmd(message: types.Message):
    await find_partner(message)

@dp.message(Command("next"))
async def next_cmd(message: types.Message):
    uid = message.from_user.id

    if uid in active_chats:
        partner = active_chats.pop(uid)
        active_chats.pop(partner, None)

        # 🔔 rating hook comes later
        await bot.send_message(uid, "🔁 Finding next partner...")
        await bot.send_message(partner, "❌ Partner left the chat.")

    await find_partner(message)

# =========================
# /STOP
# =========================

@dp.message(Command("stop"))
async def stop_cmd(message: types.Message):
    uid = message.from_user.id

    if uid in active_chats:
        partner = active_chats.pop(uid)
        active_chats.pop(partner, None)
        await bot.send_message(partner, "❌ Partner left the chat.")
        await message.answer("🛑 Chat ended.")
    elif uid in user_searching:
        user_searching.discard(uid)
        if uid in search_queue:
            search_queue.remove(uid)
        await message.answer("🛑 Search stopped.")
    else:
        await message.answer("ℹ️ You are not in a chat.")

# =========================
# MESSAGE RELAY
# =========================

@dp.message()
async def relay(message: types.Message):
    uid = message.from_user.id

    if uid in active_chats:
        partner = active_chats[uid]

        # 🔒 admin monitoring hook (later)
        await bot.send_message(partner, message.text)
    else:
        await message.answer("ℹ️ Use /find to start chatting.")

# =========================
# STARTUP
# =========================

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

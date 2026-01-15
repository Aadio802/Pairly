import asyncio
import time
import logging
import re
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

BOT_TOKEN = "YOUR_BOT_TOKEN"
ADMIN_IDS = {123456789}  # replace
DB_PATH = "pairly.db"

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────

async def db():
    conn = await aiosqlite.connect(DB_PATH)
    await conn.execute("PRAGMA journal_mode=WAL;")
    await conn.execute("PRAGMA foreign_keys=ON;")
    return conn


async def init_db():
    async with await db() as d:
        await d.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            gender TEXT,
            premium_until INTEGER DEFAULT 0,
            rating_sum INTEGER DEFAULT 0,
            rating_count INTEGER DEFAULT 0,
            banned_until INTEGER,
            created_at INTEGER
        );

        CREATE TABLE IF NOT EXISTS matchmaking (
            user_id INTEGER PRIMARY KEY,
            partner_id INTEGER,
            searching INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS ratings (
            rater INTEGER,
            rated INTEGER,
            stars INTEGER
        );
        """)
        await d.commit()

# ─────────────────────────────────────────────
# BOT SETUP
# ─────────────────────────────────────────────

bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

async def is_premium(user_id: int) -> bool:
    async with await db() as d:
        cur = await d.execute(
            "SELECT premium_until FROM users WHERE user_id=?",
            (user_id,)
        )
        row = await cur.fetchone()
        return bool(row and row[0] > time.time())


async def get_rating(user_id: int):
    async with await db() as d:
        cur = await d.execute(
            "SELECT rating_sum, rating_count FROM users WHERE user_id=?",
            (user_id,)
        )
        r = await cur.fetchone()
        if not r or r[1] < 5:
            return None
        return round(r[0] / r[1], 1), r[1]


def gender_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="♂ Male", callback_data="gender_male")],
        [InlineKeyboardButton(text="♀ Female", callback_data="gender_female")]
    ])


def rating_kb(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{i} ⭐", callback_data=f"rate_{i}_{user_id}")]
        for i in range(1, 6)
    ])

# ─────────────────────────────────────────────
# START / AGREEMENT
# ─────────────────────────────────────────────

@dp.message(Command("start"))
async def start(msg: types.Message):
    async with await db() as d:
        cur = await d.execute(
            "SELECT user_id FROM users WHERE user_id=?",
            (msg.from_user.id,)
        )
        if await cur.fetchone():
            await find(msg)
            return

        await d.execute(
            "INSERT INTO users (user_id, created_at) VALUES (?, ?)",
            (msg.from_user.id, int(time.time()))
        )
        await d.commit()

    await msg.answer(
        "👋 <b>Welcome to Pairly</b>\n\n"
        "• Anonymous chatting\n"
        "• Possible unfiltered content\n"
        "• Admin monitoring enabled\n"
        "• Premium gives better matches\n\n"
        "By using /find or /next you agree.\n\n"
        "Select your gender:",
        reply_markup=gender_kb()
    )


@dp.callback_query(F.data.startswith("gender_"))
async def set_gender(cb: types.CallbackQuery):
    gender = cb.data.split("_")[1]
    async with await db() as d:
        await d.execute(
            "UPDATE users SET gender=? WHERE user_id=?",
            (gender, cb.from_user.id)
        )
        await d.commit()
    await cb.message.edit_text("✅ Gender saved.\nUse /find to start chatting.")

# ─────────────────────────────────────────────
# MATCHMAKING
# ─────────────────────────────────────────────

@dp.message(Command("find"))
async def find(msg: types.Message):
    uid = msg.from_user.id
    async with await db() as d:
        cur = await d.execute(
            "SELECT partner_id, searching FROM matchmaking WHERE user_id=?",
            (uid,)
        )
        row = await cur.fetchone()
        if row and row[0]:
            await msg.answer("You are already in a chat.")
            return
        if row and row[1]:
            await msg.answer("Already searching for a partner…")
            return

        # find partner
        cur = await d.execute(
            "SELECT user_id FROM matchmaking WHERE searching=1 AND user_id!=?",
            (uid,)
        )
        partner = await cur.fetchone()

        if not partner:
            await d.execute(
                "INSERT OR REPLACE INTO matchmaking (user_id, searching) VALUES (?, 1)",
                (uid,)
            )
            await d.commit()
            await msg.answer("🔍 Searching for a partner…")
            return

        pid = partner[0]

        await d.execute(
            "UPDATE matchmaking SET partner_id=?, searching=0 WHERE user_id=?",
            (pid, uid)
        )
        await d.execute(
            "UPDATE matchmaking SET partner_id=?, searching=0 WHERE user_id=?",
            (uid, pid)
        )
        await d.commit()

    rating = await get_rating(pid)
    text = "🎉 Partner found!"
    if rating:
        text += f"\n⭐ {rating[0]} rated by {rating[1]} users"

    await msg.answer(text)
    await bot.send_message(pid, text)


@dp.message(Command("next"))
async def next_chat(msg: types.Message):
    await end_chat(msg.from_user.id, rate=True)
    await find(msg)


@dp.message(Command("stop"))
async def stop(msg: types.Message):
    await end_chat(msg.from_user.id, rate=True)
    await msg.answer("❌ Chat ended.")

# ─────────────────────────────────────────────
# MESSAGE RELAY + ADMIN MONITOR
# ─────────────────────────────────────────────

@dp.message(F.text)
async def relay(msg: types.Message):
    uid = msg.from_user.id

    if re.search(r"http|@", msg.text) and not await is_premium(uid):
        await msg.delete()
        await msg.answer("🚫 Links are blocked for normal users.")
        return

    async with await db() as d:
        cur = await d.execute(
            "SELECT partner_id FROM matchmaking WHERE user_id=?",
            (uid,)
        )
        row = await cur.fetchone()

    if not row or not row[0]:
        return

    pid = row[0]
    await bot.send_message(pid, msg.text)

    for admin in ADMIN_IDS:
        await bot.send_message(admin, f"👁 {uid} → {pid}: {msg.text}")

# ─────────────────────────────────────────────
# CHAT END + RATING
# ─────────────────────────────────────────────

async def end_chat(user_id: int, rate=False):
    async with await db() as d:
        cur = await d.execute(
            "SELECT partner_id FROM matchmaking WHERE user_id=?",
            (user_id,)
        )
        row = await cur.fetchone()
        if not row or not row[0]:
            return

        partner = row[0]

        await d.execute(
            "UPDATE matchmaking SET partner_id=NULL, searching=0 WHERE user_id IN (?, ?)",
            (user_id, partner)
        )
        await d.commit()

    if rate:
        await bot.send_message(
            user_id,
            "Please rate your last partner:",
            reply_markup=rating_kb(partner)
        )

# ─────────────────────────────────────────────
# RATING HANDLER
# ─────────────────────────────────────────────

@dp.callback_query(F.data.startswith("rate_"))
async def rate(cb: types.CallbackQuery):
    _, stars, rated = cb.data.split("_")
    stars = int(stars)
    rated = int(rated)

    async with await db() as d:
        await d.execute(
            "INSERT INTO ratings VALUES (?, ?, ?)",
            (cb.from_user.id, rated, stars)
        )
        await d.execute(
            "UPDATE users SET rating_sum = rating_sum + ?, rating_count = rating_count + 1 WHERE user_id=?",
            (stars, rated)
        )
        await d.commit()

    await cb.message.edit_text("⭐ Thanks for your rating!")

# ─────────────────────────────────────────────
# START BOT
# ─────────────────────────────────────────────

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

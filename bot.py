import os
import time
import asyncio
import re
import aiosqlite
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from config import BOT_TOKEN
from database import init_db

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

waiting = set()
pairs = {}
rating_targets = {}

#############################
# Helper functions
#############################

async def now_seconds():
    return int(time.time())

async def user_exists(uid):
    async with aiosqlite.connect("botdata.db") as db:
        await db.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (uid,))
        await db.commit()

async def get_user_info(uid):
    async with aiosqlite.connect("botdata.db") as db:
        async with db.execute("SELECT * FROM users WHERE user_id=?", (uid,)) as cur:
            return await cur.fetchone()

async def is_ghost_banned(uid):
    info = await get_user_info(uid)
    if not info:
        return False
    ban_until = info[6]  # ghost_ban_until
    if ban_until and ban_until > await now_seconds():
        return True
    return False

async def set_ghost_ban(uid, days=3):
    ban_until = await now_seconds() + (days * 24 * 3600)
    async with aiosqlite.connect("botdata.db") as db:
        await db.execute("UPDATE users SET ghost_ban_until=? WHERE user_id=?", (ban_until, uid))
        await db.commit()

async def add_rating(uid, score):
    async with aiosqlite.connect("botdata.db") as db:
        await db.execute("INSERT OR IGNORE INTO users(user_id) VALUES (?)", (uid,))
        await db.execute("""
            UPDATE users
            SET rating_sum = rating_sum + ?, rating_count = rating_count + 1
            WHERE user_id = ?
        """, (score, uid))
        await db.commit()

async def get_avg_rating(uid):
    async with aiosqlite.connect("botdata.db") as db:
        async with db.execute("SELECT rating_sum, rating_count FROM users WHERE user_id=?", (uid,)) as cur:
            row = await cur.fetchone()
    if not row or row[1] == 0:
        return 0
    return row[0] / row[1]

async def log_chat(uid, partner, mtype, content):
    async with aiosqlite.connect("botdata.db") as db:
        await db.execute("""
            INSERT INTO chats(user_id, partner_id, timestamp, message_type, content)
            VALUES (?, ?, ?, ?, ?)
        """, (uid, partner, await now_seconds(), mtype, content))
        await db.commit()

#############################
# Matching logic
#############################

async def try_match(uid):
    # Remove ghost banned
    if await is_ghost_banned(uid):
        return None

    # Attempt prioritized matching for premium
    user = await get_user_info(uid)
    preferred_gender = user[2] if user else None
    user_rating = await get_avg_rating(uid)

    candidate = None
    best_score = -1

    for other in list(waiting):
        if other == uid:
            continue

        other_info = await get_user_info(other)
        # Ghost banned skip
        if await is_ghost_banned(other):
            continue

        # Not recent partner if possible
        if user and other_info and other_info[7] == uid:
            continue

        other_rating = await get_avg_rating(other)
        match_gender_ok = True

        if preferred_gender:
            match_gender_ok = (other_info and other_info[1] == preferred_gender)

        if user[5] == 1:  # Premium
            score = other_rating if match_gender_ok else other_rating / 2
        else:
            score = 0

        if score > best_score:
            best_score = score
            candidate = other

    if candidate:
        waiting.remove(candidate)
        pairs[uid] = candidate
        pairs[candidate] = uid
        return candidate

    return None

#############################
# Commands
#############################

@dp.message(Command("start"))
async def start(message: types.Message):
    uid = message.from_user.id
    await user_exists(uid)
    await message.answer("Welcome! Use /find to search for a partner.")

@dp.message(Command("setgender"))
async def set_gender(message: types.Message):
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Usage: /setgender <male/female/other>")
        return
    uid = message.from_user.id
    gender = parts[1]
    async with aiosqlite.connect("botdata.db") as db:
        await db.execute("UPDATE users SET gender=? WHERE user_id=?", (gender, uid))
        await db.commit()
    await message.answer(f"Your gender has been set to {gender}.")

@dp.message(Command("setpref"))
async def set_pref(message: types.Message):
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Usage: /setpref <male/female/other>")
        return
    uid = message.from_user.id
    pref = parts[1]
    async with aiosqlite.connect("botdata.db") as db:
        await db.execute("UPDATE users SET preferred_gender=? WHERE user_id=?", (pref, uid))
        await db.commit()
    await message.answer(f"Preferred gender set to {pref}.")

@dp.message(Command("find"))
async def find(message: types.Message):
    uid = message.from_user.id
    await user_exists(uid)

    if await is_ghost_banned(uid):
        await message.answer("🚫 You are temporarily ghost blocked.")
        return

    if uid in pairs:
        await message.answer("You’re already in a chat.")
        return

    if uid in waiting:
        await message.answer("Already searching…")
        return

    found = await try_match(uid)
    if found:
        await bot.send_message(found, "🔗 Connected to a partner!")
        await message.answer("🔗 Connected!")
        return

    waiting.add(uid)
    await message.answer("🔍 Searching...")

@dp.message(Command("next"))
async def next_cmd(message: types.Message):
    uid = message.from_user.id
    if uid in pairs:
        p = pairs[uid]
        del pairs[p]
        del pairs[uid]
        await bot.send_message(p, "❌ Partner left chat.")
        waiting.add(p)

    if uid in waiting:
        await message.answer("Already searching...")
        return

    found = await try_match(uid)
    if found:
        await bot.send_message(found, "🔗 Connected to new partner!")
        await message.answer("🔗 Connected!")
        return

    waiting.add(uid)
    await message.answer("🔍 Searching...")

@dp.message(Command("stop"))
async def stop(message: types.Message):
    uid = message.from_user.id

    if uid in pairs:
        partner = pairs[uid]
        del pairs[partner]
        del pairs[uid]

        await bot.send_message(partner, "❌ Partner disconnected.")
        rating_targets[partner] = uid
        rating_targets[uid] = partner
        await bot.send_message(partner, "Rate partner: /rate 1–5")
        await message.answer("Rate partner: /rate 1–5")
        return

    if uid in waiting:
        waiting.remove(uid)
        await message.answer("Stopped searching.")
        return

    await message.answer("Not in chat.")

@dp.message(lambda m: m.text and m.text.startswith("/rate "))
async def rate_handler(message: types.Message):
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Usage: /rate <1–5>")
        return

    try:
        score = int(parts[1])
    except:
        await message.answer("Invalid rating.")
        return

    if score < 1 or score > 5:
        await message.answer("Rate must be 1–5.")
        return

    uid = message.from_user.id
    if uid not in rating_targets:
        await message.answer("Nothing to rate.")
        return

    target = rating_targets.pop(uid)
    await add_rating(target, score)
    avg = await get_avg_rating(target)
    await message.answer(f"Thanks for rating! ⭐ {avg:.2f} average.")

@dp.message(Command("myrating"))
async def myrating(message: types.Message):
    uid = message.from_user.id
    avg = await get_avg_rating(uid)
    await message.answer(f"Your rating: ⭐ {avg:.2f}")

@dp.message(Command("premium"))
async def premium(message: types.Message):
    uid = message.from_user.id
    async with aiosqlite.connect("botdata.db") as db:
        await db.execute("UPDATE users SET is_premium=1 WHERE user_id=?", (uid,))
        await db.commit()
    await message.answer("🎉 You are now a premium user!")

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    uid = message.from_user.id
    if uid != 123456789:
        await message.answer("Unauthorized.")
        return
    await message.answer("Admin: /ban /unban /stats /logs")

@dp.message(Command("ban"))
async def ban_user(message: types.Message):
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Usage: /ban <id>")
        return
    target = int(parts[1])
    async with aiosqlite.connect("botdata.db") as db:
        await db.execute("UPDATE users SET ghost_ban_until=? WHERE user_id=?", (await now_seconds() + 10*365*24*3600, target))
        await db.commit()
    await message.answer(f"Banned {target}")

@dp.message(Command("unban"))
async def unban(message: types.Message):
    parts = message.text.split()
    target = int(parts[1])
    async with aiosqlite.connect("botdata.db") as db:
        await db.execute("UPDATE users SET ghost_ban_until=0 WHERE user_id=?", (target,))
        await db.commit()
    await message.answer(f"Unbanned {target}")

@dp.message(Command("stats"))
async def stats(message: types.Message):
    async with aiosqlite.connect("botdata.db") as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            total = await cur.fetchone()
    await message.answer(f"Total users: {total[0]}")

@dp.message(Command("logs"))
async def logs(message: types.Message):
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Usage: /logs <user_id>")
        return
    target = int(parts[1])
    response = ""
    async with aiosqlite.connect("botdata.db") as db:
        async with db.execute("SELECT * FROM chats WHERE user_id=?", (target,)) as cur:
            rows = await cur.fetchall()
            for r in rows:
                response += f"{r[3]} | {r[4]} | {r[5]}\n"
    if not response: response="No logs."
    await message.answer(response)

@dp.message()
async def relay(message: types.Message):
    uid = message.from_user.id
    if uid in pairs:
        partner = pairs[uid]
        if message.text:
            if re.search(r"http[s]?://", message.text.lower()):
                info = await get_user_info(uid)
                if not info or info[5] == 0:
                    async with aiosqlite.connect("botdata.db") as db:
                        await db.execute("INSERT INTO reports(reporter,reported) VALUES(?,?)",(uid,uid))
                        await db.commit()
                    if await get_avg_rating(uid)<5: 
                        await set_ghost_ban(uid)
                        await message.answer("🚫 Ghost ban: too many links.")
                        return
            await log_chat(uid, partner, "text", message.text)
            await bot.send_message(partner, message.text)

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

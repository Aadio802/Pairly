import os
import asyncio
import time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from database import (
    init_db,
    ensure_user,
    set_gender,
    get_gender,
    save_cooldown,
    recently_matched,
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

# =========================
# START
# =========================
@dp.message(Command("start"))
async def start(message: types.Message):
    await ensure_user(message.from_user.id)
    await message.answer(
        "👋 Welcome to Pairly\n\n"
        "Here you can chat anonymously with strangers.\n"
        "You may encounter unfiltered content.\n\n"
        "🌟 Premium gives:\n"
        "• Better matches\n"
        "• High-rated partners\n"
        "• Gender preference\n"
        "• Faster matching\n\n"
        "🌻 Earn Sunflowers by:\n"
        "• Good ratings\n"
        "• Streaks\n"
        "• Games\n\n"
        "Set your gender:\n"
        "/male or /female\n\n"
        "Use /find to start chatting."
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

    # Already chatting
    if uid in chat_pairs:
        await message.answer("⚠️ You are already in a chat. Use /next or /stop.")
        return

    # Already searching
    if uid in searching:
        await message.answer("⏳ Already searching for a partner.")
        return

    gender = await get_gender(uid)
    if not gender:
        await message.answer("❗ Please set your gender first: /male or /female")
        return

    # Try to match
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
# STOP
# =========================
@dp.message(Command("stop"))
async def stop(message: types.Message):
    uid = message.from_user.id

    if uid in chat_pairs:
        partner = chat_pairs.pop(uid)
        chat_pairs.pop(partner, None)

        await save_cooldown(uid, partner)
        await save_cooldown(partner, uid)

        await bot.send_message(partner, "❌ Stranger has left the chat.")
        await message.answer("❌ Chat ended.")
        return

    if uid in searching:
        searching.discard(uid)
        if uid in queue:
            queue.remove(uid)
        await message.answer("❌ Stopped searching.")
        return

    await message.answer("⚠️ You are not in a chat.")

# =========================
# RELAY MESSAGES
# =========================
@dp.message()
async def relay(message: types.Message):
    uid = message.from_user.id

    if uid in chat_pairs:
        partner = chat_pairs[uid]
        await bot.send_message(partner, message.text)

# =========================
# MAIN
# =========================
async def main():
    await init_db()
    print("🤖 Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

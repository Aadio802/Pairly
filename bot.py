import asyncio
import time
import re
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.enums import ParseMode

from config import BOT_TOKEN, is_admin, DB_PATH
from database import Database

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
db = Database(DB_PATH)

# ===============================
# IN-MEMORY STATE
# ===============================
searching_users = set()      # users currently searching
active_chats = {}            # user_id -> partner_id
pending_rating = {}          # user_id -> last_partner_id

LINK_REGEX = re.compile(r"(http|@)", re.IGNORECASE)


# ===============================
# STARTUP
# ===============================
@dp.startup()
async def startup():
    await db.init()
    print("✅ Pairly bot started")


# ===============================
# HELPERS
# ===============================
async def end_chat(user_id: int, silent=False):
    partner = active_chats.pop(user_id, None)
    if partner:
        active_chats.pop(partner, None)
        await db.end_match(user_id)
        await db.end_match(partner)

        pending_rating[user_id] = partner
        pending_rating[partner] = user_id

        if not silent:
            await ask_rating(user_id)
            await ask_rating(partner)


async def ask_rating(user_id: int):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"{i} ⭐", callback_data=f"rate:{i}")
                for i in range(1, 6)
            ]
        ]
    )
    await bot.send_message(
        user_id,
        "⭐ <b>Please rate your last partner</b>",
        reply_markup=kb,
    )


async def send_to_partner(sender: int, text: str):
    partner = active_chats.get(sender)
    if partner:
        await bot.send_message(partner, text)


# ===============================
# /START
# ===============================
@dp.message(Command("start"))
async def start(message: Message):
    user = await db.get_user(message.from_user.id)
    if user:
        await find_partner(message)
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Male", callback_data="gender:male")],
            [InlineKeyboardButton(text="Female", callback_data="gender:female")],
        ]
    )

    await message.answer(
        "👋 <b>Welcome to Pairly</b>\n\n"
        "• Anonymous chatting\n"
        "• Chats may be unfiltered\n"
        "• Admins may monitor for safety\n"
        "• Premium gives priority & perks\n"
        "• Earn 🌻 Sunflowers via chats & games\n\n"
        "By using /find or /next you agree to the rules.\n\n"
        "<b>Select your gender:</b>",
        reply_markup=kb,
    )


@dp.callback_query(F.data.startswith("gender:"))
async def set_gender(cb: CallbackQuery):
    gender = cb.data.split(":")[1]
    await db.add_user(cb.from_user.id, gender)
    await cb.message.edit_text("✅ Gender saved. Finding a partner...")
    await find_partner(cb.message)


# ===============================
# MATCHMAKING
# ===============================
@dp.message(Command("find"))
async def find_partner(message: Message):
    uid = message.from_user.id

    ban = await db.is_banned(uid)
    if ban:
        reason, until = ban
        await message.answer(
            f"🚫 <b>You are banned</b>\nReason: {reason}\n"
            f"Until: <code>{time.ctime(until)}</code>"
        )
        return

    if uid in active_chats:
        await message.answer("❗ You are already in a chat.")
        return

    if uid in searching_users:
        await message.answer("⏳ Already searching for a partner...")
        return

    searching_users.add(uid)
    await message.answer("🔍 Searching for a partner...")

    await try_match()


async def try_match():
    if len(searching_users) < 2:
        return

    users = list(searching_users)
    u1 = users[0]
    u2 = users[1]

    searching_users.discard(u1)
    searching_users.discard(u2)

    active_chats[u1] = u2
    active_chats[u2] = u1

    await db.start_match(u1, u2)

    await bot.send_message(u1, "💬 <b>Partner found!</b>\nSay hi 👋")
    await bot.send_message(u2, "💬 <b>Partner found!</b>\nSay hi 👋")


# ===============================
# /NEXT & /STOP
# ===============================
@dp.message(Command("next"))
async def next_chat(message: Message):
    await end_chat(message.from_user.id)
    await find_partner(message)


@dp.message(Command("stop"))
async def stop_chat(message: Message):
    uid = message.from_user.id
    searching_users.discard(uid)
    await end_chat(uid)
    await message.answer("🛑 You left the chat.")


# ===============================
# MESSAGE RELAY + MODERATION
# ===============================
@dp.message()
async def relay(message: Message):
    uid = message.from_user.id

    if uid not in active_chats:
        return

    if LINK_REGEX.search(message.text or ""):
        if not await db.is_premium(uid):
            await message.answer("🚫 Links are not allowed for free users.")
            return

    await send_to_partner(uid, message.text)


# ===============================
# RATINGS
# ===============================
@dp.callback_query(F.data.startswith("rate:"))
async def rate(cb: CallbackQuery):
    rating = int(cb.data.split(":")[1])
    rater = cb.from_user.id

    target = pending_rating.pop(rater, None)
    if not target:
        await cb.answer("Rating expired", show_alert=True)
        return

    await db.add_rating(rater, target, rating)
    await cb.message.edit_text("✅ Thanks for your rating!")


# ===============================
# /HOW
# ===============================
@dp.message(Command("how"))
async def how(message: Message):
    await message.answer(
        "🌻 <b>Pairly Guide</b>\n\n"
        "• Anonymous chats\n"
        "• Rate partners after chats\n"
        "• Earn Sunflowers via streaks & games\n"
        "• Premium = priority + perks\n"
        "• Pets protect streaks\n"
        "• Games can be played inside chats\n"
    )


# ===============================
# ADMIN VIEW (SILENT)
# ===============================
@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("👁 Admin mode active (silent monitoring).")


# ===============================
# RUN
# ===============================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

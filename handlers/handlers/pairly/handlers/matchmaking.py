from aiogram import Router, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

from database import (
    create_user,
    get_user,
    set_searching,
    set_partner,
    get_partner,
    is_premium,
)

from handlers.ratings import ask_for_rating
from handlers.games import force_game_loss

router = Router()

# -------------------- MEMORY STATE --------------------
searching_users = set()
recent_pairs = {}  # user_id -> last_partner_id


# -------------------- KEYBOARDS --------------------

def gender_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="♂️ Male", callback_data="gender_male")],
            [InlineKeyboardButton(text="♀️ Female", callback_data="gender_female")],
        ]
    )


# -------------------- /start --------------------

@router.message(commands=["start"])
async def start_cmd(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)

    if user:
        # After first time, /start behaves like /find
        await find_partner(message)
        return

    await message.reply(
        "👋 <b>Welcome to Pairly</b>\n\n"
        "• Anonymous chatting with strangers\n"
        "• Content may be unfiltered\n"
        "• Chats are monitored by admins\n"
        "• Premium users get priority matching\n"
        "• Earn 🌻 Sunflowers via games & streaks\n\n"
        "By using /find or /next, you agree to the rules.\n\n"
        "Please select your gender:",
        reply_markup=gender_keyboard()
    )


@router.callback_query(F.data.startswith("gender_"))
async def set_gender(callback: CallbackQuery):
    gender = callback.data.split("_")[1]
    user_id = callback.from_user.id

    await create_user(user_id, gender)

    await callback.message.edit_text(
        "✅ Gender saved.\n\nUse /find to start chatting."
    )
    await callback.answer()


# -------------------- MATCHMAKING --------------------

@router.message(commands=["find"])
async def find_partner(message: Message):
    user_id = message.from_user.id

    partner_id = await get_partner(user_id)
    if partner_id:
        await message.reply("⚠️ You are already in a chat.")
        return

    if user_id in searching_users:
        await message.reply("⏳ Already searching for a partner...")
        return

    # Try to find partner
    for candidate in list(searching_users):
        if candidate == user_id:
            continue
        if recent_pairs.get(user_id) == candidate:
            continue

        # premium priority (simple)
        if await is_premium(candidate) or not await is_premium(user_id):
            await match_users(user_id, candidate, message)
            return

    # No partner found
    searching_users.add(user_id)
    await set_searching(user_id, True)
    await message.reply("🔍 Searching for a partner...")


async def match_users(u1: int, u2: int, message: Message):
    searching_users.discard(u1)
    searching_users.discard(u2)

    await set_searching(u1, False)
    await set_searching(u2, False)

    await set_partner(u1, u2)
    await set_partner(u2, u1)

    recent_pairs[u1] = u2
    recent_pairs[u2] = u1

    await message.bot.send_message(u1, "✅ Partner found! Start chatting 💬")
    await message.bot.send_message(u2, "✅ Partner found! Start chatting 💬")


# -------------------- /next --------------------

@router.message(commands=["next"])
async def next_partner(message: Message):
    user_id = message.from_user.id
    partner_id = await get_partner(user_id)

    if not partner_id:
        await find_partner(message)
        return

    # end active game
    await force_game_loss(user_id)

    # ask for rating
    await ask_for_rating(message.bot, user_id, partner_id)
    await ask_for_rating(message.bot, partner_id, user_id)

    # disconnect
    await set_partner(user_id, None)
    await set_partner(partner_id, None)

    await message.bot.send_message(partner_id, "🔁 Partner skipped the chat.")
    await message.reply("🔁 Finding a new partner...")

    await find_partner(message)


# -------------------- /stop --------------------

@router.message(commands=["stop"])
async def stop_chat(message: Message):
    user_id = message.from_user.id
    partner_id = await get_partner(user_id)

    if partner_id:
        await force_game_loss(user_id)

        await ask_for_rating(message.bot, user_id, partner_id)
        await ask_for_rating(message.bot, partner_id, user_id)

        await set_partner(partner_id, None)
        await message.bot.send_message(partner_id, "❌ Partner left the chat.")

    searching_users.discard(user_id)
    await set_partner(user_id, None)
    await set_searching(user_id, False)

    await message.reply("🛑 You have left the chat.")

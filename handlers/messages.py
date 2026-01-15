from aiogram import Router, F
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

from database import (
    get_partner,
    is_premium,
    check_ban,
)

from config import ADMIN_IDS

router = Router()

# Simple in-memory daily link counter (reset on restart)
premium_link_usage = {}  # user_id -> count
DAILY_LINK_LIMIT = 3


def contains_blocked_link(text: str) -> bool:
    text = text.lower()
    return "http://" in text or "https://" in text or "@" in text


@router.message()
async def relay_message(message: Message):
    user_id = message.from_user.id

    # Ignore service messages
    if not message.from_user or not message.text and not message.caption and not message.photo and not message.video:
        return

    partner_id = await get_partner(user_id)
    if not partner_id:
        return  # not in chat

    # -------------------- LINK MODERATION --------------------
    text_content = message.text or message.caption or ""
    if contains_blocked_link(text_content):
        if not await is_premium(user_id):
            await message.reply("🚫 Links are not allowed for free users.")
            return
        else:
            used = premium_link_usage.get(user_id, 0)
            if used >= DAILY_LINK_LIMIT:
                await message.reply("⚠️ Daily link limit reached for premium users.")
                return
            premium_link_usage[user_id] = used + 1

    # -------------------- RELAY MESSAGE --------------------
    try:
        if message.text:
            await message.bot.send_message(
                partner_id,
                message.text
            )
        elif message.photo:
            await message.bot.send_photo(
                partner_id,
                photo=message.photo[-1].file_id,
                caption=message.caption
            )
        elif message.video:
            await message.bot.send_video(
                partner_id,
                video=message.video.file_id,
                caption=message.caption
            )
        elif message.voice:
            await message.bot.send_voice(
                partner_id,
                voice=message.voice.file_id
            )
        elif message.sticker:
            await message.bot.send_sticker(
                partner_id,
                sticker=message.sticker.file_id
            )
    except TelegramBadRequest:
        await message.reply("⚠️ Partner is unavailable. Chat ended.")

    # -------------------- ADMIN MONITORING --------------------
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"👁️ Chat Monitor\n"
                f"From: {user_id}\n"
                f"To: {partner_id}\n"
                f"Content: {text_content[:500]}"
            )
        except Exception:
            pass

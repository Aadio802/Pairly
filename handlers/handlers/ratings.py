from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from database import add_rating

router = Router()

# In-memory mapping: who needs to rate whom
# rater_id -> rated_id
pending_ratings = {}


def rating_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⭐ 1", callback_data="rate_1"),
                InlineKeyboardButton(text="⭐ 2", callback_data="rate_2"),
                InlineKeyboardButton(text="⭐ 3", callback_data="rate_3"),
                InlineKeyboardButton(text="⭐ 4", callback_data="rate_4"),
                InlineKeyboardButton(text="⭐ 5", callback_data="rate_5"),
            ]
        ]
    )


async def ask_for_rating(bot, rater_id: int, rated_id: int):
    """
    Call this function when a chat ends.
    """
    pending_ratings[rater_id] = rated_id
    await bot.send_message(
        rater_id,
        "Please rate your last partner:",
        reply_markup=rating_keyboard(),
    )


@router.callback_query(F.data.startswith("rate_"))
async def handle_rating(callback: CallbackQuery):
    rater_id = callback.from_user.id

    if rater_id not in pending_ratings:
        await callback.answer("Rating expired or already submitted.", show_alert=True)
        return

    rated_id = pending_ratings.pop(rater_id)
    stars = int(callback.data.split("_")[1])

    await add_rating(
        rater_id=rater_id,
        rated_id=rated_id,
        stars=stars,
    )

    await callback.message.edit_text("✅ Thanks for your rating!")
    await callback.answer()

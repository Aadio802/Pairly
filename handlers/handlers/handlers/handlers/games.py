from aiogram import Router
from aiogram.types import Message
import random

from database import (
    get_partner,
    add_sunflowers,
)

router = Router()

# -------------------- GAME STATE --------------------
# chat_key = tuple(sorted(user1, user2))
active_games = {}  # chat_key -> game_data


def get_chat_key(u1: int, u2: int):
    return tuple(sorted((u1, u2)))


# -------------------- GAME COMMAND ENTRY --------------------

@router.message(commands=["game"])
async def start_game(message: Message):
    user_id = message.from_user.id
    partner_id = await get_partner(user_id)

    if not partner_id:
        await message.reply("❌ You must be in a chat to play games.")
        return

    chat_key = get_chat_key(user_id, partner_id)
    if chat_key in active_games:
        await message.reply("🎮 A game is already active in this chat.")
        return

    await message.reply(
        "🎮 <b>Choose a game</b>\n\n"
        "/ttt <bet> — Tic Tac Toe\n"
        "/word_easy <bet>\n"
        "/word_hard <bet>\n"
        "/hangman <bet>"
    )


# -------------------- TIC TAC TOE --------------------

@router.message(commands=["ttt"])
async def tic_tac_toe(message: Message):
    await start_simple_game(message, "ttt")


# -------------------- WORD CHAIN --------------------

@router.message(commands=["word_easy"])
async def word_easy(message: Message):
    await start_simple_game(message, "word_easy")


@router.message(commands=["word_hard"])
async def word_hard(message: Message):
    await start_simple_game(message, "word_hard")


# -------------------- HANGMAN --------------------

@router.message(commands=["hangman"])
async def hangman(message: Message):
    await start_simple_game(message, "hangman")


# -------------------- GAME CORE --------------------

async def start_simple_game(message: Message, game_type: str):
    user_id = message.from_user.id
    partner_id = await get_partner(user_id)

    if not partner_id:
        return

    try:
        bet = int(message.text.split()[1])
        if bet <= 0:
            raise ValueError
    except Exception:
        await message.reply("❌ Usage: /game_name <bet>")
        return

    chat_key = get_chat_key(user_id, partner_id)
    if chat_key in active_games:
        await message.reply("🎮 Game already running.")
        return

    active_games[chat_key] = {
        "game": game_type,
        "players": [user_id, partner_id],
        "bet": bet,
    }

    await message.bot.send_message(
        user_id,
        f"🎮 {game_type} started!\nBet: 🌻 {bet}\nWinner will be decided shortly."
    )
    await message.bot.send_message(
        partner_id,
        f"🎮 {game_type} started!\nBet: 🌻 {bet}\nWinner will be decided shortly."
    )

    # simulate game result
    await resolve_game(chat_key)


async def resolve_game(chat_key):
    game = active_games.pop(chat_key, None)
    if not game:
        return

    p1, p2 = game["players"]
    bet = game["bet"]

    winner = random.choice([p1, p2])
    loser = p2 if winner == p1 else p1

    # rewards
    await add_sunflowers(winner, bet, source="game")
    await add_sunflowers(loser, -bet, source="game")

    from aiogram import Bot
    bot = Bot.get_current()

    await bot.send_message(
        winner,
        f"🏆 You won the game!\n🌻 +{bet}"
    )
    await bot.send_message(
        loser,
        f"❌ You lost the game.\n🌻 -{bet}"
    )


# -------------------- FORCE LOSS ON LEAVE --------------------

async def force_game_loss(user_id: int):
    """
    Call this when /next or /stop is used
    """
    for chat_key, game in list(active_games.items()):
        if user_id in game["players"]:
            winner = game["players"][0] if game["players"][1] == user_id else game["players"][1]
            bet = game["bet"]

            await add_sunflowers(winner, bet, source="game")
            await add_sunflowers(user_id, -bet, source="game")

            from aiogram import Bot
            bot = Bot.get_current()

            await bot.send_message(winner, "🏆 Opponent left. You win!")
            await bot.send_message(user_id, "❌ You left the game. You lose.")

            del active_games[chat_key]
            return

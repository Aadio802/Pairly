import random
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    Message,
)
from aiogram import Bot
from database import Database

# ===============================
# GAME CONSTANTS
# ===============================
GAMES = ("tictactoe", "word_easy", "word_hard", "hangman")

WORD_EASY = ["cat", "dog", "sun", "tree", "book"]
WORD_HARD = ["quantum", "biology", "telegram", "anonymous"]
HANGMAN_WORDS = ["python", "railway", "premium", "sunflower"]


class GameManager:
    def __init__(self, bot: Bot, db: Database, active_chats: dict):
        self.bot = bot
        self.db = db
        self.active_chats = active_chats

    # ===============================
    # GAME ENTRY
    # ===============================
    async def start_game(self, user_id: int, game: str, bet: int = 0):
        partner = self.active_chats.get(user_id)
        if not partner:
            return

        await self.db.add_sunflowers(user_id, -bet, "game")
        await self.db.add_sunflowers(partner, -bet, "game")

        state = self._initial_state(game)

        await self.db.save_game(
            chat_id=user_id,
            game_type=game,
            state=state,
            bet=bet,
        )

        await self.bot.send_message(
            user_id, f"🎮 Game started: <b>{game}</b>"
        )
        await self.bot.send_message(
            partner, f"🎮 Game started: <b>{game}</b>"
        )

        if game == "tictactoe":
            await self._send_ttt_board(user_id)
            await self._send_ttt_board(partner)

    # ===============================
    # TIC TAC TOE
    # ===============================
    async def _send_ttt_board(self, user_id: int):
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬜", callback_data=f"ttt:{i}"
                    )
                    for i in range(r, r + 3)
                ]
                for r in range(0, 9, 3)
            ]
        )
        await self.bot.send_message(user_id, "❌⭕ Tic Tac Toe", reply_markup=kb)

    # ===============================
    # WORD CHAIN
    # ===============================
    async def start_word_chain(self, user_id: int, hard=False):
        word = random.choice(WORD_HARD if hard else WORD_EASY)
        await self.bot.send_message(
            user_id,
            f"🔤 Word Chain started!\nFirst word: <b>{word}</b>",
        )

    # ===============================
    # HANGMAN
    # ===============================
    async def start_hangman(self, user_id: int):
        word = random.choice(HANGMAN_WORDS)
        masked = "_" * len(word)
        await self.bot.send_message(
            user_id,
            f"🪢 Hangman\nWord: <code>{masked}</code>",
        )

    # ===============================
    # GAME END
    # ===============================
    async def end_game(self, winner: int, loser: int, bet: int):
        if bet > 0:
            await self.db.add_sunflowers(winner, bet * 2, "game")

        await self.bot.send_message(winner, "🏆 You won the game!")
        await self.bot.send_message(loser, "💀 You lost the game!")

        await self.db.delete_game(winner)

    # ===============================
    # AUTO LOSS
    # ===============================
    async def auto_lose(self, quitter: int):
        game = await self.db.get_game(quitter)
        if not game:
            return

        _, _, _, bet, _ = game
        partner = self.active_chats.get(quitter)

        if partner:
            await self.end_game(partner, quitter, bet)

    # ===============================
    # STATE
    # ===============================
    def _initial_state(self, game: str) -> str:
        if game == "tictactoe":
            return "---------"
        return ""

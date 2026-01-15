import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database import init_db

from handlers.matchmaking import router as matchmaking_router
from handlers.messages import router as messages_router
from handlers.ratings import router as ratings_router
from handlers.premium import router as premium_router
from handlers.games import router as games_router

from middlewares.ban_check import BanCheckMiddleware
from middlewares.spam_guard import SpamGuardMiddleware


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    print("✅ Pairly bot booting...")

    # Initialize database
    await init_db()

    bot = Bot(
        token=BOT_TOKEN,
        parse_mode=ParseMode.HTML
    )

    dp = Dispatcher()

    # Middlewares
    dp.message.middleware(BanCheckMiddleware())
    dp.message.middleware(SpamGuardMiddleware())

    # Routers
    dp.include_router(matchmaking_router)
    dp.include_router(messages_router)
    dp.include_router(ratings_router)
    dp.include_router(premium_router)
    dp.include_router(games_router)

    print("🚀 Pairly bot started successfully")

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("❌ Pairly bot stopped")

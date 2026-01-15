from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)

import config
import database


# ---------- COMMANDS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    database.add_user(user.id, user.username)
    await update.message.reply_text(
        "👋 Welcome!\n\n"
        "Earn 🌻 Sunflowers, adopt 🐾 pets, maintain 🔥 streaks, and more!\n\n"
        "Use /daily to start."
    )


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    success, reward = database.claim_daily(user_id)

    if not success:
        await update.message.reply_text("❌ You already claimed today!")
    else:
        await update.message.reply_text(
            f"🔥 Daily claimed!\n"
            f"You earned 🌻 {reward} sunflowers."
        )


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = database.get_user(update.effective_user.id)
    await update.message.reply_text(
        f"🌻 Sunflowers: {user[2]}\n"
        f"🔥 Streak: {user[4]}"
    )


async def adopt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /adopt <pet_name>")
        return

    pet_name = " ".join(context.args)
    database.adopt_pet(update.effective_user.id, pet_name)
    await update.message.reply_text(f"🐾 You adopted **{pet_name}**!")


async def pet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pet = database.get_pet(update.effective_user.id)
    if not pet:
        await update.message.reply_text("❌ You don't have a pet yet.")
    else:
        await update.message.reply_text(
            f"🐾 Pet: {pet[0]}\n"
            f"⭐ Level: {pet[1]}"
        )


async def game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import random
    win = random.choice([True, False])
    database.record_game(update.effective_user.id, win)

    if win:
        database.add_sunflowers(update.effective_user.id, 20)
        await update.message.reply_text("🎮 You WON! +20 🌻")
    else:
        await update.message.reply_text("🎮 You lost 😢 Try again!")


# ---------- MAIN ----------
def main():
    database.setup_database()

    app = ApplicationBuilder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("adopt", adopt))
    app.add_handler(CommandHandler("pet", pet))
    app.add_handler(CommandHandler("game", game))

    print("🤖 Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()

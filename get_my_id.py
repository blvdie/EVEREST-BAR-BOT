# get_my_id.py
import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

BOT_TOKEN = "8470106768:AAFtDu1bfpsY7DJnnZq8wT43v7nkgLhv0t4"

async def show_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = (
        f"Профиль:\n"
        f"ID: <code>{user.id}</code>\n"
        f"Имя: {user.first_name}\n"
        f"Username: @{user.username if user.username else 'не задан'}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, show_id))
    print("Отправьте любое сообщение боту, чтобы узнать свой ID.")
    app.run_polling()

if __name__ == "__main__":

    main()

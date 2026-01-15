import logging
import sqlite3
import os
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = "8470106768:AAFtDu1bfpsY7DJnnZq8wT43v7nkgLhv0t4"
DB_PATH = "menu.db"

# Твой Telegram ID
ADMIN_IDS = {
    946820627,  # я
    825303517,  # саша
    6885937626, # второй бармен
}

logging.basicConfig(level=logging.INFO)

def is_admin(user):
    return user.id in ADMIN_IDS

# === Функция сохранения пользователей ===
async def save_user(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    if 'active_users' not in context.bot_data:
        context.bot_data['active_users'] = set()
    context.bot_data['active_users'].add(user_id)

# === Работа с базой данных ===
def get_categories():
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT category FROM items ORDER BY category")
    cats = [r[0] for r in cur.fetchall()]
    conn.close()
    return cats

def get_items_by_category(category):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name, is_stopped FROM items WHERE category = ? ORDER BY name", (category,))
    items = cur.fetchall()
    conn.close()
    return items

def set_item_stopped(name, stopped: bool):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE items SET is_stopped = ? WHERE name = ?", (int(stopped), name))
    conn.commit()
    conn.close()

# === Клавиатуры ===
def main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Меню"), KeyboardButton("Стоп лист")]
    ], resize_keyboard=True)

def admin_category_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Управление")],
        [KeyboardButton("Назад")]
    ], resize_keyboard=True)

def non_admin_category_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Стоп лист")],
        [KeyboardButton("Назад")]
    ], resize_keyboard=True)

def action_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Вернуть в наличие")],
        [KeyboardButton("Стоп-лист")],
        [KeyboardButton("Назад к категориям")]
    ], resize_keyboard=True)

# === НОВАЯ ФУНКЦИЯ: Показ реального стоп-листа ===
async def show_stoplist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_user(context, update.effective_user.id)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT category, name FROM items WHERE is_stopped = 1 ORDER BY category, name")
    stopped_items = cur.fetchall()
    conn.close()

    if not stopped_items:
        await update.message.reply_text("✅ Стоп-лист пуст.")
        await update.message.reply_text("Выберите действие:", reply_markup=main_keyboard())
        return

    # Группируем по категориям
    categories = {}
    for cat, name in stopped_items:
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(name)

    # Формируем сообщение
    lines = []
    for cat in sorted(categories.keys()):
        lines.append(f"---{cat}---")
        for name in categories[cat]:
            lines.append(name)
        lines.append("")  # пустая строка между категориями

    response = "\n".join(lines).strip()

    await update.message.reply_text(response)
    await update.message.reply_text("Выберите действие:", reply_markup=main_keyboard())

# === Обработчики ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_user(context, update.effective_user.id)
    text = 'Привет! Это бот для помощи официантам “Эверест” по барному меню'
    await update.message.reply_text(text, reply_markup=main_keyboard())

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_user(context, update.effective_user.id)
    categories = get_categories()
    if not categories:
        await update.message.reply_text("❌ Меню пусто.")
        return

    buttons = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in categories]
    await update.message.reply_text(
        "Выберите категорию из бар-меню:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    await update.message.reply_text("Выберите действие:", reply_markup=main_keyboard())

async def stoplist_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_user(context, update.effective_user.id)
    await show_stoplist(update, context)

async def back_to_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_user(context, update.effective_user.id)
    categories = get_categories()
    buttons = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in categories]
    await update.message.reply_text(
        "Выберите категорию из бар-меню:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    await update.message.reply_text("Выберите действие:", reply_markup=main_keyboard())

# === Уведомления ВСЕМ не-админам ===
async def notify_all_non_admins(context: ContextTypes.DEFAULT_TYPE, item_name: str, action: str):
    if 'active_users' not in context.bot_data:
        return

    message = f"‼️{item_name} {action}."

    for user_id in list(context.bot_data['active_users']):
        try:
            user = await context.bot.get_chat(user_id)
            if not is_admin(user):
                await context.bot.send_message(chat_id=user_id, text=message)
        except Exception:
            context.bot_data['active_users'].discard(user_id)

# === Отображение категории ===
async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_user(context, update.effective_user.id)
    query = update.callback_query
    await query.answer()
    category = query.data.replace("cat_", "")
    context.chat_data['current_category'] = category

    items = get_items_by_category(category)
    items_list = "\n".join(
        f"• {'❌<b>' + name + '</b>❌' if stopped else name}"
        for _, name, stopped in items
    )
    response = f"🍸 <b>{category}</b>\n\n{items_list}"

    await query.message.reply_text(response, parse_mode="HTML")

    if is_admin(update.effective_user):
        await query.message.reply_text("Выберите действие:", reply_markup=admin_category_keyboard())
    else:
        await query.message.reply_text("Выберите действие:", reply_markup=non_admin_category_keyboard())

# === Админка ===
async def manage_availability_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_user(context, update.effective_user.id)
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Доступ запрещён.")
        return

    category = context.chat_data.get('current_category')
    if not category:
        await update.message.reply_text("❌ Не выбрана категория.")
        return

    items = get_items_by_category(category)
    if not items:
        await update.message.reply_text("❌ В категории нет позиций.")
        return

    buttons = [[InlineKeyboardButton(
        ("❌ " if stopped else "") + name,
        callback_data=f"item_{item_id}"
    )] for item_id, name, stopped in items]

    await update.message.reply_text(
        "Выберите позицию и действие:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def item_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_user(context, update.effective_user.id)
    query = update.callback_query
    await query.answer()
    
    try:
        item_id = int(query.data.replace("item_", ""))
    except ValueError:
        await query.message.reply_text("❌ Неверный формат данных.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM items WHERE id = ?", (item_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        await query.message.reply_text("❌ Позиция не найдена.")
        return

    item_name = row[0]
    context.user_data['selected_item'] = item_name

    await query.message.reply_text("Выберите действие:", reply_markup=action_keyboard())

async def action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_user(context, update.effective_user.id)
    if not is_admin(update.effective_user):
        await update.message.reply_text("❌ Доступ запрещён.")
        return

    action = update.message.text
    item_name = context.user_data.get('selected_item')
    category = context.chat_data.get('current_category')

    if action == "Назад к категориям":
        await back_to_categories(update, context)
        return

    if not item_name or not category:
        await update.message.reply_text("❌ Ошибка: не выбрана позиция.")
        return

    if action == "Стоп-лист":
        set_item_stopped(item_name, True)
        await update.message.reply_text(f"✅ '{item_name}' добавлен в стоп-лист.")
        await notify_all_non_admins(context, item_name, "добавлен в стоп")
    elif action == "Вернуть в наличие":
        set_item_stopped(item_name, False)
        await update.message.reply_text(f"✅ '{item_name}' возвращён в меню.")
        await notify_all_non_admins(context, item_name, "возвращён в меню")
    else:
        await update.message.reply_text("❓ Неизвестное действие.")
        return

    await update.message.reply_text("Выберите действие:", reply_markup=admin_category_keyboard())

# === Обработка "Назад" для не-админов ===
async def back_from_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_user(context, update.effective_user.id)
    await back_to_categories(update, context)

# === Запуск ===
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^Меню$"), menu_handler))
    app.add_handler(MessageHandler(filters.Regex("^Стоп лист$"), stoplist_handler))
    app.add_handler(MessageHandler(filters.Regex("^Назад$"), back_from_category))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^Управление"), manage_availability_start))
    app.add_handler(MessageHandler(filters.Regex("^(Вернуть в наличие|Стоп-лист|Назад к категориям)$"), action_handler))
    app.add_handler(CallbackQueryHandler(category_callback, pattern=r"^cat_"))
    app.add_handler(CallbackQueryHandler(item_selected, pattern=r"^item_"))

    print("✅ Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
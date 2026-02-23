import os
import logging
import time
from collections import defaultdict
from anthropic import Anthropic
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

client = Anthropic(api_key=ANTHROPIC_API_KEY)

user_history: dict[int, list] = defaultdict(list)
user_mode: dict[int, str] = {}
user_topic: dict[int, str] = {}
rate_limit: dict[int, list] = defaultdict(list)

RATE_LIMIT_MAX = 20
RATE_LIMIT_WINDOW = 3600

SYSTEM_PROMPT = """Ты ArtMuse - страстный, эрудированный ИИ-гид по истории искусства.
Говоришь только по-русски. Теплый и увлеченный, как любимый профессор.

ПРАВИЛА ФОРМАТИРОВАНИЯ (строго обязательно):
- Никаких символов # для заголовков - они отображаются как решетки в Telegram
- Никаких markdown-заголовков вообще
- Ключевые заголовки разделов всегда *жирным*
- Названия картин всегда в кавычках: "Звездная ночь"
- Имена художников всегда жирным: *Ван Гог*
- При первом упоминании художника - сразу после имени годы жизни в скобках: *Ван Гог* (1853-1890)
- Структуру делай через эмодзи и переносы строк, не через заголовки
- Используй эмодзи умеренно
- Telegram Markdown: *жирный*, _курсив_

РЕЖИМЫ:

[explore] - пользователь ввел год:
*Эпоха:* одним ярким предложением
*Художники эпохи:* Топ-5 - имя *жирным* с годами жизни, 1-2 предложения о стиле
*Шедевры:* Топ-3 с историей создания
*Интересный факт:* один поразительный факт

[quiz] - режим викторины:
- Задавай РОВНО ОДИН вопрос за раз
- После ответа: правильно или нет + объяснение
- Показывай *Счет: X/Y*
- После 5 вопросов - *Итог* с похвалой

[artist] - пользователь назвал художника:
*О мастере:* эпоха, страна, движение
*Главные работы:* 3-5 работ с историями
*Интересный факт:* смешной или трогательный анекдот

[painting] - режим угадай картину:
- Опиши известную картину словами: цвета, композиция, сюжет, настроение, эпоха - но НЕ называй картину и НЕ называй художника
- Жди ответа пользователя
- Если угадала: *Верно!* + расскажи историю картины: художник с годами жизни, год создания, где хранится
- Если не угадала: дай подсказку и жди снова
- После 3 подсказок - назови картину и расскажи о ней
- Веди счет угаданных картин *Угадано: X*
- Выбирай картины разного уровня сложности

[free] - свободный разговор об искусстве.
"""

def is_rate_limited(user_id: int) -> bool:
    now = time.time()
    timestamps = rate_limit[user_id]
    rate_limit[user_id] = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
    if len(rate_limit[user_id]) >= RATE_LIMIT_MAX:
        return True
    rate_limit[user_id].append(now)
    return False

def get_mode_system(mode: str) -> str:
    return SYSTEM_PROMPT + f"\n\nТЕКУЩИЙ РЕЖИМ: [{mode}]"

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗺 Эпоха", callback_data="mode_explore"),
            InlineKeyboardButton("🎨 О мастере", callback_data="mode_artist"),
        ],
        [
            InlineKeyboardButton("🎓 Викторина", callback_data="mode_quiz"),
            InlineKeyboardButton("🖼 Картина", callback_data="mode_painting"),
        ],
        [
            InlineKeyboardButton("💬 Чат", callback_data="mode_free"),
        ]
    ])

def after_any_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗺 Эпоха", callback_data="mode_explore"),
            InlineKeyboardButton("🎨 О мастере", callback_data="mode_artist"),
        ],
        [
            InlineKeyboardButton("🎓 Викторина", callback_data="mode_quiz"),
            InlineKeyboardButton("🖼 Картина", callback_data="mode_painting"),
        ],
        [
            InlineKeyboardButton("🏠 Меню", callback_data="main_menu"),
        ]
    ])

async def call_claude(user_id: int, user_message: str, mode: str) -> str:
    history = user_history[user_id]
    history.append({"role": "user", "content": user_message})

    if len(history) > 10:
        history = history[-10:]
        user_history[user_id] = history

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1200,
            system=get_mode_system(mode),
            messages=history,
        )
        reply = response.content[0].text
        history.append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return "Что-то пошло не так. Попробуй ещё раз через минуту."

def detect_mode(text: str, current_mode: str) -> str:
    import re
    if re.match(r"^\s*\d{3,4}\s*$", text.strip()):
        return "explore"
    return current_mode or "free"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_mode[user_id] = "free"
    user_history[user_id] = []

    text = (
        "👑 *Привет, принцесса!*\n\n"
        "Я ArtMuse — твой личный гид по истории искусства.\n\n"
        "🗺 *Эпоха* — введи год, расскажу об эпохе, художниках и шедеврах\n"
        "🎨 *О мастере* — всё о любом художнике: жизнь, работы, анекдоты\n"
        "🎓 *Викторина* — проверю знания с разбором ошибок\n"
        "🖼 *Картина* — угадай картину по описанию\n"
        "💬 *Чат* — просто поговорим об искусстве\n\n"
        "_Попробуй написать год — например, 1888 или 1503_"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard())

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выбери режим:", reply_markup=main_menu_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if is_rate_limited(user_id):
        await update.message.reply_text(
            "Слишком много сообщений. Подожди немного и попробуй снова."
        )
        return

    mode = user_mode.get(user_id, "free")
    mode = detect_mode(text, mode)
    user_mode[user_id] = mode

    if mode in ("explore", "artist"):
        user_topic[user_id] = text

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    reply = await call_claude(user_id, text, mode)

    await update.message.reply_text(
        reply,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=after_any_keyboard()
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "main_menu":
        await query.message.reply_text("Выбери режим:", reply_markup=main_menu_keyboard())

    elif data.startswith("mode_"):
        mode = data.replace("mode_", "")
        user_mode[user_id] = mode
        user_history[user_id] = []

        prompts = {
            "explore": "🗺 *Эпоха*\n\nВведи любой год — например, *1620* или *1888*.",
            "artist": "🎨 *О мастере*\n\nНазови любого художника — *Рембрандт*, *Климт*, *Малевич*.",
            "quiz": "🎓 *Викторина*\n\nО чём проверяем знания? Напиши эпоху или имя художника — например, _импрессионизм_ или _Дали_.",
            "painting": "🖼 *Картина*\n\nЯ опишу картину, а ты угадаешь!\nНапиши _начинаем_ — и поехали!",
            "free": "💬 *Чат*\n\nСпрашивай всё что угодно об искусстве!",
        }
        await query.message.reply_text(
            prompts[mode],
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=after_any_keyboard()
        )

def main():
    if not TELEGRAM_TOKEN or not ANTHROPIC_API_KEY:
        raise ValueError("Укажи TELEGRAM_TOKEN и ANTHROPIC_API_KEY в переменных окружения!")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("ArtMuse запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

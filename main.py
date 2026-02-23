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

# In-memory state per user
user_history: dict[int, list] = defaultdict(list)
user_mode: dict[int, str] = {}          # explore | quiz | artist | free
user_topic: dict[int, str] = {}         # last explored year/artist
user_quiz_score: dict[int, tuple] = {}  # (correct, total)
rate_limit: dict[int, list] = defaultdict(list)

RATE_LIMIT_MAX = 20
RATE_LIMIT_WINDOW = 3600  # 1 hour

SYSTEM_PROMPT = """Ты ArtMuse — страстный, эрудированный ИИ-гид по истории искусства.
Говоришь только по-русски. Тёплый и увлечённый, как любимый профессор.

ПРАВИЛА ФОРМАТИРОВАНИЯ (строго обязательно):
- Никаких символов # для заголовков — они отображаются как решётки в Telegram
- Никаких markdown-заголовков вообще
- Ключевые заголовки и названия разделов всегда *жирным*
- Названия картин всегда в кавычках: «Звёздная ночь»
- Имена художников всегда жирным: *Ван Гог*
- При первом упоминании художника — сразу после имени годы жизни в скобках: *Ван Гог* (1853-1890)
- Структуру делай через эмодзи и переносы строк, не через заголовки
- Используй эмодзи умеренно
- Telegram Markdown: *жирный*, _курсив_

РЕЖИМЫ:

[explore] — пользователь ввёл год:
*Эпоха:* одним ярким предложением
*Художники эпохи:* Топ-5 — имя *жирным* с годами жизни, 1-2 предложения о стиле
*Шедевры:* Топ-3 с историей создания
*Интересный факт:* один поразительный факт
Предложи викторину или узнать подробнее о художнике

[quiz] — режим викторины:
- Задавай РОВНО ОДИН вопрос за раз
- После ответа: правильно или нет + объяснение
- Показывай *Счёт: X/Y*
- После 5 вопросов — *Итог* с похвалой

[artist] — пользователь назвал художника:
*О мастере:* эпоха, страна, движение
*Главные работы:* 3-5 работ с историями
*Интересный факт:* смешной или трогательный анекдот
Предложи викторину

[free] — свободный разговор об искусстве.
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
            InlineKeyboardButton("💬 Чат", callback_data="mode_free"),
        ]
    ])

def after_explore_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎓 Викторина по эпохе", callback_data="start_quiz"),
            InlineKeyboardButton("🎨 Подробнее о художнике", callback_data="mode_artist"),
        ],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ])

def after_quiz_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Ещё викторина", callback_data="start_quiz"),
            InlineKeyboardButton("🗺 Новый период", callback_data="mode_explore"),
        ],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ])

async def call_claude(user_id: int, user_message: str, mode: str) -> str:
    history = user_history[user_id]
    history.append({"role": "user", "content": user_message})
    
    # Keep last 10 messages
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
        return "😔 Что-то пошло не так при обращении к ИИ. Попробуй ещё раз через минуту."

def detect_mode(text: str, current_mode: str) -> str:
    """Auto-detect mode from user input if not set."""
    import re
    if re.match(r"^\s*\d{3,4}\s*$", text.strip()):
        return "explore"
    return current_mode or "free"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_mode[user_id] = "explore"
    user_history[user_id] = []
    
    text = (
        "👑 *Привет, принцесса!*\n\n"
        "Я ArtMuse — твой личный гид по истории искусства.\n\n"
        "Вот что я умею:\n"
        "🗺 *Эпоха* — введи год, и я расскажу об эпохе, художниках и шедеврах\n"
        "🎓 *Викторина* — проверю твои знания с разбором ошибок\n"
        "🎨 *О мастере* — всё о любом художнике: жизнь, работы, анекдоты\n"
        "💬 *Чат* — просто поговорим об искусстве\n\n"
        "_Попробуй написать год — например, 1888 или 1503_"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard())

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выбери режим:",
        reply_markup=main_menu_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if is_rate_limited(user_id):
        await update.message.reply_text(
            "⏳ Ты отправляешь слишком много сообщений. Подожди немного и попробуй снова."
        )
        return

    mode = user_mode.get(user_id, "free")
    mode = detect_mode(text, mode)
    user_mode[user_id] = mode

    # Track topic for quiz
    if mode in ("explore", "artist"):
        user_topic[user_id] = text

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    reply = await call_claude(user_id, text, mode)

    # Choose keyboard based on mode
    if mode == "explore":
        keyboard = after_explore_keyboard()
    elif mode == "quiz":
        # Check if quiz session ended (7 questions heuristic)
        score_data = user_quiz_score.get(user_id, (0, 0))
        if score_data[1] >= 5:
            keyboard = after_quiz_keyboard()
            user_quiz_score[user_id] = (0, 0)
        else:
            keyboard = None
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ])

    await update.message.reply_text(
        reply,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
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
        prompts = {
            "explore": "🗺 *Режим исследования*\n\nВведи любой год — например, *1620* или *1888* — и я расскажу о художниках и шедеврах той эпохи.",
            "artist": "🎨 *Режим художника*\n\nНазови любого мастера — *Рембрандт*, *Климт*, *Малевич* — и я расскажу всё: жизнь, стиль, главные работы.",
            "quiz": "🎓 *Режим викторины*\n\nО чём будем проверять знания? Напиши эпоху или имя художника — например, *«импрессионизм»* или *«Дали»*.",
            "free": "💬 *Свободный режим*\n\nСпрашивай всё что угодно об искусстве! Я готов рассуждать, объяснять и удивлять.",
        }
        await query.message.reply_text(prompts[mode], parse_mode=ParseMode.MARKDOWN)

    elif data == "start_quiz":
        user_mode[user_id] = "quiz"
        user_quiz_score[user_id] = (0, 0)
        topic = user_topic.get(user_id, "историю искусства")
        
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")
        reply = await call_claude(
            user_id,
            f"Начни викторину на тему: {topic}. Задай первый вопрос.",
            "quiz"
        )
        await query.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)

def main():
    if not TELEGRAM_TOKEN or not ANTHROPIC_API_KEY:
        raise ValueError("Укажи TELEGRAM_TOKEN и ANTHROPIC_API_KEY в переменных окружения!")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("quiz", lambda u, c: handle_callback(
        type("Q", (), {"callback_query": type("Q2", (), {
            "answer": lambda: None,
            "from_user": u.effective_user,
            "message": u.message,
            "data": "start_quiz"
        })()})(), c
    )))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🎨 ArtMuse запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

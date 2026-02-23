import os
import logging
import time
import random
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
user_painting: dict[int, dict] = {}
rate_limit: dict[int, list] = defaultdict(list)

RATE_LIMIT_MAX = 20
RATE_LIMIT_WINDOW = 3600

# Картины: (название, художник, url изображения, год, где хранится)
PAINTINGS = [
    {
        "title": "Звёздная ночь",
        "artist": "Винсент ван Гог",
        "years": "1853-1890",
        "year_created": "1889",
        "location": "Музей современного искусства, Нью-Йорк",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ea/Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg/1280px-Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg"
    },
    {
        "title": "Девочка с персиками",
        "artist": "Валентин Серов",
        "years": "1865-1911",
        "year_created": "1887",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d7/Valentin_Serov_-_Girl_with_Peaches_%28Vera_Mamontova%29_-_Google_Art_Project.jpg/800px-Valentin_Serov_-_Girl_with_Peaches_%28Vera_Mamontova%29_-_Google_Art_Project.jpg"
    },
    {
        "title": "Постоянство памяти",
        "artist": "Сальвадор Дали",
        "years": "1904-1989",
        "year_created": "1931",
        "location": "Музей современного искусства, Нью-Йорк",
        "url": "https://upload.wikimedia.org/wikipedia/en/d/dd/The_Persistence_of_Memory.jpg"
    },
    {
        "title": "Девушка с жемчужной серёжкой",
        "artist": "Ян Вермер",
        "years": "1632-1675",
        "year_created": "1665",
        "location": "Маурицхёйс, Гаага",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/1665_Girl_with_a_Pearl_Earring.jpg/800px-1665_Girl_with_a_Pearl_Earring.jpg"
    },
    {
        "title": "Крик",
        "artist": "Эдвард Мунк",
        "years": "1863-1944",
        "year_created": "1893",
        "location": "Национальная галерея, Осло",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Edvard_Munch%2C_1893%2C_The_Scream%2C_oil%2C_tempera_and_pastel_on_cardboard%2C_91_x_73_cm%2C_National_Gallery_of_Norway.jpg/800px-Edvard_Munch%2C_1893%2C_The_Scream%2C_oil%2C_tempera_and_pastel_on_cardboard%2C_91_x_73_cm%2C_National_Gallery_of_Norway.jpg"
    },
    {
        "title": "Утро в сосновом лесу",
        "artist": "Иван Шишкин",
        "years": "1832-1898",
        "year_created": "1889",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/Ivan_Shishkin_-_Morning_in_a_Pine_Forest.jpg/1280px-Ivan_Shishkin_-_Morning_in_a_Pine_Forest.jpg"
    },
    {
        "title": "Балерины",
        "artist": "Эдгар Дега",
        "years": "1834-1917",
        "year_created": "1878",
        "location": "Музей д'Орсе, Париж",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e4/Edgar_Degas_-_Blue_Dancers.jpg/800px-Edgar_Degas_-_Blue_Dancers.jpg"
    },
    {
        "title": "Чёрный квадрат",
        "artist": "Казимир Малевич",
        "years": "1879-1935",
        "year_created": "1915",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/en/4/4e/Kazimir_Malevich%2C_1915%2C_Black_Suprematic_Square%2C_oil_on_linen_canvas%2C_79.5_x_79.5_cm%2C_Tretyakov_Gallery%2C_Moscow.jpg"
    },
    {
        "title": "Сикстинская Мадонна",
        "artist": "Рафаэль Санти",
        "years": "1483-1520",
        "year_created": "1512",
        "location": "Галерея старых мастеров, Дрезден",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Raffael_-_Sixtinische_Madonna.jpg/800px-Raffael_-_Sixtinische_Madonna.jpg"
    },
    {
        "title": "Явление Христа народу",
        "artist": "Александр Иванов",
        "years": "1806-1858",
        "year_created": "1857",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e6/Ivanov_appearance_of_christ.jpg/1280px-Ivanov_appearance_of_christ.jpg"
    },
    {
        "title": "Подсолнухи",
        "artist": "Винсент ван Гог",
        "years": "1853-1890",
        "year_created": "1888",
        "location": "Национальная галерея, Лондон",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/46/Vincent_van_Gogh_-_Sunflowers_%281888%2C_National_Gallery_London%29.jpg/800px-Vincent_van_Gogh_-_Sunflowers_%281888%2C_National_Gallery_London%29.jpg"
    },
    {
        "title": "Купание красного коня",
        "artist": "Кузьма Петров-Водкин",
        "years": "1878-1939",
        "year_created": "1912",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d7/Petrov-Vodkin_Bathing_of_a_Red_Horse.jpg/1024px-Petrov-Vodkin_Bathing_of_a_Red_Horse.jpg"
    },
    {
        "title": "Водяные лилии",
        "artist": "Клод Моне",
        "years": "1840-1926",
        "year_created": "1906",
        "location": "Чикагский институт искусств",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/aa/Claude_Monet_-_Water_Lilies_-_1906%2C_Ryerson.jpg/1280px-Claude_Monet_-_Water_Lilies_-_1906%2C_Ryerson.jpg"
    },
    {
        "title": "Боярыня Морозова",
        "artist": "Василий Суриков",
        "years": "1848-1916",
        "year_created": "1887",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d7/Surikov_Boyarina_Morozova_1887.jpg/1280px-Surikov_Boyarina_Morozova_1887.jpg"
    },
    {
        "title": "Поцелуй",
        "artist": "Густав Климт",
        "years": "1862-1918",
        "year_created": "1908",
        "location": "Австрийская галерея Бельведер, Вена",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/40/The_Kiss_-_Gustav_Klimt_-_Google_Cultural_Institute.jpg/800px-The_Kiss_-_Gustav_Klimt_-_Google_Cultural_Institute.jpg"
    },
]

SYSTEM_PROMPT = """Ты страстный, эрудированный гид по истории искусства.
Говоришь только по-русски. Теплый и увлеченный, как любимый профессор.
Никогда не называй себя ArtMuse - говори просто "я" или "твой гид".

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

[free] - свободный разговор об искусстве.
"""

PAINTING_CHECK_PROMPT = """Пользователь угадывает картину. 

Картина: "{title}"
Художник: "{artist}"

Ответ пользователя: "{answer}"

Реши: угадал(а) ли пользователь картину или художника (полностью или частично)?
Достаточно угадать название картины ИЛИ фамилию художника.

Если угадала - ответь радостно: *Верно!* + расскажи историю этой картины: 
когда написана ({year_created}), что изображено, интересный факт о создании, где хранится ({location}).
Художника упомяни жирным с годами жизни: *{artist}* ({years}).

Если не угадала - дай одну подсказку (намекни на эпоху или страну художника, не называя имени и картины).
Подсказка должна быть короткой - одно предложение.

Никаких # заголовков. Только *жирный* и _курсив_ для форматирования.
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

def next_painting_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🖼 Следующая картина", callback_data="next_painting"),
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

async def check_painting_answer(answer: str, painting: dict) -> str:
    try:
        prompt = PAINTING_CHECK_PROMPT.format(
            title=painting["title"],
            artist=painting["artist"],
            answer=answer,
            year_created=painting["year_created"],
            location=painting["location"],
            years=painting["years"],
        )
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return "Что-то пошло не так. Попробуй ещё раз."

async def send_painting(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    painting = random.choice(PAINTINGS)
    user_painting[user_id] = painting

    try:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=painting["url"],
            caption="🖼 *Угадай картину!*\n\nКто написал эту картину? Как она называется?\nМожно ответить на любой из вопросов!",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.error(f"Failed to send photo: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="Не удалось загрузить картину. Попробуй нажать ещё раз.",
            reply_markup=after_any_keyboard()
        )

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
        "Я твой личный гид по истории искусства.\n\n"
        "🗺 *Эпоха* — введи год, расскажу об эпохе, художниках и шедеврах\n"
        "🎨 *О мастере* — всё о любом художнике: жизнь, работы, анекдоты\n"
        "🎓 *Викторина* — проверю знания с разбором ошибок\n"
        "🖼 *Картина* — угадай картину по изображению\n"
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
        await update.message.reply_text("Слишком много сообщений. Подожди немного.")
        return

    mode = user_mode.get(user_id, "free")

    # Режим угадывания картины
    if mode == "painting" and user_id in user_painting:
        painting = user_painting[user_id]
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        reply = await check_painting_answer(text, painting)

        # Если угадала - показываем кнопку следующей картины
        if "Верно" in reply or "верно" in reply or "правильно" in reply or "Правильно" in reply:
            del user_painting[user_id]
            await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN, reply_markup=next_painting_keyboard())
        else:
            await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)
        return

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

    elif data == "next_painting":
        user_mode[user_id] = "painting"
        await send_painting(query.message.chat_id, user_id, context)

    elif data.startswith("mode_"):
        mode = data.replace("mode_", "")
        user_mode[user_id] = mode
        user_history[user_id] = []

        if mode == "painting":
            await send_painting(query.message.chat_id, user_id, context)
            return

        prompts = {
            "explore": "🗺 *Эпоха*\n\nВведи любой год — например, *1620* или *1888*.",
            "artist": "🎨 *О мастере*\n\nНазови любого художника — *Рембрандт*, *Климт*, *Малевич*.",
            "quiz": "🎓 *Викторина*\n\nО чём проверяем знания? Напиши эпоху или имя художника — например, _импрессионизм_ или _Дали_.",
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

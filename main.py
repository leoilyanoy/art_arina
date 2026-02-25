import os
import logging
import time
import random
import asyncio
import httpx
from io import BytesIO
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

PAINTINGS = [
    # ===== РУССКИЕ ХУДОЖНИКИ (50) =====
    {
        "title": "Девочка с персиками",
        "artist": "Валентин Серов",
        "years": "1865-1911",
        "year_created": "1887",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d7/Valentin_Serov_-_Girl_with_Peaches_%28Vera_Mamontova%29_-_Google_Art_Project.jpg/800px-Valentin_Serov_-_Girl_with_Peaches_%28Vera_Mamontova%29_-_Google_Art_Project.jpg"
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
        "title": "Чёрный квадрат",
        "artist": "Казимир Малевич",
        "years": "1879-1935",
        "year_created": "1915",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/en/4/4e/Kazimir_Malevich%2C_1915%2C_Black_Suprematic_Square%2C_oil_on_linen_canvas%2C_79.5_x_79.5_cm%2C_Tretyakov_Gallery%2C_Moscow.jpg"
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
        "title": "Купание красного коня",
        "artist": "Кузьма Петров-Водкин",
        "years": "1878-1939",
        "year_created": "1912",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d7/Petrov-Vodkin_Bathing_of_a_Red_Horse.jpg/1024px-Petrov-Vodkin_Bathing_of_a_Red_Horse.jpg"
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
        "title": "Богатыри",
        "artist": "Виктор Васнецов",
        "years": "1848-1926",
        "year_created": "1898",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9d/Vasnetsov_Bogatyrs.jpg/1280px-Vasnetsov_Bogatyrs.jpg"
    },
    {
        "title": "Грачи прилетели",
        "artist": "Алексей Саврасов",
        "years": "1830-1897",
        "year_created": "1871",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f2/Savrasov_Rooks.jpg/800px-Savrasov_Rooks.jpg"
    },
    {
        "title": "Охотники на привале",
        "artist": "Василий Перов",
        "years": "1834-1882",
        "year_created": "1871",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Perov_-_Hunting_Party_at_Rest.jpg/1280px-Perov_-_Hunting_Party_at_Rest.jpg"
    },
    {
        "title": "Иван Грозный и сын его Иван",
        "artist": "Илья Репин",
        "years": "1844-1930",
        "year_created": "1885",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b9/Iv_grozny_repin.jpg/800px-Iv_grozny_repin.jpg"
    },
    {
        "title": "Бурлаки на Волге",
        "artist": "Илья Репин",
        "years": "1844-1930",
        "year_created": "1873",
        "location": "Русский музей, Санкт-Петербург",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a6/Repin_Barge_Haulers.jpg/1280px-Repin_Barge_Haulers.jpg"
    },
    {
        "title": "Не ждали",
        "artist": "Илья Репин",
        "years": "1844-1930",
        "year_created": "1884",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Repin_-_They_did_not_expect_him.jpg/1280px-Repin_-_They_did_not_expect_him.jpg"
    },
    {
        "title": "Утро стрелецкой казни",
        "artist": "Василий Суриков",
        "years": "1848-1916",
        "year_created": "1881",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f7/Surikov_Streltsy.jpg/1280px-Surikov_Streltsy.jpg"
    },
    {
        "title": "Меншиков в Берёзове",
        "artist": "Василий Суриков",
        "years": "1848-1916",
        "year_created": "1883",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7c/Surikov_Menshikov.jpg/800px-Surikov_Menshikov.jpg"
    },
    {
        "title": "Девятый вал",
        "artist": "Иван Айвазовский",
        "years": "1817-1900",
        "year_created": "1850",
        "location": "Русский музей, Санкт-Петербург",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b9/Aivazovsky_-_The_Ninth_Wave.jpg/1280px-Aivazovsky_-_The_Ninth_Wave.jpg"
    },
    {
        "title": "Среди волн",
        "artist": "Иван Айвазовский",
        "years": "1817-1900",
        "year_created": "1898",
        "location": "Феодосийская картинная галерея",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Aivazovsky_-_Among_the_Waves.jpg/1280px-Aivazovsky_-_Among_the_Waves.jpg"
    },
    {
        "title": "Рожь",
        "artist": "Иван Шишкин",
        "years": "1832-1898",
        "year_created": "1878",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/Shishkin_-_Rye.jpg/1280px-Shishkin_-_Rye.jpg"
    },
    {
        "title": "Лесные дали",
        "artist": "Иван Шишкин",
        "years": "1832-1898",
        "year_created": "1884",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Shishkin_forest_distances.jpg/1024px-Shishkin_forest_distances.jpg"
    },
    {
        "title": "Демон сидящий",
        "artist": "Михаил Врубель",
        "years": "1856-1910",
        "year_created": "1890",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Vrubel_Demon.jpg/800px-Vrubel_Demon.jpg"
    },
    {
        "title": "Царевна-лебедь",
        "artist": "Михаил Врубель",
        "years": "1856-1910",
        "year_created": "1900",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/thirty/Vrubel_Swan_Princess.jpg/800px-Vrubel_Swan_Princess.jpg"
    },
    {
        "title": "Алёнушка",
        "artist": "Виктор Васнецов",
        "years": "1848-1926",
        "year_created": "1881",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/Vasnetsov_Alenushka.jpg/800px-Vasnetsov_Alenushka.jpg"
    },
    {
        "title": "После побоища Игоря Святославича с половцами",
        "artist": "Виктор Васнецов",
        "years": "1848-1926",
        "year_created": "1880",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c9/Vasnetsov_After_Igoris_Battle.jpg/1280px-Vasnetsov_After_Igoris_Battle.jpg"
    },
    {
        "title": "Тройка",
        "artist": "Василий Перов",
        "years": "1834-1882",
        "year_created": "1866",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/52/Perov_-_Troika.jpg/800px-Perov_-_Troika.jpg"
    },
    {
        "title": "Московский дворик",
        "artist": "Василий Поленов",
        "years": "1844-1927",
        "year_created": "1878",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8b/Polenov_Moscow_courtyard.jpg/1024px-Polenov_Moscow_courtyard.jpg"
    },
    {
        "title": "Христос и грешница",
        "artist": "Василий Поленов",
        "years": "1844-1927",
        "year_created": "1888",
        "location": "Русский музей, Санкт-Петербург",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/Polenov_-_Christ_and_the_Adulteress.jpg/1280px-Polenov_-_Christ_and_the_Adulteress.jpg"
    },
    {
        "title": "Принцесса Грёза",
        "artist": "Михаил Врубель",
        "years": "1856-1910",
        "year_created": "1896",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3d/Vrubel_Princess_of_dream.jpg/800px-Vrubel_Princess_of_dream.jpg"
    },
    {
        "title": "Заросший пруд",
        "artist": "Василий Поленов",
        "years": "1844-1927",
        "year_created": "1879",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/57/Polenov_-_Overgrown_Pond.jpg/1280px-Polenov_-_Overgrown_Pond.jpg"
    },
    {
        "title": "Последний день Помпеи",
        "artist": "Карл Брюллов",
        "years": "1799-1852",
        "year_created": "1833",
        "location": "Русский музей, Санкт-Петербург",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/forty/Karl_Briullov_-_The_Last_Day_of_Pompeii_-_Google_Art_Project.jpg/1280px-Karl_Briullov_-_The_Last_Day_of_Pompeii_-_Google_Art_Project.jpg"
    },
    {
        "title": "Всадница",
        "artist": "Карл Брюллов",
        "years": "1799-1852",
        "year_created": "1832",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Karl_Bryullov_-_Horsewoman.jpg/800px-Karl_Bryullov_-_Horsewoman.jpg"
    },
    {
        "title": "Над вечным покоем",
        "artist": "Исаак Левитан",
        "years": "1860-1900",
        "year_created": "1894",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9f/Levitan_above_eternal_peace.jpg/1280px-Levitan_above_eternal_peace.jpg"
    },
    {
        "title": "Золотая осень",
        "artist": "Исаак Левитан",
        "years": "1860-1900",
        "year_created": "1895",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/Levitan_Zolotaya_osen.jpg/1280px-Levitan_Zolotaya_osen.jpg"
    },
    {
        "title": "Вечерний звон",
        "artist": "Исаак Левитан",
        "years": "1860-1900",
        "year_created": "1892",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c0/Levitan_vecherny_zvon.jpg/1024px-Levitan_vecherny_zvon.jpg"
    },
    {
        "title": "Портрет Мусоргского",
        "artist": "Илья Репин",
        "years": "1844-1930",
        "year_created": "1881",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/thirty/Musorgskiy.jpg/800px-Musorgskiy.jpg"
    },
    {
        "title": "Крестный ход в Курской губернии",
        "artist": "Илья Репин",
        "years": "1844-1930",
        "year_created": "1883",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Repin_Religious_Procession.jpg/1280px-Repin_Religious_Procession.jpg"
    },
    {
        "title": "Сирень",
        "artist": "Михаил Врубель",
        "years": "1856-1910",
        "year_created": "1900",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1f/Vrubel_Lilac.jpg/800px-Vrubel_Lilac.jpg"
    },
    {
        "title": "Девушка, освещённая солнцем",
        "artist": "Валентин Серов",
        "years": "1865-1911",
        "year_created": "1888",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Valentin_Serov_-_Girl_in_Sunlight.jpg/800px-Valentin_Serov_-_Girl_in_Sunlight.jpg"
    },
    {
        "title": "Портрет Иды Рубинштейн",
        "artist": "Валентин Серов",
        "years": "1865-1911",
        "year_created": "1910",
        "location": "Русский музей, Санкт-Петербург",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d0/Serov_Ida_Rubinstein.jpg/600px-Serov_Ida_Rubinstein.jpg"
    },
    {
        "title": "Снегурочка",
        "artist": "Виктор Васнецов",
        "years": "1848-1926",
        "year_created": "1899",
        "location": "Дом-музей Васнецова, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e1/Vasnetsov_snegurochka.jpg/800px-Vasnetsov_snegurochka.jpg"
    },
    {
        "title": "Взятие снежного городка",
        "artist": "Василий Суриков",
        "years": "1848-1916",
        "year_created": "1891",
        "location": "Русский музей, Санкт-Петербург",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e2/Surikov_Snowcity.jpg/1280px-Surikov_Snowcity.jpg"
    },
    {
        "title": "Письмо запорожцев турецкому султану",
        "artist": "Илья Репин",
        "years": "1844-1930",
        "year_created": "1891",
        "location": "Русский музей, Санкт-Петербург",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6a/Repin_Cossacks.jpg/1280px-Repin_Cossacks.jpg"
    },
    {
        "title": "Масленица",
        "artist": "Борис Кустодиев",
        "years": "1878-1927",
        "year_created": "1916",
        "location": "Русский музей, Санкт-Петербург",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0a/Kustodiev_Maslenitsa_1916.jpg/1280px-Kustodiev_Maslenitsa_1916.jpg"
    },
    {
        "title": "Купчиха за чаем",
        "artist": "Борис Кустодиев",
        "years": "1878-1927",
        "year_created": "1918",
        "location": "Русский музей, Санкт-Петербург",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9c/Kustodiev_Merchant%27s_Wife.jpg/800px-Kustodiev_Merchant%27s_Wife.jpg"
    },
    {
        "title": "Три царевны подземного царства",
        "artist": "Виктор Васнецов",
        "years": "1848-1926",
        "year_created": "1884",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e4/Vasnetsov_three_princesses.jpg/800px-Vasnetsov_three_princesses.jpg"
    },
    {
        "title": "Видение отроку Варфоломею",
        "artist": "Михаил Нестеров",
        "years": "1862-1942",
        "year_created": "1890",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7c/Nesterov_Bartholomew.jpg/800px-Nesterov_Bartholomew.jpg"
    },
    {
        "title": "На Шипке всё спокойно",
        "artist": "Василий Верещагин",
        "years": "1842-1904",
        "year_created": "1878",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f8/Vereshchagin-Shipka.jpg/800px-Vereshchagin-Shipka.jpg"
    },
    {
        "title": "Апофеоз войны",
        "artist": "Василий Верещагин",
        "years": "1842-1904",
        "year_created": "1871",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/thirty/Vereshchagin-Apofeoz_vojny.jpg/1280px-Vereshchagin-Apofeoz_vojny.jpg"
    },
    {
        "title": "Красная комната",
        "artist": "Анри Матисс",
        "years": "1869-1954",
        "year_created": "1908",
        "location": "Эрмитаж, Санкт-Петербург",
        "url": "https://upload.wikimedia.org/wikipedia/en/thumb/d/d1/Matisseredroom.jpg/1024px-Matisseredroom.jpg"
    },
    {
        "title": "Чёрный супрематический прямоугольник",
        "artist": "Казимир Малевич",
        "years": "1879-1935",
        "year_created": "1915",
        "location": "Русский музей, Санкт-Петербург",
        "url": "https://upload.wikimedia.org/wikipedia/en/thumb/3/3b/Malevich_-_Black_Rectangle%2C_Blue_Triangle.jpg/800px-Malevich_-_Black_Rectangle%2C_Blue_Triangle.jpg"
    },
    {
        "title": "Новая планета",
        "artist": "Константин Юон",
        "years": "1875-1958",
        "year_created": "1921",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Yuon_new_planet.jpg/1024px-Yuon_new_planet.jpg"
    },

    # ===== ЗАРУБЕЖНЫЕ ХУДОЖНИКИ (50) =====
    {
        "title": "Звёздная ночь",
        "artist": "Винсент ван Гог",
        "years": "1853-1890",
        "year_created": "1889",
        "location": "Музей современного искусства, Нью-Йорк",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ea/Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg/1280px-Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg"
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
        "title": "Ночное кафе",
        "artist": "Винсент ван Гог",
        "years": "1853-1890",
        "year_created": "1888",
        "location": "Художественная галерея Йельского университета",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Van_Gogh_-_The_Night_Cafe_-_Yale.jpg/1280px-Van_Gogh_-_The_Night_Cafe_-_Yale.jpg"
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
        "title": "Искушение святого Антония",
        "artist": "Сальвадор Дали",
        "years": "1904-1989",
        "year_created": "1946",
        "location": "Королевские музеи изящных искусств, Брюссель",
        "url": "https://upload.wikimedia.org/wikipedia/en/thumb/1/1e/Dali_-_The_Temptation_of_St._Anthony.jpg/1024px-Dali_-_The_Temptation_of_St._Anthony.jpg"
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
        "title": "Балерины",
        "artist": "Эдгар Дега",
        "years": "1834-1917",
        "year_created": "1878",
        "location": "Музей д'Орсе, Париж",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e4/Edgar_Degas_-_Blue_Dancers.jpg/800px-Edgar_Degas_-_Blue_Dancers.jpg"
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
        "title": "Завтрак на траве",
        "artist": "Эдуар Мане",
        "years": "1832-1883",
        "year_created": "1863",
        "location": "Музей д'Орсе, Париж",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Edouard_Manet_-_Le_D%C3%A9jeuner_sur_l%27herbe.jpg/1280px-Edouard_Manet_-_Le_D%C3%A9jeuner_sur_l%27herbe.jpg"
    },
    {
        "title": "Поцелуй",
        "artist": "Густав Климт",
        "years": "1862-1918",
        "year_created": "1908",
        "location": "Австрийская галерея Бельведер, Вена",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/40/The_Kiss_-_Gustav_Klimt_-_Google_Cultural_Institute.jpg/800px-The_Kiss_-_Gustav_Klimt_-_Google_Cultural_Institute.jpg"
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
        "title": "Сотворение Адама",
        "artist": "Микеланджело",
        "years": "1475-1564",
        "year_created": "1512",
        "location": "Сикстинская капелла, Ватикан",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5b/Michelangelo_-_Creation_of_Adam_%28cropped%29.jpg/1280px-Michelangelo_-_Creation_of_Adam_%28cropped%29.jpg"
    },
    {
        "title": "Рождение Венеры",
        "artist": "Сандро Боттичелли",
        "years": "1445-1510",
        "year_created": "1485",
        "location": "Галерея Уффици, Флоренция",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/26/Sandro_Botticelli_-_La_nascita_di_Venere_-_Google_Art_Project_-_edited.jpg/1280px-Sandro_Botticelli_-_La_nascita_di_Venere_-_Google_Art_Project_-_edited.jpg"
    },
    {
        "title": "Ночной дозор",
        "artist": "Рембрандт ван Рейн",
        "years": "1606-1669",
        "year_created": "1642",
        "location": "Рейксмюзеум, Амстердам",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/The_Night_Watch_-_HD.jpg/1280px-The_Night_Watch_-_HD.jpg"
    },
    {
        "title": "Автопортрет",
        "artist": "Рембрандт ван Рейн",
        "years": "1606-1669",
        "year_created": "1659",
        "location": "Национальная галерея искусства, Вашингтон",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bd/Rembrandt_van_Rijn_-_Self-Portrait_-_Google_Art_Project.jpg/800px-Rembrandt_van_Rijn_-_Self-Portrait_-_Google_Art_Project.jpg"
    },
    {
        "title": "Менины",
        "artist": "Диего Веласкес",
        "years": "1599-1660",
        "year_created": "1656",
        "location": "Музей Прадо, Мадрид",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/99/Las_Meninas_01.jpg/800px-Las_Meninas_01.jpg"
    },
    {
        "title": "Сад земных наслаждений",
        "artist": "Иероним Босх",
        "years": "1450-1516",
        "year_created": "1505",
        "location": "Музей Прадо, Мадрид",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/96/The_Garden_of_earthly_delights.jpg/800px-The_Garden_of_earthly_delights.jpg"
    },
    {
        "title": "Свобода, ведущая народ",
        "artist": "Эжен Делакруа",
        "years": "1798-1863",
        "year_created": "1830",
        "location": "Лувр, Париж",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/52/Eug%C3%A8ne_Delacroix_-_La_libert%C3%A9_guidant_le_peuple.jpg/1024px-Eug%C3%A8ne_Delacroix_-_La_libert%C3%A9_guidant_le_peuple.jpg"
    },
    {
        "title": "Большие купальщицы",
        "artist": "Поль Сезанн",
        "years": "1839-1906",
        "year_created": "1906",
        "location": "Музей искусств Филадельфии",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/Paul_C%C3%A9zanne_-_Les_Grandes_Baigneuses_%28The_Large_Bathers%29_-_Google_Art_Project.jpg/1280px-Paul_C%C3%A9zanne_-_Les_Grandes_Baigneuses_%28The_Large_Bathers%29_-_Google_Art_Project.jpg"
    },
    {
        "title": "Герника",
        "artist": "Пабло Пикассо",
        "years": "1881-1973",
        "year_created": "1937",
        "location": "Музей королевы Софии, Мадрид",
        "url": "https://upload.wikimedia.org/wikipedia/en/7/74/PicassoGuernica.jpg"
    },
    {
        "title": "Авиньонские девицы",
        "artist": "Пабло Пикассо",
        "years": "1881-1973",
        "year_created": "1907",
        "location": "Музей современного искусства, Нью-Йорк",
        "url": "https://upload.wikimedia.org/wikipedia/en/4/4c/Les_Demoiselles_d%27Avignon.jpg"
    },
    {
        "title": "Танец",
        "artist": "Анри Матисс",
        "years": "1869-1954",
        "year_created": "1910",
        "location": "Эрмитаж, Санкт-Петербург",
        "url": "https://upload.wikimedia.org/wikipedia/en/a/a7/Matissedance.jpg"
    },
    {
        "title": "Впечатление. Восход солнца",
        "artist": "Клод Моне",
        "years": "1840-1926",
        "year_created": "1872",
        "location": "Музей Мармоттан-Моне, Париж",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/59/Monet_-_Impression%2C_Sunrise.jpg/1024px-Monet_-_Impression%2C_Sunrise.jpg"
    },
    {
        "title": "Бар в Фоли-Бержер",
        "artist": "Эдуар Мане",
        "years": "1832-1883",
        "year_created": "1882",
        "location": "Институт Курто, Лондон",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Edouard_Manet%2C_A_Bar_at_the_Folies-Berg%C3%A8re.jpg/1280px-Edouard_Manet%2C_A_Bar_at_the_Folies-Berg%C3%A8re.jpg"
    },
    {
        "title": "Воскресный день на острове Гранд-Жатт",
        "artist": "Жорж Сёра",
        "years": "1859-1891",
        "year_created": "1886",
        "location": "Чикагский институт искусств",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7d/A_Sunday_on_La_Grande_Jatte%2C_Georges_Seurat%2C_1884.jpg/1280px-A_Sunday_on_La_Grande_Jatte%2C_Georges_Seurat%2C_1884.jpg"
    },
    {
        "title": "Жёлтый Христос",
        "artist": "Поль Гоген",
        "years": "1848-1903",
        "year_created": "1889",
        "location": "Галерея Олбрайт-Нокс, Буффало",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bb/Paul_Gauguin_-_The_Yellow_Christ.jpg/800px-Paul_Gauguin_-_The_Yellow_Christ.jpg"
    },
    {
        "title": "Откуда мы пришли? Кто мы? Куда мы идём?",
        "artist": "Поль Гоген",
        "years": "1848-1903",
        "year_created": "1897",
        "location": "Музей изящных искусств, Бостон",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/08/Paul_Gauguin_-_D%27ou_venons-nous.jpg/1280px-Paul_Gauguin_-_D%27ou_venons-nous.jpg"
    },
    {
        "title": "Два автопортрета",
        "artist": "Фрида Кало",
        "years": "1907-1954",
        "year_created": "1939",
        "location": "Музей современного искусства, Мехико",
        "url": "https://upload.wikimedia.org/wikipedia/en/1/1e/Frida_Kahlo_%28self_portrait%29.jpg"
    },
    {
        "title": "Американская готика",
        "artist": "Грант Вуд",
        "years": "1891-1942",
        "year_created": "1930",
        "location": "Чикагский институт искусств",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cc/Grant_Wood_-_American_Gothic_-_Google_Art_Project.jpg/800px-Grant_Wood_-_American_Gothic_-_Google_Art_Project.jpg"
    },
    {
        "title": "Портрет Адели Блох-Бауэр",
        "artist": "Густав Климт",
        "years": "1862-1918",
        "year_created": "1907",
        "location": "Новая галерея, Нью-Йорк",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/43/Gustav_Klimt_046.jpg/800px-Gustav_Klimt_046.jpg"
    },
    {
        "title": "Постель",
        "artist": "Анри де Тулуз-Лотрек",
        "years": "1864-1901",
        "year_created": "1892",
        "location": "Музей д'Орсе, Париж",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7e/Henri_de_Toulouse-Lautrec_-_In_Bed_-_Google_Art_Project.jpg/800px-Henri_de_Toulouse-Lautrec_-_In_Bed_-_Google_Art_Project.jpg"
    },
    {
        "title": "Весна (Примавера)",
        "artist": "Сандро Боттичелли",
        "years": "1445-1510",
        "year_created": "1482",
        "location": "Галерея Уффици, Флоренция",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Botticelli-primavera.jpg/1280px-Botticelli-primavera.jpg"
    },
    {
        "title": "Тайная вечеря",
        "artist": "Леонардо да Винчи",
        "years": "1452-1519",
        "year_created": "1498",
        "location": "Санта-Мария-делле-Грацие, Милан",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/%C3%9Altima_Cena_-_Da_Vinci_5.jpg/1280px-%C3%9Altima_Cena_-_Da_Vinci_5.jpg"
    },
    {
        "title": "Дама с горностаем",
        "artist": "Леонардо да Винчи",
        "years": "1452-1519",
        "year_created": "1490",
        "location": "Национальный музей, Краков",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f9/Lady_with_an_Ermine_-_Leonardo_da_Vinci_-_Google_Art_Project.jpg/800px-Lady_with_an_Ermine_-_Leonardo_da_Vinci_-_Google_Art_Project.jpg"
    },
    {
        "title": "Портрет четы Арнольфини",
        "artist": "Ян ван Эйк",
        "years": "1390-1441",
        "year_created": "1434",
        "location": "Национальная галерея, Лондон",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/33/Van_Eyck_-_Arnolfini_Portrait.jpg/800px-Van_Eyck_-_Arnolfini_Portrait.jpg"
    },
    {
        "title": "Сдача Бреды",
        "artist": "Диего Веласкес",
        "years": "1599-1660",
        "year_created": "1635",
        "location": "Музей Прадо, Мадрид",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9e/The_Surrender_of_Breda_by_Velazquez.jpg/1280px-The_Surrender_of_Breda_by_Velazquez.jpg"
    },
    {
        "title": "Прогулка",
        "artist": "Марк Шагал",
        "years": "1887-1985",
        "year_created": "1918",
        "location": "Русский музей, Санкт-Петербург",
        "url": "https://upload.wikimedia.org/wikipedia/en/3/thirty/Marc_Chagall_-_The_Promenade.jpg"
    },
    {
        "title": "Над городом",
        "artist": "Марк Шагал",
        "years": "1887-1985",
        "year_created": "1918",
        "location": "Третьяковская галерея, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/en/3/3b/Marc_Chagall_-_Over_the_Town.jpg"
    },
    {
        "title": "Девочка на шаре",
        "artist": "Пабло Пикассо",
        "years": "1881-1973",
        "year_created": "1905",
        "location": "Пушкинский музей, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/en/9/9e/Girl_on_the_Ball.jpg"
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
        "title": "Урок анатомии доктора Тульпа",
        "artist": "Рембрандт ван Рейн",
        "years": "1606-1669",
        "year_created": "1632",
        "location": "Маурицхёйс, Гаага",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/Rembrandt_-_The_Anatomy_Lesson_of_Dr._Nicolaes_Tulp.jpg/1280px-Rembrandt_-_The_Anatomy_Lesson_of_Dr._Nicolaes_Tulp.jpg"
    },
    {
        "title": "Молочница",
        "artist": "Ян Вермер",
        "years": "1632-1675",
        "year_created": "1658",
        "location": "Рейксмюзеум, Амстердам",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/20/Johannes_Vermeer_-_Het_melkmeisje_-_Google_Art_Project.jpg/800px-Johannes_Vermeer_-_Het_melkmeisje_-_Google_Art_Project.jpg"
    },
    {
        "title": "Сенокос",
        "artist": "Питер Брейгель Старший",
        "years": "1525-1569",
        "year_created": "1565",
        "location": "Лобковицкий дворец, Прага",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b6/Pieter_Bruegel_the_Elder-_The_Harvesters_-_Google_Art_Project.jpg/1280px-Pieter_Bruegel_the_Elder-_The_Harvesters_-_Google_Art_Project.jpg"
    },
    {
        "title": "Сон",
        "artist": "Франсиско Гойя",
        "years": "1746-1828",
        "year_created": "1799",
        "location": "Музей Прадо, Мадрид",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a4/Francisco_de_Goya_y_Lucientes_-_The_Sleep_of_Reason_Produces_Monsters_%28No._43%29%2C_from_Los_Caprichos_-_Google_Art_Project.jpg/800px-Francisco_de_Goya_y_Lucientes_-_The_Sleep_of_Reason_Produces_Monsters_%28No._43%29%2C_from_Los_Caprichos_-_Google_Art_Project.jpg"
    },
    {
        "title": "Сатурн, пожирающий своего сына",
        "artist": "Франсиско Гойя",
        "years": "1746-1828",
        "year_created": "1823",
        "location": "Музей Прадо, Мадрид",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Francisco_de_Goya%2C_Saturno_devorando_a_su_hijo_%281819-1823%29.jpg/800px-Francisco_de_Goya%2C_Saturno_devorando_a_su_hijo_%281819-1823%29.jpg"
    },
    {
        "title": "Три музыканта",
        "artist": "Пабло Пикассо",
        "years": "1881-1973",
        "year_created": "1921",
        "location": "Музей современного искусства, Нью-Йорк",
        "url": "https://upload.wikimedia.org/wikipedia/en/3/3c/Pablo_Picasso%2C_1921%2C_Nous_autres_musiciens_%28Three_Musicians%29%2C_oil_on_canvas%2C_204.5_x_188.3_cm%2C_Philadelphia_Museum_of_Art.jpg"
    },
    {
        "title": "Красные виноградники в Арле",
        "artist": "Винсент ван Гог",
        "years": "1853-1890",
        "year_created": "1888",
        "location": "Пушкинский музей, Москва",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7a/Van_Gogh_-_Red_vineyards.jpg/1280px-Van_Gogh_-_Red_vineyards.jpg"
    },
    {
        "title": "Портрет папы Иннокентия X",
        "artist": "Диего Веласкес",
        "years": "1599-1660",
        "year_created": "1650",
        "location": "Галерея Дориа-Памфили, Рим",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0e/Pope_Innocent_X._by_Velazquez.jpg/800px-Pope_Innocent_X._by_Velazquez.jpg"
    },
    {
        "title": "Олимпия",
        "artist": "Эдуар Мане",
        "years": "1832-1883",
        "year_created": "1863",
        "location": "Музей д'Орсе, Париж",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/Edouard_Manet_-_Olympia_-_Google_Art_Project_2.jpg/1280px-Edouard_Manet_-_Olympia_-_Google_Art_Project_2.jpg"
    },
    {
        "title": "Купальщицы в Аньере",
        "artist": "Жорж Сёра",
        "years": "1859-1891",
        "year_created": "1884",
        "location": "Национальная галерея, Лондон",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c0/Georges_Seurat_-_Bathers_at_Asnieres.jpg/1280px-Georges_Seurat_-_Bathers_at_Asnieres.jpg"
    },
]

SYSTEM_PROMPT = """Ты страстный, эрудированный гид по истории искусства.
Говоришь только по-русски. Теплый и увлеченный, как любимый профессор.
Никогда не называй себя ArtMuse — говори просто "я" или "твой гид".

ПРАВИЛА ФОРМАТИРОВАНИЯ (строго обязательно):
- Никаких символов # для заголовков — они отображаются как решетки в Telegram
- Никаких markdown-заголовков вообще
- Ключевые заголовки разделов всегда *жирным*
- Названия картин всегда в кавычках: "Звездная ночь"
- Имена художников всегда жирным: *Ван Гог*
- При первом упоминании художника — сразу после имени годы жизни в скобках: *Ван Гог* (1853-1890)
- Структуру делай через эмодзи и переносы строк, не через заголовки
- Используй эмодзи умеренно
- Telegram Markdown: *жирный*, _курсив_

РЕЖИМЫ:

[explore] — пользователь ввел год:
*Эпоха:* одним ярким предложением
*Художники эпохи:* Топ-5 — имя *жирным* с годами жизни, 1-2 предложения о стиле
*Шедевры:* Топ-3 с историей создания
*Интересный факт:* один поразительный факт

[quiz] — режим викторины:
- Задавай РОВНО ОДИН вопрос за раз
- После ответа: правильно или нет + объяснение
- Показывай *Счет: X/Y*
- После 5 вопросов — *Итог* с похвалой

[artist] — пользователь назвал художника:
*О мастере:* эпоха, страна, движение
*Главные работы:* 3-5 работ с историями
*Интересный факт:* смешной или трогательный анекдот

[free] — свободный разговор об искусстве.
"""

PAINTING_CHECK_PROMPT = """Пользователь угадывает картину.

Картина: "{title}"
Художник: "{artist}"

Ответ пользователя: "{answer}"

Реши: угадал(а) ли пользователь картину или художника (полностью или частично)?
Достаточно угадать название картины ИЛИ фамилию художника.

Если угадала — ответь радостно: *Верно!* + расскажи историю этой картины:
когда написана ({year_created}), что изображено, интересный факт о создании, где хранится ({location}).
Художника упомяни жирным с годами жизни: *{artist}* ({years}).

Если не угадала — дай одну короткую подсказку (намекни на эпоху или страну художника, не называя имени и картины).

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
        [InlineKeyboardButton("🖼 Следующая картина", callback_data="next_painting")],
        [InlineKeyboardButton("🏠 Меню", callback_data="main_menu")],
    ])

async def call_claude(user_id: int, user_message: str, mode: str) -> str:
    history = user_history[user_id]
    history.append({"role": "user", "content": user_message})
    if len(history) > 10:
        history = history[-10:]
        user_history[user_id] = history
    for attempt in range(5):
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
            logger.error(f"Claude API error (attempt {attempt+1}): {e}")
            if attempt < 4:
                await asyncio.sleep(2 ** attempt)
    return "Сервер перегружен, попробуй ещё раз через несколько секунд 🔄"

async def check_painting_answer(answer: str, painting: dict) -> str:
    prompt = PAINTING_CHECK_PROMPT.format(
        title=painting["title"],
        artist=painting["artist"],
        answer=answer,
        year_created=painting["year_created"],
        location=painting["location"],
        years=painting["years"],
    )
    for attempt in range(5):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API error (attempt {attempt+1}): {e}")
            if attempt < 4:
                await asyncio.sleep(2 ** attempt)
    return "Сервер перегружен, попробуй ещё раз через несколько секунд 🔄"

async def send_painting(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    # Try up to 10 random paintings
    tried = []
    available = PAINTINGS.copy()
    random.shuffle(available)
    
    for painting in available[:10]:
        user_painting[user_id] = painting
        url = painting["url"]
        caption = "🖼 *Угадай картину!*\n\nКто написал эту картину? Как она называется?\nМожно ответить на любой из вопросов!"
        
        # Method 1: download bytes with httpx
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as http:
                r = await http.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://en.wikipedia.org/",
                })
                if r.status_code == 200 and len(r.content) > 5000:
                    buf = BytesIO(r.content)
                    buf.name = "painting.jpg"
                    await context.bot.send_photo(chat_id=chat_id, photo=buf, caption=caption, parse_mode=ParseMode.MARKDOWN)
                    return
                else:
                    logger.warning(f"Bad response {r.status_code} / {len(r.content)} bytes for {painting['title']}")
        except Exception as e:
            logger.warning(f"httpx failed for '{painting['title']}': {e}")
        
        # Method 2: pass URL directly to Telegram
        try:
            await context.bot.send_photo(chat_id=chat_id, photo=url, caption=caption, parse_mode=ParseMode.MARKDOWN)
            return
        except Exception as e:
            logger.warning(f"Direct URL failed for '{painting['title']}': {e}")
            continue

    await context.bot.send_message(
        chat_id=chat_id,
        text="Не удалось загрузить картину. Попробуй ещё раз 🔄",
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

    if mode == "painting" and user_id in user_painting:
        painting = user_painting[user_id]
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        reply = await check_painting_answer(text, painting)
        if any(w in reply.lower() for w in ["верно", "правильно", "угадала", "угадал"]):
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
    await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN, reply_markup=after_any_keyboard())

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
        await query.message.reply_text(prompts[mode], parse_mode=ParseMode.MARKDOWN, reply_markup=after_any_keyboard())

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

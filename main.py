
import os
import asyncio
import sqlite3
import aiohttp
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.bot import DefaultBotProperties

# Создаем сессию с увеличенным таймаутом
session = AiohttpSession()

# В Блоке 1 замени строку bot = ... на это:
# Настройка стильного логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Конфигурация (в идеале токены выносятся в .env)
TOKEN = "8620005772:AAEs2ZB_L7f_8w5r7fsf-j9s3b6OLwcAmbk"
ADMIN_IDS = [5510184597]  # Твой ID, чтобы выдавать подписки друзьям

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
# Состояния для поиска (FSM)
class SearchState(StatesGroup):
    waiting_for_desc = State()     # Ожидание описания или фото
    waiting_for_price = State()    # Ожидание диапазона цен

    # Сюда позже добавим стильную клавиатуру
# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users 
                   (user_id INTEGER PRIMARY KEY, is_premium INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()
init_db()
# --- Хендлеры (обработчики) ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer
    welcome_text = (
        "✨ **Добро пожаловать в LOOKY!**\n\n"
        "Я помогу найти одежду на маркетплейсах по фото или описанию.\n\n"
        "Чтобы узнать, как я работаю, нажми: /help\n"
        "Или просто жми кнопку ниже! 👇"
    )
    await message.answer(welcome_text, reply_markup=get_main_kb(), parse_mode="Markdown")
# Функция для проверки подписки
def check_sub(user_id):
    if user_id in ADMIN_IDS: return True
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("SELECT is_premium FROM users WHERE user_id = ?", (user_id,))
    result = cur.fetchone()
    conn.close()
    return result and result[0] == 1
# --- ПРОДОЛЖЕНИЕ КОДА (Блок 2) ---

# Функция для создания inline-кнопок (под товаром)
def get_item_kb(url_wb, url_ozon):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="Wildberries", url=url_wb))
    builder.row(types.InlineKeyboardButton(text="Ozon", url=url_ozon))
    builder = ReplyKeyboardBuilder()
    return builder.as_markup()
# Обработчик кнопки "Подписка" (заготовка)
@dp.message(F.text == "💳 Подписка")
async def show_subs(message: types.Message):
    await message.answer(
        "💎 **Статус подписки:** Не активна\n\n"
        "Подписка дает безлимитный поиск по фото.\n"
        "Цена: 199₽ / месяц."
    )
# --- Кнопки (убедись, что они стоят ПЕРЕД хендлерами) ---
def get_main_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔍 Найти вещь")
    builder.button(text="📖 Инструкция")
    builder.button(text="💳 Подписка")
    builder.button(text="⚙️ Настройки")
    builder.adjust(1, 2, 1)
    return builder.as_markup(resize_keyboard=True)


@dp.message(Command("help"))
@dp.message(F.text == "📖 Инструкция")
async def cmd_help(message: types.Message):
    instruction = (
        "🛍️ **Как пользоваться LOOKY:**\n\n"
        "1️⃣ Нажми **'Найти вещь'**\n"
        "2️⃣ Пришли **фото** или **текст**\n"
        "3️⃣ Укажи **цену** (например, 3000)\n\n"
        "Бот сам сравнит цены и выдаст лучшие ссылки! 🔥"
    )
    await message.answer(instruction, parse_mode="Markdown")
# --- ПРОДОЛЖЕНИЕ КОДА (Блок 3) ---

# Обработка текстового описания
@dp.message(SearchState.waiting_for_desc, F.text)
async def process_text_search(message: types.Message, state: FSMContext):
    # Сохраняем текст поиска в память бота
    await state.update_data(query_text=message.text)
    await message.answer(
        f"Ищу: *{message.text}*\n"
        "Теперь напиши максимальную цену (цифрами, например 3000).\n"
        "Если цена не важна, напиши '0'.",
        parse_mode="Markdown"
    )
    await state.set_state(SearchState.waiting_for_price)

# Обработка ФОТО
@dp.message(SearchState.waiting_for_desc, F.photo)
async def process_photo_search(message: types.Message, state: FSMContext):
    # Берем самое качественное фото из присланных
    photo = message.photo[-1]
    await state.update_data(photo_id=photo.file_id)
    
    # В будущем здесь будет логика распознавания фото
    await message.answer(
        "Вижу фото! Попробую найти похожие вещи.\n"
        "На какой бюджет рассчитываешь? (Введи число)",
        parse_mode="Markdown"
    )
    await state.set_state(SearchState.waiting_for_price)
    # --- ПРОДОЛЖЕНИЕ КОДА (Блок 4) ---

# Эмуляция поиска (базовый пример для WB)
async def search_wb(query, max_price):
    # В реальности здесь будет URL к API поиска WB или парсинг
    search_url = f"https://search.wb.ru/exactmatch/ru/common/v4/search?query={query}"
    
    # Для примера создадим логику проверки цены
    # Представим, что мы получили список товаров 'items'
    items = [
        {"name": "Худи Oversize", "price": 2500, "url": "https://www.wildberries.ru/catalog/123/detail.aspx"},
        {"name": "Худи Стиль", "price": 4500, "url": "https://www.wildberries.ru/catalog/456/detail.aspx"}
    ]
    
    results = []
    min_found_price = None

    for item in items:
        if min_found_price is None or item['price'] < min_found_price:
            min_found_price = item['price']
            
        if item['price'] <= max_price:
            results.append(item)
    
    return results, min_found_price

# Обработчик ввода цены и запуск поиска
@dp.message(SearchState.waiting_for_price)
async def process_price_step(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Пожалуйста, введи только цифры (например, 1500)")

    max_price = int(message.text)
    user_data = await state.get_data()
    query = user_data.get("query_text") or "Товар по фото"

    await message.answer(f"🔍 Ищу *{query}* до *{max_price}₽*...", parse_mode="Markdown")

    # Вызываем функцию поиска
    found_items, min_price = await search_wb(query, max_price)

    if found_items:
        await message.answer("✅ Вот что я нашел по твоей цене:")
        for item in found_items[:3]: # Показываем топ-3
            text = f"🔹 **{item['name']}**\n💰 Цена: {item['price']}₽"
            await message.answer(text, reply_markup=get_item_kb(item['url'], "#"), parse_mode="Markdown")
    else:
        if min_price and max_price != 0:
            await message.answer(
                f"😔 В бюджет {max_price}₽ ничего не нашлось.\n"
                f"Но я нашел варианты от **{min_price}₽**. Показать?",
                parse_mode="Markdown"
            )
        else:
            await message.answer("Такого товара сейчас нет в наличии.")
    
    await state.clear() # Сбрасываем состояние после поиска
@dp.message(F.text == "🔍 Найти вещь")
async def start_search(message: types.Message, state: FSMContext):
    if not check_sub(message.from_user.id):
        return await message.answer(
            "🔒 **Поиск доступен только по подписке.**\n\n"
            "Нажми кнопку '💳 Подписка', чтобы активировать доступ.",
            parse_mode="Markdown"
        )
    
    await state.set_state(SearchState.waiting_for_desc)
    await message.answer("Пришли фото или описание вещи:")
async def main():
    # Удаляем старые вебхуки и запускаем опрос серверов ТГ
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

async def search_wb(query, max_price):
    # Заголовки, чтобы WB думал, что мы — обычный человек с браузером
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    # Ссылка на поисковый API Wildberries

import os
import asyncio
import sqlite3
import aiohttp
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.bot import DefaultBotProperties

# Создаем сессию с увеличенным таймаутом
session = AiohttpSession()

# В Блоке 1 замени строку bot = ... на это:
# Настройка стильного логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Конфигурация (в идеале токены выносятся в .env)
TOKEN = "8620005772:AAEs2ZB_L7f_8w5r7fsf-j9s3b6OLwcAmbk"
ADMIN_IDS = [5510184597]  # Твой ID, чтобы выдавать подписки друзьям

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
# Состояния для поиска (FSM)
class SearchState(StatesGroup):
    waiting_for_desc = State()     # Ожидание описания или фото
    waiting_for_price = State()    # Ожидание диапазона цен

    # Сюда позже добавим стильную клавиатуру
# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users 
                   (user_id INTEGER PRIMARY KEY, is_premium INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()
init_db()
# --- Хендлеры (обработчики) ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer
    welcome_text = (
        "✨ **Добро пожаловать в LOOKY!**\n\n"
        "Я помогу найти одежду на маркетплейсах по фото или описанию.\n\n"
        "Чтобы узнать, как я работаю, нажми: /help\n"
        "Или просто жми кнопку ниже! 👇"
    )
    await message.answer(welcome_text, reply_markup=get_main_kb(), parse_mode="Markdown")
# Функция для проверки подписки
def check_sub(user_id):
    if user_id in ADMIN_IDS: return True
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("SELECT is_premium FROM users WHERE user_id = ?", (user_id,))
    result = cur.fetchone()
    conn.close()
    return result and result[0] == 1
# --- ПРОДОЛЖЕНИЕ КОДА (Блок 2) ---

# Функция для создания inline-кнопок (под товаром)
def get_item_kb(url_wb, url_ozon):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="Wildberries", url=url_wb))
    builder.row(types.InlineKeyboardButton(text="Ozon", url=url_ozon))
    builder = ReplyKeyboardBuilder()
    return builder.as_markup()
# Обработчик кнопки "Подписка" (заготовка)
@dp.message(F.text == "💳 Подписка")
async def show_subs(message: types.Message):
    await message.answer(
        "💎 **Статус подписки:** Не активна\n\n"
        "Подписка дает безлимитный поиск по фото.\n"
        "Цена: 199₽ / месяц."
    )
# --- Кнопки (убедись, что они стоят ПЕРЕД хендлерами) ---
def get_main_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔍 Найти вещь")
    builder.button(text="📖 Инструкция")
    builder.button(text="💳 Подписка")
    builder.button(text="⚙️ Настройки")
    builder.adjust(1, 2, 1)
    return builder.as_markup(resize_keyboard=True)


@dp.message(Command("help"))
@dp.message(F.text == "📖 Инструкция")
async def cmd_help(message: types.Message):
    instruction = (
        "🛍️ **Как пользоваться LOOKY:**\n\n"
        "1️⃣ Нажми **'Найти вещь'**\n"
        "2️⃣ Пришли **фото** или **текст**\n"
        "3️⃣ Укажи **цену** (например, 3000)\n\n"
        "Бот сам сравнит цены и выдаст лучшие ссылки! 🔥"
    )
    await message.answer(instruction, parse_mode="Markdown")
# --- ПРОДОЛЖЕНИЕ КОДА (Блок 3) ---

# Обработка текстового описания

@dp.message(SearchState.waiting_for_price)
async def process_price_step(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Пожалуйста, введи только цифры!")

    max_price = int(message.text)
    user_data = await state.get_data()
    # Берем текст, который юзер ввел на первом шаге
    query = user_data.get("query_text") 

    await message.answer(f"🔍 Ищу *{query}* до *{max_price}₽*...", parse_mode="Markdown")

    # Вызываем реальный поиск (исправим функцию ниже)
    found_items, min_price = await search_wb(query, max_price)
    
    if found_items:
        for item in found_items[:5]: # Выводим первые 5 находок
            text = f"🔹 **{item['name']}**\n💰 Цена: {item['price']}₽"
            # Передаем ссылку в кнопку
            await message.answer(text, reply_markup=get_item_kb(item['url'], "#"), parse_mode="Markdown")
    else:
        await message.answer(f"Ничего не нашлось. Самая низкая цена в поиске: {min_price}₽")
    
    await state.clear()

# Обработка ФОТО
@dp.message(SearchState.waiting_for_desc, F.photo)
async def process_photo_search(message: types.Message, state: FSMContext):
    # Берем самое качественное фото из присланных
    photo = message.photo[-1]
    await state.update_data(photo_id=photo.file_id)
    
    # В будущем здесь будет логика распознавания фото
    await message.answer(
        "Вижу фото! Попробую найти похожие вещи.\n"
        "На какой бюджет рассчитываешь? (Введи число)",
        parse_mode="Markdown"
    )
    await state.set_state(SearchState.waiting_for_price)
    # --- ПРОДОЛЖЕНИЕ КОДА (Блок 4) ---

# Эмуляция поиска (базовый пример для WB)
async def search_wb(query, max_price):
    # В реальности здесь будет URL к API поиска WB или парсинг
    search_url = f"https://search.wb.ru/exactmatch/ru/common/v4/search?query={query}"
    
    # Для примера создадим логику проверки цены
    # Представим, что мы получили список товаров 'items'
    
async def search_wb(query, max_price):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    }
    
    # Правильная ссылка для поиска (v4)
    url = f"https://search.wb.ru/exactmatch/ru/common/v4/search?appType=1&curr=rub&dest=-1257786&query={query}&resultset=catalog"
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return [], None
                
                data = await response.json()
                products = data.get('data', {}).get('products', [])
                
                results = []
                all_prices = []

                for prod in products:
                    # Конвертируем цену WB (у них 250000 это 2500 руб)
                    price = prod.get('salePriceU', 0) // 100 
                    if price > 0:
                        all_prices.append(price)
                    
                    # Фильтр по цене
                    if price <= max_price or max_price == 0:
                        results.append({
                            "name": prod.get('name'),
                            "price": price,
                            "url": f"https://www.wildberries.ru/catalog/{prod.get('id')}/detail.aspx"
                        })
                
                min_found = min(all_prices) if all_prices else None
                return results, min_found
                
        except Exception as e:
            print(f"Ошибка поиска: {e}")
            return [], None
        
    results = []
    min_found_price = None

    for item in items:
        if min_found_price is None or item['price'] < min_found_price:
            min_found_price = item['price']
            
        if item['price'] <= max_price:
            results.append(item)
    
    return results, min_found_price

# Обработчик ввода цены и запуск поиска
@dp.message(SearchState.waiting_for_price)
async def process_price_step(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Пожалуйста, введи только цифры (например, 1500)")

    max_price = int(message.text)
    user_data = await state.get_data()
    query = user_data.get("query_text") or "Товар по фото"

    await message.answer(f"🔍 Ищу *{query}* до *{max_price}₽*...", parse_mode="Markdown")

    # Вызываем функцию поиска
    found_items, min_price = await search_wb(query, max_price)

    if found_items:
        await message.answer("✅ Вот что я нашел по твоей цене:")
        for item in found_items[:3]: # Показываем топ-3
            text = f"🔹 **{item['name']}**\n💰 Цена: {item['price']}₽"
            await message.answer(text, reply_markup=get_item_kb(item['url'], "#"), parse_mode="Markdown")
    else:
        if min_price and max_price != 0:
            await message.answer(
                f"😔 В бюджет {max_price}₽ ничего не нашлось.\n"
                f"Но я нашел варианты от **{min_price}₽**. Показать?",
                parse_mode="Markdown"
            )
        else:
            await message.answer("Такого товара сейчас нет в наличии.")
    
    await state.clear() # Сбрасываем состояние после поиска
@dp.message(F.text == "🔍 Найти вещь")
async def start_search(message: types.Message, state: FSMContext):
    if not check_sub(message.from_user.id):
        return await message.answer(
            "🔒 **Поиск доступен только по подписке.**\n\n"
            "Нажми кнопку '💳 Подписка', чтобы активировать доступ.",
            parse_mode="Markdown"
        )
    
    await state.set_state(SearchState.waiting_for_desc)
    await message.answer("Пришли фото или описание вещи:")
async def main():
    # Удаляем старые вебхуки и запускаем опрос серверов ТГ
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

async def search_wb(query, max_price):
    # Заголовки, чтобы WB думал, что мы — обычный человек с браузером
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    # Ссылка на поисковый API Wildberries
    search_url = f"https://search.wb.ru/exactmatch/ru/common/v4/search?appType=1&curr=rub&dest=-1257786&query={query}&resultset=catalog&sort=popular&suppressSpellcheck=false"
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(search_url) as response:
                if response.status != 200:
                    return [], None
                
                data = await response.json()
                products = data.get('data', {}).get('products', [])
                
                results = []
                all_prices = []

                for prod in products:
                    # У WB цены хранятся в целых числах (например, 250000 вместо 2500.00)
                    price = prod.get('salePriceU', 0) // 100 
                    all_prices.append(price)
                    
                    if price <= max_price or max_price == 0:
                        results.append({
                            "name": prod.get('name'),
                            "price": price,
                            "url": f"https://www.wildberries.ru/catalog/{prod.get('id')}/detail.aspx"
                        })
                
                min_found_price = min(all_prices) if all_prices else None
                return results, min_found_price
                
        except Exception as e:
            print(f"Ошибка парсинга: {e}")
            return [], None
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")

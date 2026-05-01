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

# --- БЛОК 1: Конфигурация ---
logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [5510184597] # Твой ID

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- БЛОК 2: Состояния и БД ---
class SearchState(StatesGroup):
    waiting_for_desc = State()
    waiting_for_price = State()

def init_db():
    conn = sqlite3.connect('users.db')
    cur = conn.close() # Я заменю это на правильное открытие ниже
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users 
                   (user_id INTEGER PRIMARY KEY, is_premium INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def check_sub(user_id):
    if user_id in ADMIN_IDS: return True
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("SELECT is_premium FROM users WHERE user_id = ?", (user_id,))
    result = cur.fetchone()
    conn.close()
    return result and result[0] == 1

# --- БЛОК 3: Клавиатуры ---
def get_main_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔍 Найти вещь")
    builder.button(text="📖 Инструкция")
    builder.button(text="💳 Подписка")
    builder.button(text="⚙️ Настройки")
    builder.adjust(1, 2, 1)
    return builder.as_markup(resize_keyboard=True)

def get_item_kb(url_wb):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="Открыть на WB", url=url_wb))
    return builder.as_markup()

# --- БЛОК 4: Логика поиска (Парсинг) ---
async def search_wb(query, max_price):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*",
        "Accept-Language": "ru-RU,ru;q=0.9"
    }
    search_url = f"https://search.wb.ru/exactmatch/ru/common/v4/search?query={query}&curr=rub&dest=-1257786"
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(search_url, timeout=10) as resp:
                if resp.status != 200: return [], None
                data = await resp.json()
                products = data.get('data', {}).get('products', [])
                
                results = []
                all_prices = []
                for p in products:
                    price = p.get('salePriceU', 0) // 100
                    all_prices.append(price)
                    if price <= max_price or max_price == 0:
                        results.append({
                            "name": p.get('name'),
                            "price": price,
                            "url": f"https://www.wildberries.ru/catalog/{p.get('id')}/detail.aspx"
                        })
                
                min_found = min(all_prices) if all_prices else None
                return results, min_found
        except Exception as e:
            print(f"Ошибка парсинга: {e}")
            return [], None

# --- БЛОК 5: Хендлеры (Обработка команд) ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    init_db() # Гарантируем, что юзер в базе (упрощенно)
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    conn.close()
    
    welcome_text = (
        "✨ **Добро пожаловать в LOOKY!**\n\n"
        "Я помогу найти одежду на маркетплейсах по твоей цене.\n"
        "Чтобы начать, нажми кнопку поиска ниже."
    )
    await message.answer(welcome_text, reply_markup=get_main_kb(), parse_mode="Markdown")

@dp.message(F.text == "🔍 Найти вещь")
asy

nc def start_search(message: types.Message, state: FSMContext):
    await state.set_state(SearchState.waiting_for_desc)
    await message.answer("Пришли описание вещи (например: 'оверсайз худи'):")

@dp.message(SearchState.waiting_for_desc)
async def process_desc(message: types.Message, state: FSMContext):
    await state.update_data(query=message.text)
    await state.set_state(SearchState.waiting_for_price)
    await message.answer("Введи максимальную цену (только цифры, например: 3000):")

@dp.message(SearchState.waiting_for_price)
async def process_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Пожалуйста, введи цену цифрами!")
    
    max_p = int(message.text)
    user_data = await state.get_data()
    
    await message.answer("🔍 Ищу лучшие варианты...")
    items, min_p = await search_wb(user_data['query'], max_p)
    
    if items:
        await message.answer(f"✅ Нашел варианты до {max_p}₽:")
        for item in items[:3]: # Берем топ-3
            text = f"👕 **{item['name']}**\n💰 Цена: {item['price']}₽"
            await message.answer(text, reply_markup=get_item_kb(item['url']), parse_mode="Markdown")
    else:
        resp = f"❌ До {max_p}₽ ничего не нашлось."
        if min_p: resp += f"\nСамый дешевый вариант сейчас: {min_p}₽"
        await message.answer(resp)
    
    await state.clear()

@dp.message(F.text == "💳 Подписка")
async def cmd_sub(message: types.Message):
    status = "Активна ✅" if check_sub(message.from_user.id) else "Не активна ❌"
    await message.answer(f"Твой статус подписки: {status}\n\nДля покупки обратись к @admin")

# --- БЛОК 6: Запуск ---
async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")

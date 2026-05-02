import asyncio
import logging
import sqlite3
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

TOKEN = "8620005772:AAEs2ZB_L7f_8w5r7fsf-j9s3b6OLwcAmbk"
ADMIN_IDS = [5510184597] 

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class SearchState(StatesGroup):
    waiting_for_desc = State()
    waiting_for_price = State()

# --- КЛАВИАТУРЫ ---
def get_main_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔍 Найти вещь")
    builder.button(text="📖 Инструкция")
    builder.button(text="💳 Подписка")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

def get_item_kb(url_wb, url_ozon="#"):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="Wildberries", url=url_wb))
    if url_ozon != "#":
        builder.row(types.InlineKeyboardButton(text="Ozon", url=url_ozon))
    return builder.as_markup()

# --- БАЗА ДАННЫХ ---
def init_db():
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

# --- ЛОГИКА ПОИСКА (Парсинг WB) ---
async def search_wb(query, max_price):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
        "Accept": "*/*"
    }
    search_url = f"https://search.wb.ru/exactmatch/ru/common/v4/search?appType=1&curr=rub&dest=-1257786&query={query}&resultset=catalog&sort=popular"
    
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
                    price = prod.get('salePriceU', 0) // 100 
                    all_prices.append(price)
                    if max_price == 0 or price <= max_price:
                        results.append({
                            "name": prod.get('name'),
                            "price": price,
                            "url": f"https://www.wildberries.ru/catalog/{prod.get('id')}/detail.aspx"
                        })
                return results, (min(all_prices) if all_prices else None)
        except Exception as e:
            logging.error(f"Ошибка парсинга: {e}")
            return [], None

# --- ХЕНДЛЕРЫ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "✨ **Добро пожаловать в LOOKY!**\n\nЯ помогу найти шмот на маркетплейсах.",
        reply_markup=get_main_kb(),
        parse_mode="Markdown"
    )

@dp.message(F.text == "🔍 Найти вещь")
async def start_search(message: types.Message, state: FSMContext):
    if not check_sub(message.from_user.id):
        return await message.answer("🔒 Поиск доступен только по подписке.")
    
    await state.set_state(SearchState.waiting_for_desc)
    await message.answer("Пришли описание вещи (например: *черное худи*) или фото:", parse_mode="Markdown")

@dp.message(SearchState.waiting_for_desc, F.text)
async def process_text_search(message: types.Message, state: FSMContext):
    await state.update_data(query_text=message.text)
    await message.answer("На какой бюджет рассчитываешь? (Введи число, например 3000)")
    await state.set_state(SearchState.waiting_for_price)

@dp.message(SearchState.waiting_for_price)
async def process_price_step(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Введи только цифры!")

    max_price = int(message.text)
    user_data = await state.get_data()
    query = user_data.get("query_text", "одежда")

    await message.answer(f"🔍 Ищу {query}...")
    found_items, min_price = await search_wb(query, max_price)

    if found_items:
        for item in found_items[:3]:
            await message.answer(
                f"🔹 **{item['name']}**\n💰 Цена: {item['price']}₽",
                reply_markup=get_item_kb(item['url']),
                parse_mode="Markdown"
            )
    else:
        await message.answer(f"Ничего не нашел в бюджет {max_price}₽. Минимум на рынке сейчас: {min_price}₽")
    
    await state.clear()

@dp.message(Command("give"))
async def give_access(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        target_id = int(message.text.split()[1])
        conn = sqlite3.connect('users.db')
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO users (user_id, is_premium) VALUES (?, 1)", (target_id,))
        conn.commit()
        conn.close()
        await message.answer(f"✅ Доступ выдан `{target_id}`", parse_mode="Markdown")
    except:
        await message.answer("Пиши: `/give ID`")

async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

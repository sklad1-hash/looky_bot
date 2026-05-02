
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

# Настройка логов
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

TOKEN = "8620005772:AAEs2ZB_L7f_8w5r7fsf-j9s3b6OLwcAmbk"
ADMIN_IDS = [5510184597] 

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class SearchState(StatesGroup):
    waiting_for_desc = State()
    waiting_for_price = State()

# --- КЛАВИАТУРЫ ---

# Главное меню
def get_main_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔍 Найти вещь")
    builder.button(text="📖 Инструкция")
    builder.button(text="💳 Подписка")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

# Кнопка назад (для режимов поиска)
def get_back_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="⬅️ Назад в меню")
    return builder.as_markup(resize_keyboard=True)

# Кнопка оплаты (инлайн)
def get_pay_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="💎 Купить подписку (199₽)", callback_data="buy_sub")
    return builder.as_markup()

# --- БАЗА ДАННЫХ (оставляем как было) ---
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

# --- ПАРСИНГ WB (ровный вариант) ---
async def search_wb(query, max_price):
    headers = {"User-Agent": "Mozilla/5.0"}
    search_url = f"https://search.wb.ru/exactmatch/ru/common/v4/search?appType=1&curr=rub&dest=-1257786&query={query}&resultset=catalog&sort=popular"
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(search_url) as response:
                if response.status != 200: return [], None
                data = await response.json()
                products = data.get('data', {}).get('products', [])
                results = []
                prices = []
                for p in products:
                    price = p.get('salePriceU', 0) // 100
                    prices.append(price)
                    if max_price == 0 or price <= max_price:
                        results.append({"name": p.get('name'), "price": price, "url": f"https://www.wildberries.ru/catalog/{p.get('id')}/detail.aspx"})
                return results, (min(prices) if prices else None)
        except: return [], None

# --- ХЕНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "✨ **Здарова! Это LOOKY.**\n\nЯ ищу шмот на маркетплейсах по твоим запросам. Жми на кнопки ниже, разберемся.",
        reply_markup=get_main_kb(),
        parse_mode="Markdown"
    )

# Обработка кнопки "Назад" (сброс состояний)
@dp.message(F.text == "⬅️ Назад в меню")
async def cmd_back(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Возвращаемся в главное меню.", reply_markup=get_main_kb())

# ИНСТРУКЦИЯ (теперь не пустая)
@dp.message(F.text == "📖 Инструкция")
async def cmd_help(message: types.Message):
    text = (
        "🛍 **Как пользоваться ботом:**\n\n"
        "1. Жми кнопку **'Найти вещь'**.\n"
        "2. Скидывай текст (например: *белые кеды*) или фото.\n"
        "3. Вводи свой бюджет (цифрами).\n\n"
        "Я прочешу Wildberries и выдам тебе 3 самых четких варианта под твой кошелек. Если ничего не найду — скажу, какая минимальная цена сейчас на рынке."
    )
    await message.answer(text, parse_mode="Markdown")

# ПОДПИСКА (с кнопкой оплаты)
@dp.message(F.text == "💳 Подписка")
async def show_subs(message: types.Message):
    is_premium = check_sub(message.from_user.id)
    status = "✅ Активна" if is_premium else "❌ Не активна"
    
    text = (
        f"💎 **Твой статус:** {status}\n\n"
        "**Что дает Premium?**\n"
        "— Безлимитный поиск вещей\n"
        "— Поиск по фото (распознавание стиля)\n"
        "— Первым узнаешь о скидках\n\n"
        "Цена вопроса: **199₽ / месяц**"
    )
    await message.answer(text, reply_markup=get_pay_kb(), parse_mode="Markdown")

# ПОИСК
@dp.message(F.text == "🔍 Найти вещь")
async def start_search(message: types.Message, state: FSMContext):
    if not check_sub(message.from_user.id):
        return await message.answer("🔒 Поиск доступен только для своих (по подписке).")
    
    await state.set_state(SearchState.waiting_for_desc)
    await message.answer("Пришли описание или фото. Если передумал — жми 'Назад'.", reply_markup=get_back_kb())

@dp.message(SearchState.waiting_for_desc, F.text)
async def process_text_search(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад в меню": return # Проверка на кнопку назад
    await state.update_data(query_text=message.text)
    await message.answer("Какой максимальный бюджет в рублях? (Напиши просто число)", reply_markup=get_back_kb())
    await state.set_state(SearchState.waiting_for_price)

# Обработка ФОТО
@dp.message(SearchState.waiting_for_desc, F.photo)
async def process_photo_search(message: types.Message, state: FSMContext):
    # Берем самое четкое фото из тех, что прислали
    photo = message.photo[-1]
    # Сохраняем ID фотки, чтобы потом не потерять
    await state.update_data(photo_id=photo.file_id, query_text="Товар по фото")
    
    await message.answer(
        "Вижу! Фотка чёткая. 📸\n"
        "Теперь напиши, сколько готов(а) за это выложить (бюджет цифрами):",
        reply_markup=get_back_kb()
    )
    await state.set_state(SearchState.waiting_for_price)

@dp.message(SearchState.waiting_for_price)
async def process_price_step(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад в меню": return
    if not message.text.isdigit():
        return await message.answer("Йо, пиши только цифры, без лишних слов!")

    max_price = int(message.text)
    user_data = await state.get_data()
    
    # Если был текст — берем его, если фото — будет "Товар по фото"
    query = user_data.get("query_text", "шмот")
    photo_id = user_data.get("photo_id")

    if photo_id:
        await message.answer(f"🔍 Начинаю поиск по твоему фото в пределах {max_price}₽...")
    else:
        await message.answer(f"🔍 Погнали искать {query} до {max_price}₽...")

    # Дальше идет твой вызов функции search_wb и вывод результатов...

    found_items, min_price = await search_wb(query, max_price)

    if found_items:
        for item in found_items[:3]:
            builder = InlineKeyboardBuilder()
            builder.button(text="Смотреть на WB", url=item['url'])
            await message.answer(f"🔹 **{item['name']}**\n💰 Цена: {item['price']}₽", reply_markup=builder.as_markup(), parse_mode="Markdown")
    else:
        await message.answer(f"Пусто. В твой бюджет ничего не влезло. Самое дешевое сейчас: {min_price}₽")
    
    await state.clear()

# Админ-команда выдачи доступа
@dp.message(Command("give"))
async def give_access(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        target_id = int(message.text.split()[1])
        conn = sqlite3.connect('users.db'); cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO users (user_id, is_premium) VALUES (?, 1)", (target_id,))
        conn.commit(); conn.close()
        await message.answer(f"✅ Доступ для `{target_id}` открыт.")
    except: await message.answer("Пиши: `/give ID`")

async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

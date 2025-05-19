import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from main import extract_title_and_id, extract_keywords, find_position
import cloudscraper

# Получаем токен из переменной окружения или вставьте свой токен ниже
BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "<ВАШ ТОКЕН>")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

# user_id -> max_pages (session memory)
user_maxpages = {}

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 Привет! Пришли мне ссылку на товар Wildberries (и опционально число страниц через пробел), и я покажу позиции по ключевым словам.\n\nПример: https://www.wildberries.ru/catalog/145726284/detail.aspx \n\nИли установи значение по умолчанию командой /maxpages 5"
    )

@dp.message(Command("maxpages"))
async def set_maxpages(message: Message):
    parts = message.text.strip().split()
    if len(parts) == 2 and parts[1].isdigit():
        max_pages = int(parts[1])
        user_maxpages[message.from_user.id] = max_pages
        await message.answer(f"✅ Значение max-pages по умолчанию установлено: {max_pages}")
    else:
        await message.answer("Используй: /maxpages 5")

@dp.message(F.text)
async def handle_url(message: Message):
    text = message.text.strip()
    parts = text.split()
    url = parts[0]
    max_pages = 3  # default
    # Если пользователь указал число после ссылки
    if len(parts) > 1 and parts[1].isdigit():
        max_pages = int(parts[1])
    elif message.from_user.id in user_maxpages:
        max_pages = user_maxpages[message.from_user.id]
    if not url.startswith("http") or "wildberries.ru/catalog/" not in url:
        await message.answer("Пожалуйста, пришли корректную ссылку на товар Wildberries.")
        return
    await message.answer(f"⏳ Ищу позиции товара (max-pages: {max_pages})... Это может занять до 30 секунд.")
    try:
        scraper = cloudscraper.create_scraper()
        title, product_id = extract_title_and_id(url, scraper)
        keywords = extract_keywords(title)
        result = f"<b>Заголовок:</b> {title}\n<b>ID:</b> {product_id}\n\n<b>Ключевые слова:</b> {', '.join(keywords)}\n\n"
        for kw in keywords:
            page_num, pos, checked = find_position(kw, product_id, scraper, max_pages)
            if page_num:
                result += f"<b>{kw}</b>: страница {page_num}, позиция {pos} (проверено ссылок: {checked})\n"
            else:
                result += f"<b>{kw}</b>: не найдено в первых {max_pages} страницах (проверено ссылок: {checked})\n"
        await message.answer(result)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 
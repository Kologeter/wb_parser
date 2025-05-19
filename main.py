# wildberries_rank_checker.py

import asyncio
import re
import sys
import argparse
from urllib.parse import quote_plus

from playwright.async_api import async_playwright

# Небольшой набор русских стоп-слов
STOPWORDS = {
    "и", "в", "на", "с", "по", "из", "за", "к", "о", "от", "для",
    "что", "это", "как", "так", "его", "ее", "но", "или", "а",
}

async def extract_title_and_id(page, url):
    await page.goto(url, wait_until="domcontentloaded")
    # Ждем появления заголовка товара
    h1 = await page.locator("h1").first
    title = (await h1.inner_text()).strip()
    # ID товара обычно содержится в URL как цифры
    m = re.search(r"/(\d+)(?:/|$)", url)
    product_id = m.group(1) if m else None
    return title, product_id

def extract_keywords(title, max_keywords=5):
    # Все русские слова
    words = re.findall(r"[А-Яа-яЁё]+", title)
    kws = []
    for w in words:
        w_low = w.lower()
        if len(w_low) > 3 and w_low not in STOPWORDS and w_low not in kws:
            kws.append(w_low)
        if len(kws) >= max_keywords:
            break
    return kws

async def find_position(playwright, query, product_id, max_pages=5):
    browser = await playwright.chromium.launch()
    page = await browser.new_page()
    # Пробегаем страницы выдачи
    for p in range(1, max_pages + 1):
        url = f"https://www.wildberries.ru/catalog/0/search.aspx?search={quote_plus(query)}&page={p}"
        await page.goto(url, wait_until="networkidle")
        # Ищем карточки товаров, у них есть атрибут data-nm-id
        cards = await page.locator("[data-nm-id]").all()
        for idx, card in enumerate(cards, start=1):
            nm = await card.get_attribute("data-nm-id")
            if nm == product_id:
                await browser.close()
                return (p, idx)
    await browser.close()
    return (None, None)

async def main():
    parser = argparse.ArgumentParser(
        description="Проверка позиций Wildberries-товара по ключевым словам."
    )
    parser.add_argument("url", help="Ссылка на страницу товара Wildberries")
    parser.add_argument(
        "--max-pages", type=int, default=3,
        help="Сколько страниц выдачи сканировать (по умолчанию 3)"
    )
    args = parser.parse_args()

    async with async_playwright() as pw:
        title, product_id = await extract_title_and_id(pw, args.url)
        if not product_id:
            print("Не удалось определить ID товара из URL.", file=sys.stderr)
            sys.exit(1)

        print(f"Заголовок товара: {title}")
        print(f"ID товара: {product_id}\n")

        keywords = extract_keywords(title)
        if not keywords:
            print("Не удалось извлечь ключевые слова из заголовка.", file=sys.stderr)
            sys.exit(1)

        print("Ключевые слова для запросов:", ", ".join(keywords), "\n")

        for kw in keywords:
            page_num, pos = await find_position(pw, kw, product_id, args.max_pages)
            if page_num:
                print(f"Запрос «{kw}»: страница {page_num}, позиция {pos}")
            else:
                print(f"Запрос «{kw}»: товар не найден в первых {args.max_pages} страницах")

if __name__ == "__main__":
    asyncio.run(main())

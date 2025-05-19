
import re
import sys
import argparse
from time import sleep
from urllib.parse import quote_plus

import cloudscraper
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError

STOPWORDS = {
    "и", "в", "на", "с", "по", "из", "за", "к", "о", "от", "для",
    "что", "это", "как", "так", "его", "ее", "но", "или", "а",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Referer": "https://www.wildberries.ru/",
}

API_URL = "https://card.wb.ru/cards/detail"

def extract_title_and_id(url, scraper):
    """
    Берёт артикул из URL, запрашивает JSON-API Wildberries
    и возвращает реальное название товара и его ID.
    """
    m = re.search(r"/catalog/(\d+)(?:/|$)", url)
    if not m:
        print("❌ Не удалось извлечь артикул из URL.", file=sys.stderr)
        sys.exit(1)
    product_id = m.group(1)

    params = {
        "dest": "-1257786",  
        "nm": product_id,
    }
    try:
        resp = scraper.get(API_URL, params=params, timeout=10, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
    except HTTPError as e:
        code = getattr(e.response, "status_code", "")
        print(f"❌ HTTP {code} при запросе JSON-API товара: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Сетевая ошибка при запросе JSON-API товара: {e}", file=sys.stderr)
        sys.exit(1)

    # 3) Извлекаем название из поля data.products[0].name
    products = data.get("data", {}).get("products") or []
    if not products:
        print("❌ В ответе JSON-API не обнаружена информация о товаре.", file=sys.stderr)
        sys.exit(1)

    title = products[0].get("name", "").strip()
    if not title:
        print("❌ Пустое название в JSON-API.", file=sys.stderr)
        sys.exit(1)

    return title, product_id

def extract_keywords(title, max_keywords=5):
    words = re.findall(r"[А-Яа-яЁё]+", title)
    kws = []
    for w in words:
        w_low = w.lower()
        if len(w_low) > 3 and w_low not in STOPWORDS and w_low not in kws:
            kws.append(w_low)
            if len(kws) >= max_keywords:
                break
    return kws

def find_position(query, product_id, scraper, max_pages=5):
    """
    Использует внутренний API поиска Wildberries и возвращает
    (page, position, checked_count) если товар найден, иначе (None, None, checked_count).
    checked_count — сколько всего товаров просмотрено.
    """
    SEARCH_API = "https://search.wb.ru/exactmatch/ru/common/v4/search"
    checked_count = 0
    for p in range(1, max_pages + 1):
        params = {
            "appType": "1",
            "dest": "-1257786",
            "curr": "rub",
            "locale": "ru",
            "lang": "ru",
            "pricemarginCoeff": "1.0",
            "query": query,
            "page": p,
            "spp": "0",
            "resultset": "catalog",    # <- обязательно
        }
        try:
            resp = scraper.get(SEARCH_API, params=params, headers=HEADERS, timeout=10)
            # print(f"[DEBUG] {resp.url}")
            # print(f"[DEBUG] {resp.text[:500]}")
            resp.raise_for_status()
            data = resp.json()
        except HTTPError as e:
            code = getattr(e.response, "status_code", "")
            print(f"❌ HTTP {code} при запросе API поиска (страница {p}): {e}", file=sys.stderr)
            return None, None, checked_count
        except Exception as e:
            print(f"❌ Сетевая ошибка при запросе API поиска (страница {p}): {e}", file=sys.stderr)
            return None, None, checked_count

        products = data.get("data", {}).get("products", [])
        for idx, item in enumerate(products, start=1):
            checked_count += 1
            if str(item.get("id")) == product_id:
                return p, idx, checked_count
        checked_count += 0  # на случай пустого products

    return None, None, checked_count

def main():
    parser = argparse.ArgumentParser(
        description="Проверка позиций Wildberries-товара (cloudscraper)."
    )
    parser.add_argument("url", help="Ссылка на страницу товара Wildberries")
    parser.add_argument("-m", "--max-pages", type=int, default=3,
                        help="Сколько страниц выдачи сканировать")
    args = parser.parse_args()

    scraper = cloudscraper.create_scraper()
    title, product_id = extract_title_and_id(args.url, scraper)
    print(f"Заголовок: {title}\nID: {product_id}\n")

    keywords = extract_keywords(title)
    print("Ключевые слова:", ", ".join(keywords), "\n")

    for kw in keywords:
        page_num, pos, checked = find_position(kw, product_id, scraper, args.max_pages)
        if page_num:
            print(f"«{kw}»: страница {page_num}, позиция {pos} (проверено ссылок: {checked})")
        else:
            print(f"«{kw}»: не найдено в первых {args.max_pages} страницах (проверено ссылок: {checked})")

if __name__ == "__main__":
    main()

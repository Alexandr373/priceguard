import aiohttp
import re
import json
import logging

logger = logging.getLogger("wb_parser")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.wildberries.ru/",
    "Origin": "https://www.wildberries.ru",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
}

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.wildberries.ru/",
    "Origin": "https://www.wildberries.ru",
}


async def parse_from_html(url, nm_id):
    """Запасной метод: парсим цену из HTML-страницы."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=20), allow_redirects=True) as resp:
                if resp.status != 200:
                    logger.warning(f"HTML статус {resp.status} для {url}")
                    return None
                html = await resp.text()

        # Ищем цену в JSON-LD
        soup_json_pattern = r'<script type="application/ld\+json"[^>]*>(.*?)</script>'
        matches = re.findall(soup_json_pattern, html, re.DOTALL)
        for match in matches:
            try:
                data = json.loads(match)
                if isinstance(data, dict):
                    offers = data.get("offers", {})
                    price = offers.get("price", 0)
                    name = data.get("name", "")
                    if price:
                        logger.info(f"HTML JSON-LD: цена {int(float(price))} ₽")
                        return {"price": int(float(price)), "name": name}
            except Exception:
                continue

        # Ищем цену в meta-тегах
        meta_pattern = r'<meta[^>]+itemprop=["\']price["\'][^>]+content=["\']([\d.]+)["\']'
        match = re.search(meta_pattern, html)
        if match:
            logger.info(f"HTML meta: цена {int(float(match.group(1)))} ₽")
            return {"price": int(float(match.group(1))), "name": ""}

        # Ищем цену в скриптах (WB часто embedит данные)
        price_pattern = r'"price":\s*(\d+)'
        match = re.search(price_pattern, html)
        if match:
            raw = int(match.group(1))
            # WB хранит цену в копейках, если число > 100000
            price = raw / 100 if raw > 100000 else raw
            logger.info(f"HTML script: цена {int(price)} ₽")
            return {"price": int(price), "name": ""}

        logger.warning(f"Цена не найдена в HTML для {nm_id}")
        return None
    except Exception as e:
        logger.error(f"Ошибка HTML-парсинга {nm_id}: {e}")
        return None


async def get_wb_price(url):
    match = re.search(r'/catalog/(\d+)/', url)
    if not match:
        logger.error(f"Не удалось извлечь ID из URL: {url}")
        return None
    nm_id = match.group(1)

    # Метод 1: API v4
    api_urls = [
        f"https://card.wb.ru/cards/v4/detail?appType=1&curr=rub&dest=-1257786&spp=30&hide_dtype=10&ab_testing=false&lang=ru&nm={nm_id}",
        f"https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=30&hide_dtype=10&ab_testing=false&lang=ru&nm={nm_id}",
        f"https://card.wb.ru/cards/v1/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm={nm_id}",
    ]

    for api_url in api_urls:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=API_HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 403:
                        logger.warning(f"403 на {api_url}")
                        continue
                    if resp.status != 200:
                        logger.warning(f"Статус {resp.status} на {api_url}")
                        continue
                    data = await resp.json()

            products = data.get("data", {}).get("products", [])
            if not products:
                continue

            product = products[0]
            name = product.get("name", "")

            price = None
            for field in ["salePriceU", "priceU", "sale_price_u", "price_u"]:
                val = product.get(field)
                if val and val > 0:
                    price = int(val) / 100
                    break

            if not price:
                sizes = product.get("sizes", [])
                if sizes:
                    price_obj = sizes[0].get("price", {})
                    for field in ["total", "basic", "product"]:
                        val = price_obj.get(field)
                        if val and val > 0:
                            price = int(val) / 100
                            break

            if price:
                logger.info(f"API: WB {nm_id} — {int(price)} ₽")
                return {"price": int(price), "name": name}

        except Exception as e:
            logger.error(f"Ошибка API {nm_id}: {e}")
            continue

    # Метод 2: HTML-страница
    logger.info(f"Пробуем HTML для {nm_id}")
    return await parse_from_html(url, nm_id)

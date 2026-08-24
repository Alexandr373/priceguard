import aiohttp
import re
import json
import logging

logger = logging.getLogger("wb_parser")

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.wildberries.ru/",
    "Origin": "https://www.wildberries.ru",
}


async def fetch_via_proxy(api_url):
    """Запрос через бесплатный CORS-прокси allorigins."""
    proxy_url = f"https://api.allorigins.win/raw?url={api_url}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(proxy_url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    logger.warning(f"Прокси статус {resp.status}")
                    return None
                return await resp.json(content_type=None)
    except Exception as e:
        logger.error(f"Ошибка прокси: {e}")
        return None


async def fetch_direct(api_url):
    """Прямой запрос (для не-заблокированных IP)."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=API_HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
    except Exception:
        return None


def extract_price(data, nm_id):
    """Извлекает цену из JSON ответа WB."""
    products = data.get("data", {}).get("products", [])
    if not products:
        return None, None
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
        return int(price), name
    return None, name


async def get_wb_price(url):
    match = re.search(r'/catalog/(\d+)/', url)
    if not match:
        return None
    nm_id = match.group(1)

    api_urls = [
        f"https://card.wb.ru/cards/v4/detail?appType=1&curr=rub&dest=-1257786&spp=30&hide_dtype=10&ab_testing=false&lang=ru&nm={nm_id}",
        f"https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=30&hide_dtype=10&ab_testing=false&lang=ru&nm={nm_id}",
    ]

    # Метод 1: прямой запрос
    for api_url in api_urls:
        data = await fetch_direct(api_url)
        if data:
            price, name = extract_price(data, nm_id)
            if price:
                logger.info(f"Прямой запрос: WB {nm_id} — {price} ₽")
                return {"price": price, "name": name}

    # Метод 2: через прокси allorigins
    logger.info(f"Пробуем через прокси для {nm_id}")
    for api_url in api_urls:
        data = await fetch_via_proxy(api_url)
        if data:
            price, name = extract_price(data, nm_id)
            if price:
                logger.info(f"Через прокси: WB {nm_id} — {price} ₽")
                return {"price": price, "name": name}

    logger.warning(f"WB {nm_id}: все методы не сработали")
    return None

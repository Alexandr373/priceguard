import aiohttp
import re
import json
import logging
from urllib.parse import quote

logger = logging.getLogger("wb_parser")

MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Accept": "application/json",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

DESKTOP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Referer": "https://www.wildberries.ru/",
    "Origin": "https://www.wildberries.ru",
}

PROXIES = [
    "https://corsproxy.io/?url=",
    "https://api.allorigins.win/raw?url=",
    "https://api.codetabs.com/v1/proxy/?quest=",
]


async def try_direct(api_url, headers):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return None
                return await resp.json(content_type=None)
    except Exception:
        return None


async def try_proxy(api_url, proxy_prefix):
    encoded = quote(api_url, safe="")
    proxy_url = f"{proxy_prefix}{encoded}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(proxy_url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    return None
                text = await resp.text()
                return json.loads(text)
    except Exception as e:
        logger.warning(f"Прокси {proxy_prefix[:30]}: {e}")
        return None


def extract_price(data):
    products = data.get("data", {}).get("products", [])
    if not products:
        return None, None
    product = products[0]
    name = product.get("name", "")
    for field in ["salePriceU", "priceU"]:
        val = product.get(field)
        if val and val > 0:
            return int(val) / 100, name
    sizes = product.get("sizes", [])
    if sizes:
        price_obj = sizes[0].get("price", {})
        for field in ["total", "basic", "product"]:
            val = price_obj.get(field)
            if val and val > 0:
                return int(val) / 100, name
    return None, name


async def get_wb_price(url):
    match = re.search(r'/catalog/(\d+)/', url)
    if not match:
        return None
    nm_id = match.group(1)

    api_urls = [
        f"https://card.wb.ru/cards/v4/detail?appType=1&curr=rub&dest=-1257786&spp=30&hide_dtype=10&ab_testing=false&lang=ru&nm={nm_id}",
        f"https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=30&hide_dtype=10&ab_testing=false&lang=ru&nm={nm_id}",
        # Мобильный эндпоинт
        f"https://card.wb.ru/cards/v1/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm={nm_id}",
    ]

    # Метод 1: прямые запросы (мобильный + десктоп UA)
    for api_url in api_urls:
        for headers in [MOBILE_HEADERS, DESKTOP_HEADERS]:
            data = await try_direct(api_url, headers)
            if data:
                price, name = extract_price(data)
                if price:
                    logger.info(f"WB прямой: {int(price)} ₽")
                    return {"price": int(price), "name": name}

    # Метод 2: через прокси (все три сервиса)
    for api_url in api_urls:
        for proxy in PROXIES:
            data = await try_proxy(api_url, proxy)
            if data:
                price, name = extract_price(data)
                if price:
                    logger.info(f"WB через прокси: {int(price)} ₽")
                    return {"price": int(price), "name": name}

    logger.warning(f"WB {nm_id}: все методы не сработали")
    return None

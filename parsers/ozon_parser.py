import aiohttp
from bs4 import BeautifulSoup
import json
import re
import logging
from urllib.parse import quote

logger = logging.getLogger("ozon_parser")

MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

DESKTOP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

PROXIES = [
    "https://corsproxy.io/?url=",
    "https://api.allorigins.win/raw?url=",
    "https://api.codetabs.com/v1/proxy/?quest=",
]


def extract_from_html(html):
    soup = BeautifulSoup(html, "lxml")

    # JSON-LD
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            raw = script.string
            if not raw:
                continue
            data = json.loads(raw)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") in ("Product", ["Product", "BreadcrumbList"]):
                    offers = item.get("offers", {})
                    price = offers.get("price", 0)
                    name = item.get("name", "")
                    if price:
                        return int(float(price)), name
        except Exception:
            continue

    # meta itemprop=price
    meta = soup.find("meta", {"itemprop": "price"})
    if meta and meta.get("content"):
        try:
            return int(float(meta["content"])), ""
        except Exception:
            pass

    # __NEXT_DATA__ (Ozon использует Next.js)
    next_data = soup.find("script", id="__NEXT_DATA__")
    if next_data and next_data.string:
        try:
            data = json.loads(next_data.string)
            # Ищем цену в глубине объекта
            text = json.dumps(data)
            prices = re.findall(r'"price"\s*:\s*"?(\d+(?:\.\d+)?)"?', text)
            if prices:
                # Берём первое разумное значение
                for p in prices:
                    val = int(float(p))
                    if val > 10:
                        return val, ""
        except Exception:
            pass

    # Грубый поиск по HTML
    price_match = re.search(r'"price"\s*:\s*(\d+)', html)
    if price_match:
        val = int(price_match.group(1))
        if val > 10:
            return val, ""

    return None, None


async def get_ozon_price(url):
    # Метод 1: прямой запрос (мобильный + десктоп)
    for headers in [MOBILE_HEADERS, DESKTOP_HEADERS]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=True) as resp:
                    if resp.status != 200:
                        continue
                    html = await resp.text()
            price, name = extract_from_html(html)
            if price:
                logger.info(f"Ozon прямой: {price} ₽")
                return {"price": price, "name": name}
        except Exception:
            continue

    # Метод 2: через прокси
    for proxy in PROXIES:
        encoded = quote(url, safe="")
        proxy_url = f"{proxy}{encoded}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(proxy_url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status != 200:
                        continue
                    html = await resp.text()
            price, name = extract_from_html(html)
            if price:
                logger.info(f"Ozon через прокси: {price} ₽")
                return {"price": price, "name": name}
        except Exception:
            continue

    logger.warning("Ozon: все методы не сработали")
    return None

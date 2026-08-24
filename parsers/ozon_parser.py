import aiohttp
from bs4 import BeautifulSoup
import json

async def get_ozon_price(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()
    except Exception:
        return None
    soup = BeautifulSoup(html, "lxml")
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                for item in data:
                    if item.get("@type") == "Product":
                        offers = item.get("offers", {})
                        price = offers.get("price", 0)
                        name = item.get("name", "")
                        if price:
                            return {"price": int(float(price)), "name": name}
            elif isinstance(data, dict):
                if data.get("@type") == "Product":
                    offers = data.get("offers", {})
                    price = offers.get("price", 0)
                    name = data.get("name", "")
                    if price:
                        return {"price": int(float(price)), "name": name}
        except Exception:
            continue
    price_meta = soup.find("meta", {"itemprop": "price"})
    if price_meta:
        try:
            return {"price": int(float(price_meta.get("content", "0"))), "name": ""}
        except Exception:
            pass
    return None

import aiohttp
import re

async def get_wb_price(url):
    match = re.search(r'/catalog/(\d+)/', url)
    if not match:
        return None
    nm_id = match.group(1)
    api_url = f"https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=30&hide_dtype=10&ab_testing=false&lang=ru&nm={nm_id}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        product = data["data"]["products"][0]
        price = product["salePriceU"] / 100
        name = product.get("name", "")
        return {"price": int(price), "name": name}
    except Exception:
        return None

import aiohttp
import re
import logging

logger = logging.getLogger("wb_parser")

async def get_wb_price(url):
    match = re.search(r'/catalog/(\d+)/', url)
    if not match:
        logger.error(f"Не удалось извлечь ID из URL: {url}")
        return None
    nm_id = match.group(1)

    # Пробуем v4, затем v1 как fallback
    api_urls = [
        f"https://card.wb.ru/cards/v4/detail?appType=1&curr=rub&dest=-1257786&spp=30&hide_dtype=10&ab_testing=false&lang=ru&nm={nm_id}",
        f"https://card.wb.ru/cards/v1/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm={nm_id}",
    ]

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for api_url in api_urls:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        logger.warning(f"WB API статус {resp.status} для {api_url}")
                        continue
                    data = await resp.json()

            products = data.get("data", {}).get("products", [])
            if not products:
                logger.warning(f"Пустой массив products для {nm_id}")
                continue

            product = products[0]
            name = product.get("name", "")

            # Ищем цену в разных полях (WB меняет структуру)
            price = None
            for field in ["salePriceU", "priceU", "sale_price_u", "price_u"]:
                val = product.get(field)
                if val and val > 0:
                    price = int(val) / 100
                    break

            # Если не нашли — ищем в sizes[0].price
            if not price:
                sizes = product.get("sizes", [])
                if sizes:
                    price_obj = sizes[0].get("price", {})
                    for field in ["total", "basic", "product"]:
                        val = price_obj.get(field)
                        if val and val > 0:
                            price = int(val) / 100
                            break

            if not price:
                logger.warning(f"Не нашли цену для {nm_id}, поля: {list(product.keys())}")
                continue

            logger.info(f"WB {nm_id}: цена {int(price)} ₽")
            return {"price": int(price), "name": name}

        except Exception as e:
            logger.error(f"Ошибка парсинга WB {nm_id}: {e}")
            continue

    return None


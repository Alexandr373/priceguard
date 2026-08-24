import asyncio
import logging
from core.database import get_products, update_price, add_violation
from parsers.wb_parser import get_wb_price
from parsers.ozon_parser import get_ozon_price

logger = logging.getLogger("monitor")

async def check_product(product):
    pid, tg_id, link, platform, min_price, current_price = product[0], product[1], product[2], product[3], product[4], product[5]
    result = None
    if platform == "wb":
        result = await get_wb_price(link)
    elif platform == "ozon":
        result = await get_ozon_price(link)
    if not result:
        return None
    new_price = result["price"]
    if new_price != current_price:
        update_price(pid, new_price)
    if new_price < min_price:
        vid = add_violation(pid, current_price, new_price)
        return {
            "violation_id": vid, "tg_id": tg_id, "product_id": pid,
            "link": link, "name": result.get("name", ""),
            "old_price": current_price, "new_price": new_price, "min_price": min_price,
        }
    return None

async def start_monitor():
    logger.info("Мониторинг запущен")
    while True:
        try:
            products = get_products()
            for product in products:
                violation = await check_product(product)
                if violation:
                    from adapters.telegram_adapter import send_violation_alert
                    await send_violation_alert(violation)
                    logger.info(f"Нарушение: товар {violation['product_id']}")
                await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Ошибка мониторинга: {e}")
        await asyncio.sleep(1800)

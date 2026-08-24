import os
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(name)s] %(levelname)s: %(message)s"
)

async def main():
    from core.database import init_db
    from core.monitor import start_monitor
    from adapters.telegram_adapter import start_bot
    from adapters.web_adapter import start_web

    logging.info("PriceGuard запускается...")
    await init_db()
    asyncio.create_task(start_web())
    asyncio.create_task(start_monitor())
    await start_bot()

if __name__ == "__main__":
    asyncio.run(main())

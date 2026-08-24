import os
import logging
from aiohttp import web

logger = logging.getLogger("web")

async def health_handler(request):
    return web.json_response({"status": "ok", "service": "priceguard"})

async def start_web():
    app = web.Application()
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Веб-сервер на порту {port}")

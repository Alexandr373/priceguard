import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from core.database import add_product, get_products, get_violations, delete_product, update_price
from parsers.wb_parser import get_wb_price
from parsers.ozon_parser import get_ozon_price

logger = logging.getLogger("telegram")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
bot = Bot(token=TOKEN)
dp = Dispatcher()

def detect_platform(url):
    if "wildberries.ru" in url or "wb.ru" in url:
        return "wb"
    if "ozon.ru" in url:
        return "ozon"
    return None

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я PriceGuard — слежу за ценами твоих товаров и ловлю нарушения 289-ФЗ.\n\n"
        "Команды:\n"
        "/add <ссылка> <мин_цена> — добавить товар\n"
        "/list — список товаров\n"
        "/violations — нарушения\n"
        "/del <id> — удалить товар\n"
        "/help — справка"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "Справка:\n\n"
        "/add https://www.wildberries.ru/catalog/12345678/detail.aspx 1500\n"
        "— добавит товар с мин. ценой 1500 ₽\n\n"
        "/list — все товары с текущими ценами\n"
        "/violations — история нарушений 289-ФЗ\n"
        "/del 5 — удалить товар №5\n\n"
        "Поддерживаются: Wildberries, Ozon"
    )

@dp.message(Command("add"))
async def cmd_add(message: types.Message):
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Формат: /add <ссылка> <минимальная_цена>\nПример: /add https://www.wildberries.ru/catalog/12345678/detail.aspx 1500")
        return
    link = parts[1]
    try:
        min_price = float(parts[2])
    except ValueError:
        await message.answer("Цена должна быть числом. Пример: /add <ссылка> 1500")
        return
    platform = detect_platform(link)
    if not platform:
        await message.answer("Не удалось определить маркетплейс. Поддерживаются WB и Ozon.")
        return
    await message.answer("Проверяю цену...")
    result = None
    if platform == "wb":
        result = await get_wb_price(link)
    elif platform == "ozon":
        result = await get_ozon_price(link)
    name = result["name"] if result else ""
    current = result["price"] if result else min_price
    pid = add_product(message.from_user.id, link, platform, min_price, name)
    if result and current != min_price:
        update_price(pid, current)
    status = f"Товар добавлен (ID: {pid})\n"
    if result:
        status += f"Текущая цена: {current} ₽\nМинимальная: {min_price} ₽\n"
        if current < min_price:
            status += "Внимание: текущая цена уже ниже минимума!"
    else:
        status += "Не удалось получить цену. Бот будет проверять автоматически."
    status += f"\nПлощадка: {platform.upper()}"
    await message.answer(status)

@dp.message(Command("list"))
async def cmd_list(message: types.Message):
    products = get_products(message.from_user.id)
    if not products:
        await message.answer("У тебя нет товаров. Добавь: /add <ссылка> <мин_цена>")
        return
    text = "Твои товары:\n\n"
    for p in products:
        pid, _, link, platform, min_price, current_price, name = p[0], p[1], p[2], p[3], p[4], p[5], p[6]
        diff = " (!)" if current_price and min_price and current_price < min_price else ""
        text += f"#{pid} [{platform.upper()}] {name or 'Без названия'}\n"
        text += f"   Тек: {current_price} ₽ | Мин: {min_price} ₽{diff}\n\n"
    await message.answer(text)

@dp.message(Command("violations"))
async def cmd_violations(message: types.Message):
    violations = get_violations(message.from_user.id)
    if not violations:
        await message.answer("Нарушений пока не найдено. Мониторинг работает.")
        return
    text = "Нарушения 289-ФЗ:\n\n"
    for v in violations:
        vid, pid, old_p, new_p, detected, link, name, min_p = v
        text += f"#{vid} {name or 'Товар'}\n"
        text += f"   Было: {old_p} -> Стало: {new_p}\n"
        text += f"   Минимум: {min_p} | Превышение: {min_p - new_p} ₽\n"
        text += f"   Дата: {detected}\n\n"
    await message.answer(text)

@dp.message(Command("del"))
async def cmd_del(message: types.Message):
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Формат: /del <id_товара>")
        return
    try:
        pid = int(parts[1])
    except ValueError:
        await message.answer("ID должен быть числом. Пример: /del 5")
        return
    delete_product(pid, message.from_user.id)
    await message.answer(f"Товар #{pid} удалён.")

async def send_violation_alert(violation):
    tg_id = violation["tg_id"]
    text = (
        f"НАРУШЕНИЕ 289-ФЗ\n\n"
        f"Товар: {violation.get('name', 'Товар')}\n"
        f"Было: {violation['old_price']} ₽ -> Стало: {violation['new_price']} ₽\n"
        f"Твой минимум: {violation['min_price']} ₽\n"
        f"Превышение: {violation['min_price'] - violation['new_price']} ₽\n\n"
        f"{violation['link']}\n\n"
        f"Маркетплейс снизил цену ниже минимума без согласия."
    )
    try:
        await bot.send_message(tg_id, text)
    except Exception as e:
        logger.error(f"Не удалось отправить алерт: {e}")

async def start_bot():
    logger.info("Telegram-бот запущен")
    await dp.start_polling(bot)

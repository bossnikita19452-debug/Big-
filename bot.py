import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import TELEGRAM_BOT_TOKEN, SCAN_INTERVAL_HOURS
from scanner import scan_all

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(
    token=TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# ВАЖНО: замените на ваш chat_id
MY_CHAT_ID = 396041420


def format_signal(s: dict) -> str:
    """Форматировать сигнал в сообщение."""
    lines = [
        f"{s['level']} <b>LONG SIGNAL | BingX</b>",
        "",
        f"💎 Монета: <code>{s['symbol']}</code>",
        f"📊 Тип: {s['type']}",
        f"📈 Таймфрейм: {s['timeframe']}",
        "",
        f"⚠️ Условия ({s['met']}/{s['total']}):",
    ]
    for cond in s["conditions"]:
        lines.append(f"• {cond}")

    lines.extend([
        "",
        f"💰 Цена: ${s['price']:.4f}",
        f"📊 RSI: {s['rsi']}",
    ])
    return "\n".join(lines)


async def send_signals():
    """Запустить сканирование и отправить сигналы."""
    logger.info(f"Начинаю сканирование: {datetime.now()}")
    try:
        signals = await scan_all()
        logger.info(f"Найдено сигналов: {len(signals)}")

        for s in signals:
            try:
                await bot.send_message(MY_CHAT_ID, format_signal(s))
                await asyncio.sleep(0.5)  # Анти-флуд
            except Exception as e:
                logger.error(f"Ошибка отправки: {e}")
    except Exception as e:
        logger.error(f"Ошибка сканирования: {e}")


from aiogram.filters import Command

@dp.message(Command("start"))
async def cmd_start(message):
    await message.answer(
        "🤖 <b>BingX Long Scanner</b>\n\n"
        "Сканирую все фьючерсные пары каждый час.\n"
        "Присылаю сигналы для Long-позиций:\n"
        "🟢 — уверенная сделка\n"
        "🟡 — средний риск\n"
        "🔴 — опасная сделка\n\n"
        "Ожидайте первый сигнал после следующего сканирования."
    )


async def main():
    # Планировщик: запуск каждый час
    scheduler.add_job(send_signals, "interval", hours=SCAN_INTERVAL_HOURS)
    scheduler.start()

    # Первый запуск сразу
    await send_signals()

    logger.info("Бот запущен, ожидаю сообщений...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

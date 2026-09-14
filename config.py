import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# BingX (публичные данные, но подпись запроса нужна)
BINGX_API_KEY = os.getenv("BINGX_API_KEY", "")
BINGX_SECRET_KEY = os.getenv("BINGX_SECRET_KEY", "")
BINGX_BASE_URL = "https://open-api.bingx.com"

# Параметры сканирования
SCAN_INTERVAL_HOURS = 1
MIN_VOLUME_USDT = 100_000  # Минимальный объём за 24ч (в USDT)
MAX_SIGNALS_PER_HOUR = 20   # Лимит сообщений, чтобы не спамить

# Условия для сигналов
# Скальп: 5м + 15м
SCALP = {
    "ema_fast": 50,
    "ema_slow": 100,
    "rsi_min": 50,
    "rsi_max": 70,
}

# Среднесрок: 1ч + 4ч
SWING = {
    "ema_trend": 200,
    "rsi_min": 50,
    "rsi_max": 65,
    "macd_confirmation": True,
}

# Долгосрок: 1D
LONGTERM = {
    "ema_trend": 200,
    "rsi_min": 50,
    "rsi_max": 70,
}

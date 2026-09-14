import asyncio
import hashlib
import hmac
import time
from datetime import datetime

import aiohttp
import pandas as pd
from config import (
    BINGX_API_KEY, BINGX_SECRET_KEY, BINGX_BASE_URL,
    SCALP, SWING, LONGTERM, MIN_VOLUME_USDT
)
from indicators import calculate_ema, calculate_rsi, calculate_macd


# ─── Подпись запросов BingX ────────────────────────────────────────
def _sign(params: str) -> str:
    """Создать HMAC SHA256 подпись для запроса."""
    return hmac.new(
        BINGX_SECRET_KEY.encode("utf-8"),
        params.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


async def fetch_signed(session: aiohttp.ClientSession, endpoint: str, params: dict) -> dict:
    """Выполнить подписанный GET-запрос к BingX."""
    params["timestamp"] = int(time.time() * 1000)
    sorted_params = "&".join(f"{k}={v}" for k, v in sorted(params.items()) if v is not None)
    signature = _sign(sorted_params)
    url = f"{BINGX_BASE_URL}{endpoint}?{sorted_params}&signature={signature}"
    headers = {"X-BX-APIKEY": BINGX_API_KEY}
    async with session.get(url, headers=headers) as resp:
        return await resp.json()


async def get_all_futures_symbols(session: aiohttp.ClientSession) -> list[str]:
    """Получить все USDT-M фьючерсные пары BingX."""
    data = await fetch_signed(session, "/openApi/swap/v2/quote/contracts", {})
    symbols = []
    for item in data.get("data", []):
        symbol = item.get("symbol", "")
        if symbol.endswith("-USDT") and item.get("status") == 1:
            symbols.append(symbol)
    return symbols


async def get_klines(session: aiohttp.ClientSession, symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
    """Получить свечи (K-line) по символу и таймфрейму."""
    data = await fetch_signed(
        session,
        "/openApi/swap/v3/quote/klines",
        {"symbol": symbol, "interval": interval, "limit": limit}
    )
    rows = data.get("data", [])
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=[
        "open_time", "open", "high", "low", "close", "volume", "close_time"
    ])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna()


# ─── Проверка сигналов ───────────────────────────────────────────
def check_scalp(df_5m: pd.DataFrame, df_15m: pd.DataFrame) -> dict | None:
    """Скальп: 5м + 15м. Цена выше EMA(50/100), RSI(15м) > 50, MACD(15м) > 0."""
    if len(df_5m) < SCALP["ema_slow"] or len(df_15m) < 30:
        return None

    close_5m = df_5m["close"].iloc[-1]
    ema_fast = calculate_ema(df_5m, SCALP["ema_fast"]).iloc[-1]
    ema_slow = calculate_ema(df_5m, SCALP["ema_slow"]).iloc[-1]

    rsi_15m = calculate_rsi(df_15m, 14).iloc[-1]
    _, _, macd_hist = calculate_macd(df_15m)
    macd_15m = macd_hist.iloc[-1]

    conditions = [
        close_5m > ema_fast,
        close_5m > ema_slow,
        rsi_15m > SCALP["rsi_min"],
        macd_15m > 0,
    ]
    met = sum(conditions)

    if met < 1:
        return None

    if met == 4:
        level = "🟢"
    elif met == 3:
        level = "🟡"
    else:
        level = "🔴"

    return {
        "type": "Скальп (до часа)",
        "timeframe": "5м + 15м",
        "level": level,
        "met": met,
        "total": 4,
        "rsi": round(rsi_15m, 1),
        "price": close_5m,
        "conditions": [
            f"Цена > EMA({SCALP['ema_fast']}): {'✅' if conditions[0] else '❌'}",
            f"Цена > EMA({SCALP['ema_slow']}): {'✅' if conditions[1] else '❌'}",
            f"RSI(15м) > {SCALP['rsi_min']}: {'✅' if conditions[2] else '❌'}",
            f"MACD(15м) > 0: {'✅' if conditions[3] else '❌'}",
        ],
    }


def check_swing(df_1h: pd.DataFrame, df_4h: pd.DataFrame) -> dict | None:
    """Среднесрок: 1ч + 4ч. Цена > EMA(200), MACD(4ч) bullish, RSI(4ч) 50-65."""
    if len(df_1h) < SWING["ema_trend"] or len(df_4h) < 30:
        return None

    close = df_1h["close"].iloc[-1]
    ema_200 = calculate_ema(df_1h, SWING["ema_trend"]).iloc[-1]

    rsi_4h = calculate_rsi(df_4h, 14).iloc[-1]
    _, _, macd_hist = calculate_macd(df_4h)
    macd_4h = macd_hist.iloc[-1]

    conditions = [
        close > ema_200,
        SWING["rsi_min"] <= rsi_4h <= SWING["rsi_max"],
        macd_4h > 0,
        df_4h["close"].iloc[-1] > df_4h["close"].iloc[-2],  # цена растёт
    ]
    met = sum(conditions)

    if met < 1:
        return None

    if met == 4:
        level = "🟢"
    elif met == 3:
        level = "🟡"
    else:
        level = "🔴"

    return {
        "type": "Среднесрок (до 3 дней)",
        "timeframe": "1ч + 4ч",
        "level": level,
        "met": met,
        "total": 4,
        "rsi": round(rsi_4h, 1),
        "price": close,
        "conditions": [
            f"Цена > EMA(200) на 1ч: {'✅' if conditions[0] else '❌'}",
            f"RSI(4ч) в диапазоне {SWING['rsi_min']}-{SWING['rsi_max']}: {'✅' if conditions[1] else '❌'}",
            f"MACD(4ч) > 0: {'✅' if conditions[2] else '❌'}",
            f"Цена растёт на 4ч: {'✅' if conditions[3] else '❌'}",
        ],
    }


def check_longterm(df_1d: pd.DataFrame) -> dict | None:
    """Долгосрок: 1D. Цена > EMA(200), RSI 50-70, цена растёт."""
    if len(df_1d) < LONGTERM["ema_trend"]:
        return None

    close = df_1d["close"].iloc[-1]
    ema_200 = calculate_ema(df_1d, LONGTERM["ema_trend"]).iloc[-1]
    rsi = calculate_rsi(df_1d, 14).iloc[-1]

    conditions = [
        close > ema_200,
        LONGTERM["rsi_min"] <= rsi <= LONGTERM["rsi_max"],
        df_1d["close"].iloc[-1] > df_1d["close"].iloc[-5],  # растёт за 5 дней
    ]
    met = sum(conditions)

    if met < 1:
        return None

    if met == 3:
        level = "🟢"
    elif met == 2:
        level = "🟡"
    else:
        level = "🔴"

    return {
        "type": "Долгосрок (до месяца)",
        "timeframe": "1D",
        "level": level,
        "met": met,
        "total": 3,
        "rsi": round(rsi, 1),
        "price": close,
        "conditions": [
            f"Цена > EMA(200) на 1D: {'✅' if conditions[0] else '❌'}",
            f"RSI(1D) в диапазоне {LONGTERM['rsi_min']}-{LONGTERM['rsi_max']}: {'✅' if conditions[1] else '❌'}",
            f"Цена растёт за 5 дней: {'✅' if conditions[2] else '❌'}",
        ],
    }


# ─── Главная функция сканирования ─────────────────────────────────
async def scan_all() -> list[dict]:
    """Сканировать все фьючерсные пары BingX и вернуть найденные сигналы."""
    signals = []
    async with aiohttp.ClientSession() as session:
        symbols = await get_all_futures_symbols(session)

        for symbol in symbols:
            try:
                df_5m = await get_klines(session, symbol, "5m", 100)
                df_15m = await get_klines(session, symbol, "15m", 100)
                df_1h = await get_klines(session, symbol, "1h", 250)
                df_4h = await get_klines(session, symbol, "4h", 100)
                df_1d = await get_klines(session, symbol, "1d", 250)

                if df_5m.empty or df_1h.empty or df_1d.empty:
                    continue

                # Проверяем минимальный объём (сейчас $10 000 — для теста)
                volume_24h = df_1h["volume"].tail(24).sum() * df_1h["close"].iloc[-1]
                if volume_24h < MIN_VOLUME_USDT:
                    continue

                for check in [
                    check_scalp(df_5m, df_15m),
                    check_swing(df_1h, df_4h),
                    check_longterm(df_1d),
                ]:
                    if check:
                        check["symbol"] = symbol
                        signals.append(check)

            except Exception as e:
                print(f"Error scanning {symbol}: {e}")
                continue

    level_order = {"🟢": 0, "🟡": 1, "🔴": 2}
    signals.sort(key=lambda s: level_order.get(s["level"], 3))
    return signals

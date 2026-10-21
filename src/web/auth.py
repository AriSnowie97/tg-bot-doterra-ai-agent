"""Захист API Mini App: перевірка підпису Telegram initData та ліміт запитів.

Telegram WebApp передає `initData` — рядок, підписаний HMAC-SHA256 з ключем,
виведеним із токена бота. Перевіряючи підпис, ми впевнені, що запит прийшов
із Mini App всередині Telegram від реального користувача.
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

# Standard
import hashlib
import hmac
import json
import os
import time
from collections import defaultdict, deque
from urllib.parse import parse_qsl
# Special
from fastapi import Header, HTTPException

# initData старше цього віку (секунди) вважаємо простроченим
INIT_DATA_MAX_AGE = int(os.getenv("INIT_DATA_MAX_AGE", "86400"))

# Ліміт запитів до /api/chat на одного користувача
RATE_LIMIT_REQUESTS = int(os.getenv("CHAT_RATE_LIMIT", "10"))
RATE_LIMIT_WINDOW = int(os.getenv("CHAT_RATE_WINDOW", "60"))

_hits: dict[int, deque] = defaultdict(deque)


def validate_init_data(init_data: str, bot_token: str) -> dict:
    """Перевіряє підпис initData. Повертає dict з даними користувача або кидає ValueError."""
    if not init_data or not bot_token:
        raise ValueError("empty init data")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise ValueError("no hash")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise ValueError("bad signature")

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError:
        raise ValueError("bad auth_date")
    if time.time() - auth_date > INIT_DATA_MAX_AGE:
        raise ValueError("init data expired")

    user = json.loads(pairs.get("user", "{}"))
    if not isinstance(user, dict) or not isinstance(user.get("id"), int):
        raise ValueError("no user")
    return user


def _check_rate_limit(user_id: int) -> None:
    """Ковзне вікно: не більше RATE_LIMIT_REQUESTS за RATE_LIMIT_WINDOW секунд."""
    now = time.monotonic()
    q = _hits[user_id]
    while q and now - q[0] > RATE_LIMIT_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(status_code=429, detail="Забагато запитів. Спробуй трохи пізніше.")
    q.append(now)


async def require_telegram_user(
    x_telegram_init_data: str = Header(default="", alias="X-Telegram-Init-Data"),
) -> dict:
    """FastAPI-залежність: автентифікація через initData + ліміт запитів."""
    bot_token = os.getenv("BOT_TOKEN", "")
    if not bot_token:
        raise HTTPException(status_code=503, detail="Service unavailable")
    try:
        user = validate_init_data(x_telegram_init_data, bot_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Unauthorized")
    _check_rate_limit(user["id"])
    return user

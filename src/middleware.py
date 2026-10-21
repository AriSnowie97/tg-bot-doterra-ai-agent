"""Middleware для aiogram: ліміт частоти повідомлень та довжини тексту на користувача."""

# Standard
import os
import time
from collections import defaultdict, deque
from typing import Any, Awaitable, Callable
# Special
from aiogram import BaseMiddleware
from aiogram.types import Message

RATE_LIMIT_MESSAGES = int(os.getenv("BOT_RATE_LIMIT", "8"))
RATE_LIMIT_WINDOW = int(os.getenv("BOT_RATE_WINDOW", "60"))
MAX_TEXT_LENGTH = int(os.getenv("BOT_MAX_TEXT_LENGTH", "2000"))


class RateLimitMiddleware(BaseMiddleware):
    """Ковзне вікно на користувача. Адміни (exempt_ids) ліміт не мають.

    Зайві повідомлення відкидаються. Попередження надсилається лише один раз
    за вікно, щоб бот сам не спамив у відповідь.
    """

    def __init__(self, exempt_ids: set[int] | None = None) -> None:
        self.exempt_ids = exempt_ids or set()
        self._hits: dict[int, deque] = defaultdict(deque)
        self._warned_at: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        user = event.from_user
        if user is None:
            return None  # анонімні адміни груп / системні повідомлення ігноруємо
        if user.id in self.exempt_ids:
            return await handler(event, data)

        if event.text and len(event.text) > MAX_TEXT_LENGTH:
            await event.answer(f"⚠️ Занадто довге повідомлення (максимум {MAX_TEXT_LENGTH} символів).")
            return None

        now = time.monotonic()
        q = self._hits[user.id]
        while q and now - q[0] > RATE_LIMIT_WINDOW:
            q.popleft()

        if len(q) >= RATE_LIMIT_MESSAGES:
            if now - self._warned_at.get(user.id, 0) > RATE_LIMIT_WINDOW:
                self._warned_at[user.id] = now
                await event.answer("⏳ Забагато повідомлень. Зачекай хвилинку і спробуй ще раз.")
            return None

        q.append(now)
        return await handler(event, data)

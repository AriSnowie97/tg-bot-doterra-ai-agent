"""Middleware для aiogram: ліміт частоти повідомлень та довжини тексту на користувача."""

# Standard
import asyncio
import os
import time
from collections import defaultdict, deque
from typing import Any, Awaitable, Callable
# Special
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

RATE_LIMIT_MESSAGES = int(os.getenv("BOT_RATE_LIMIT", "8"))
RATE_LIMIT_WINDOW = int(os.getenv("BOT_RATE_WINDOW", "60"))
MAX_TEXT_LENGTH = int(os.getenv("BOT_MAX_TEXT_LENGTH", "2000"))
CALLBACK_RATE_LIMIT = int(os.getenv("BOT_CALLBACK_RATE_LIMIT", "20"))

# Коли словник user_id → вікно перевищує цей розмір, чистимо застарілі записи
_CLEANUP_THRESHOLD = 1000


class _SlidingWindow:
    """Ковзне вікно на користувача з періодичним очищенням застарілих записів."""

    def __init__(self, limit: int, window: int) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[int, deque] = defaultdict(deque)
        self._warned_at: dict[int, float] = {}

    def _cleanup(self, now: float) -> None:
        if len(self._hits) < _CLEANUP_THRESHOLD:
            return
        for uid in [u for u, q in self._hits.items() if not q or now - q[-1] > self.window]:
            del self._hits[uid]
            self._warned_at.pop(uid, None)

    def allow(self, user_id: int) -> bool:
        """True якщо запит дозволено (і зараховує його у вікно)."""
        now = time.monotonic()
        self._cleanup(now)
        q = self._hits[user_id]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True

    def should_warn(self, user_id: int) -> bool:
        """True не частіше одного разу за вікно — щоб бот сам не спамив."""
        now = time.monotonic()
        if now - self._warned_at.get(user_id, 0) > self.window:
            self._warned_at[user_id] = now
            return True
        return False


class RateLimitMiddleware(BaseMiddleware):
    """Ліміт повідомлень (outer middleware на dp.message).

    - Адміни (exempt_ids) ліміт не мають.
    - Якщо задано `should_limit`, ліміт та перевірка довжини діють лише для
      повідомлень, які бот реально обробить (напр. приват / @mention / reply).
      Решта (звичайні розмови в групі) проходить без змін і не зараховується.
    """

    def __init__(
        self,
        exempt_ids: set[int] | None = None,
        should_limit: Callable[[Message], bool] | None = None,
    ) -> None:
        self.exempt_ids = exempt_ids or set()
        self.should_limit = should_limit
        self._window = _SlidingWindow(RATE_LIMIT_MESSAGES, RATE_LIMIT_WINDOW)

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
        if self.should_limit is not None and not self.should_limit(event):
            return await handler(event, data)

        if event.text and len(event.text) > MAX_TEXT_LENGTH:
            await event.answer(f"⚠️ Занадто довге повідомлення (максимум {MAX_TEXT_LENGTH} символів).")
            return None

        if not self._window.allow(user.id):
            if self._window.should_warn(user.id):
                await event.answer("⏳ Забагато повідомлень. Зачекай хвилинку і спробуй ще раз.")
            return None

        return await handler(event, data)


class CallbackRateLimitMiddleware(BaseMiddleware):
    """Ліміт натискань inline-кнопок (outer middleware на dp.callback_query)."""

    def __init__(self, exempt_ids: set[int] | None = None) -> None:
        self.exempt_ids = exempt_ids or set()
        self._window = _SlidingWindow(CALLBACK_RATE_LIMIT, RATE_LIMIT_WINDOW)

    async def __call__(
        self,
        handler: Callable[[CallbackQuery, dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        uid = event.from_user.id
        if uid in self.exempt_ids or self._window.allow(uid):
            return await handler(event, data)
        await event.answer("⏳ Забагато натискань. Зачекай хвилинку.", show_alert=False)
        return None


class UserSerialMiddleware(BaseMiddleware):
    """Обробляє повідомлення одного користувача в одному чаті по черзі.

    Без цього два швидкі повідомлення читають і перезаписують FSM-стан одночасно
    (друге не бачить історію першого). Довгі адмін-команди (`exempt_commands`)
    не блокують решту повідомлень цього користувача.
    """

    def __init__(self, exempt_commands: tuple[str, ...] = ()) -> None:
        self.exempt_commands = tuple(c.lower() for c in exempt_commands)
        self._locks: dict[tuple[int, int], asyncio.Lock] = {}

    def _is_exempt(self, event: Message) -> bool:
        text = (event.text or "").strip()
        if not text.startswith("/"):
            return False
        command = text.split()[0][1:].split("@")[0].lower()
        return command in self.exempt_commands

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        user = event.from_user
        if user is None or self._is_exempt(event):
            return await handler(event, data)
        key = (event.chat.id, user.id)
        lock = self._locks.setdefault(key, asyncio.Lock())
        try:
            async with lock:
                return await handler(event, data)
        finally:
            if not lock.locked() and not getattr(lock, "_waiters", None):
                self._locks.pop(key, None)

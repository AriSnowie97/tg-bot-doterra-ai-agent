"""
doTERRA Bot — Глобальний контроль витрат та лімітів запитів до LLM (Cost & Budget Guardrails).

Забезпечує:
1. Глобальний погодинний та добовий ліміт генеративних звернень до Gemini API (запобігає неконтрольованим витратам).
2. Повну свободу для початкової синхронізації та масового завантаження чанків у базу знань (sync не блокується).
3. Захист від вичерпання пулу потоків та надмірних повторних спроб.
4. Експорт метрик використання для моніторингу та дипломного дослідження.
"""

from __future__ import annotations

import os
import time
from collections import deque
from threading import Lock


class BudgetExceededError(RuntimeError):
    """Викликається при перевищенні глобального ліміту витрат або звернень до LLM."""
    pass


# Конфігурація лімітів із змінних середовища для генеративних відповідей
MAX_LLM_CALLS_PER_HOUR = int(os.getenv("MAX_LLM_CALLS_PER_HOUR", "300"))
MAX_LLM_CALLS_PER_DAY = int(os.getenv("MAX_LLM_CALLS_PER_DAY", "2000"))

# Повідомлення для користувача при досягненні ліміту
BUDGET_EXCEEDED_MESSAGE = (
    "🌿 Сервіс тимчасово досяг максимального ліміту запитів до AI на сьогодні "
    "для захисту системи від перевантаження.\n\n"
    "Будь ласка, зверніться трохи пізніше або напишіть Наталії Котелянській: https://t.me/nkotelianskablog 🌸"
)


class GlobalLLMBudgetManager:
    """Потокобезпечний менеджер глобального бюджету звернень до AI моделей."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._hour_calls: deque[float] = deque()
        self._day_calls: deque[float] = deque()
        self._sync_mode: bool = False
        self._total_calls_count: int = 0
        self._total_embed_count: int = 0
        self._total_gen_count: int = 0

    def set_sync_mode(self, enabled: bool) -> None:
        """Вмикає або вимикає режим синхронізації/завантаження бази знань (обхід лімітів)."""
        with self._lock:
            self._sync_mode = enabled

    def is_sync_mode(self) -> bool:
        with self._lock:
            return self._sync_mode

    def check_and_consume(self, call_type: str = "generate", bypass: bool = False) -> None:
        """Перевіряє доступний бюджет і фіксує виклик.
        
        В режимі синхронізації, при bypass=True або для ембеддингів бази знань ліміти не блокують завантаження.
        
        Raises:
            BudgetExceededError: якщо ліміт вичерпано для звичайних запитів користувачів.
        """
        now = time.monotonic()
        with self._lock:
            # Фіксуємо загальну аналітику використання
            if call_type == "embed":
                self._total_embed_count += 1
            else:
                self._total_gen_count += 1
            self._total_calls_count += 1

            # Синхронізація контенту та ембеддинги не обмежуються лімітом генерації
            if self._sync_mode or bypass or (call_type == "embed"):
                return

            # Очищуємо виклики старші за 1 годину (3600 с)
            while self._hour_calls and now - self._hour_calls[0] > 3600:
                self._hour_calls.popleft()

            # Очищуємо виклики старші за 24 години (86400 с)
            while self._day_calls and now - self._day_calls[0] > 86400:
                self._day_calls.popleft()

            # Перевірка погодинного ліміту (для генерації відповідей)
            if len(self._hour_calls) >= MAX_LLM_CALLS_PER_HOUR:
                raise BudgetExceededError(
                    f"Глобальний погодинний ліміт LLM вичерпано ({len(self._hour_calls)}/{MAX_LLM_CALLS_PER_HOUR})."
                )

            # Перевірка добового ліміту (для генерації відповідей)
            if len(self._day_calls) >= MAX_LLM_CALLS_PER_DAY:
                raise BudgetExceededError(
                    f"Глобальний добовий ліміт LLM вичерпано ({len(self._day_calls)}/{MAX_LLM_CALLS_PER_DAY})."
                )

            # Фіксуємо споживання генеративних запитів
            self._hour_calls.append(now)
            self._day_calls.append(now)

    def get_stats(self) -> dict[str, int | bool]:
        """Повертає поточні метрики споживання бюджету."""
        now = time.monotonic()
        with self._lock:
            while self._hour_calls and now - self._hour_calls[0] > 3600:
                self._hour_calls.popleft()
            while self._day_calls and now - self._day_calls[0] > 86400:
                self._day_calls.popleft()

            return {
                "sync_mode": self._sync_mode,
                "generation_calls_past_hour": len(self._hour_calls),
                "limit_hour": MAX_LLM_CALLS_PER_HOUR,
                "generation_calls_past_24h": len(self._day_calls),
                "limit_day": MAX_LLM_CALLS_PER_DAY,
                "total_calls_lifetime": self._total_calls_count,
                "total_generations": self._total_gen_count,
                "total_embeddings": self._total_embed_count,
            }


# Глобальний екземпляр
budget_manager = GlobalLLMBudgetManager()

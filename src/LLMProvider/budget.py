"""
doTERRA Bot — Глобальний контроль витрат та лімітів запитів до LLM (Cost & Budget Guardrails).

Забезпечує:
1. Глобальний погодинний та добовий ліміт звернень до Gemini API (запобігає неконтрольованим витратам).
2. Захист від вичерпання пулу потоків та надмірних повторних спроб.
3. Експорт метрик використання для моніторингу та дипломного дослідження.
"""

from __future__ import annotations

import os
import time
from collections import deque
from threading import Lock


class BudgetExceededError(RuntimeError):
    """Викликається при перевищенні глобального ліміту витрат або звернень до LLM."""
    pass


# Конфігурація лімітів із змінних середовища
MAX_LLM_CALLS_PER_HOUR = int(os.getenv("MAX_LLM_CALLS_PER_HOUR", "300"))
MAX_LLM_CALLS_PER_DAY = int(os.getenv("MAX_LLM_CALLS_PER_DAY", "2000"))

# Повідомлення для користувача при досягненні ліміту
BUDGET_EXCEEDED_MESSAGE = (
    "🌿 Сервіс тимчасово досяг максимального ліміту запитів до AI на сьогодні "
    "для захисту системи від перевантаження.\n\n"
    "Будь ласка, зверніться трохи пізніше або напишіть нашому консультанту: @Nataliia_Kotelianska 🌸"
)


class GlobalLLMBudgetManager:
    """Потокобезпечний менеджер глобального бюджету звернень до AI моделей."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._hour_calls: deque[float] = deque()
        self._day_calls: deque[float] = deque()
        self._total_calls_count: int = 0
        self._total_embed_count: int = 0
        self._total_gen_count: int = 0

    def check_and_consume(self, call_type: str = "generate") -> None:
        """Перевіряє доступний бюджет і фіксує виклик.
        
        Raises:
            BudgetExceededError: якщо ліміт вичерпано.
        """
        now = time.monotonic()
        with self._lock:
            # Очищуємо виклики старші за 1 годину (3600 с)
            while self._hour_calls and now - self._hour_calls[0] > 3600:
                self._hour_calls.popleft()

            # Очищуємо виклики старші за 24 години (86400 с)
            while self._day_calls and now - self._day_calls[0] > 86400:
                self._day_calls.popleft()

            # Перевірка погодинного ліміту
            if len(self._hour_calls) >= MAX_LLM_CALLS_PER_HOUR:
                raise BudgetExceededError(
                    f"Глобальний погодинний ліміт LLM вичерпано ({len(self._hour_calls)}/{MAX_LLM_CALLS_PER_HOUR})."
                )

            # Перевірка добового ліміту
            if len(self._day_calls) >= MAX_LLM_CALLS_PER_DAY:
                raise BudgetExceededError(
                    f"Глобальний добовий ліміт LLM вичерпано ({len(self._day_calls)}/{MAX_LLM_CALLS_PER_DAY})."
                )

            # Фіксуємо споживання
            self._hour_calls.append(now)
            self._day_calls.append(now)
            self._total_calls_count += 1
            if call_type == "embed":
                self._total_embed_count += 1
            else:
                self._total_gen_count += 1

    def get_stats(self) -> dict[str, int]:
        """Повертає поточні метрики споживання бюджету."""
        now = time.monotonic()
        with self._lock:
            while self._hour_calls and now - self._hour_calls[0] > 3600:
                self._hour_calls.popleft()
            while self._day_calls and now - self._day_calls[0] > 86400:
                self._day_calls.popleft()

            return {
                "calls_past_hour": len(self._hour_calls),
                "limit_hour": MAX_LLM_CALLS_PER_HOUR,
                "calls_past_24h": len(self._day_calls),
                "limit_day": MAX_LLM_CALLS_PER_DAY,
                "total_calls_lifetime": self._total_calls_count,
                "total_generations": self._total_gen_count,
                "total_embeddings": self._total_embed_count,
            }


# Глобальний екземпляр
budget_manager = GlobalLLMBudgetManager()

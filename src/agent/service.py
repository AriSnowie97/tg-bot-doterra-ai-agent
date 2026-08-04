"""
Сервіс генерації відповідей AI-агента.

Пайплайн:
    1. Пошук релевантних чанків у pgvector (RAG)
    2. Формування системного промпту з контекстом
    3. Виклик Gemini для генерації відповіді з retry + model fallback
    4. Повернення тексту відповіді

Використання:
    from src.agent import generate_response

    answer = await generate_response("Що таке лаванда?")
"""

# Standard
import os
import re
import asyncio
# Special
from google import genai
from google.genai import types
# Local
from .prompt import build_system_prompt
from ..storage import search_chunks


# ---------------------------------------------------------------------------
# Конфігурація
# ---------------------------------------------------------------------------

# Моделі у порядку пріоритету — перебираємо при вичерпанні квоти.
GENERATION_MODELS: list[str] = [
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
]

GEMINI_API_KEYS: list[str] = [
    key for key in [
        os.getenv("GEMINI_API_KEY_1", ""),
        os.getenv("GEMINI_API_KEY_2", ""),
        os.getenv("GEMINI_API_KEY_3", ""),
    ]
    if key
]

# Кількість чанків для RAG-контексту
TOP_K = 5

# Максимальна кількість повторних спроб при 429 (per-minute quota)
MAX_RETRIES = 2


# ---------------------------------------------------------------------------
# Генерація відповіді
# ---------------------------------------------------------------------------

async def generate_response(user_text: str) -> str:
    """Повний RAG-пайплайн: пошук → промпт → LLM → відповідь.

    Стратегія при помилках:
    - 429 per-minute: чекає retryDelay із відповіді і повторює (до MAX_RETRIES разів).
    - 429 per-day / limit=0: переходить до наступної моделі.
    - Інша помилка: переходить до наступного API-ключа.

    Args:
        user_text: текст повідомлення від користувача.

    Returns:
        Текст відповіді від моделі.

    Raises:
        RuntimeError: якщо всі комбінації ключ × модель вичерпані.
    """
    # 1. Знаходимо релевантні чанки з БД
    chunks = await asyncio.to_thread(search_chunks, user_text, TOP_K)
    print(f"[agent] Found {len(chunks)} chunks for query: {user_text!r}")

    # 2. Будуємо системний промпт із контекстом
    system_prompt = build_system_prompt(chunks)

    # 3. Перебираємо комбінації ключ × модель
    last_error: Exception | None = None

    for api_key in GEMINI_API_KEYS:
        for model in GENERATION_MODELS:
            for attempt in range(1, MAX_RETRIES + 2):  # спроби: 1, 2, 3
                try:
                    response = await asyncio.to_thread(
                        _call_gemini,
                        api_key=api_key,
                        model=model,
                        system_prompt=system_prompt,
                        user_text=user_text,
                    )
                    print(f"[agent] Success: key=...{api_key[-6:]}, model={model}")
                    return response

                except Exception as e:
                    error_str = str(e)
                    last_error = e

                    is_429 = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str

                    if not is_429:
                        # Не квота — одразу переходимо до наступного ключа
                        print(f"[agent] Non-quota error on model={model}: {e}")
                        break

                    # Перевіряємо чи це per-day / limit=0 → не ретраємо
                    is_per_day = (
                        "GenerateRequestsPerDay" in error_str
                        or '"limit": 0' in error_str
                        or "limit: 0" in error_str
                    )

                    if is_per_day:
                        print(f"[agent] Per-day quota exhausted, model={model} → next model")
                        break  # до наступної моделі

                    # per-minute quota — чекаємо і повторюємо
                    if attempt <= MAX_RETRIES:
                        delay = _parse_retry_delay(error_str) or (attempt * 15)
                        print(f"[agent] Per-minute 429, model={model}, retry in {delay}s (attempt {attempt})")
                        await asyncio.sleep(delay)
                    else:
                        print(f"[agent] Retries exhausted for model={model} → next model")

    raise RuntimeError(
        f"Усі Gemini API-ключі та моделі недоступні. "
        f"Остання помилка: {last_error}"
    )


def _parse_retry_delay(error_str: str) -> float | None:
    """Витягує retryDelay із тексту помилки Gemini (формат: 'N.NNs' або 'Ns')."""
    match = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+\.?\d*)\s*s", error_str)
    if match:
        return float(match.group(1)) + 1.0  # +1с буфер
    return None


def _call_gemini(api_key: str, model: str, system_prompt: str, user_text: str) -> str:
    """Синхронний виклик Gemini API (запускається через asyncio.to_thread).

    Args:
        api_key:       Gemini API ключ.
        model:         назва моделі Gemini.
        system_prompt: системний промпт із RAG-контекстом.
        user_text:     повідомлення користувача.

    Returns:
        Текст відповіді моделі.
    """
    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=model,
        contents=user_text,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.3,
            max_output_tokens=1024,
        ),
    )

    return response.text

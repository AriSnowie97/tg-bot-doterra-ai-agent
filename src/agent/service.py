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
import asyncio
# Special
from google.genai import types
# Local
from .prompt import build_system_prompt
from ..storage import search_chunks
from src.LLMProvider import GeminiFlashProvider as LLM


# ---------------------------------------------------------------------------
# Конфігурація
# ---------------------------------------------------------------------------
# Кількість чанків для RAG-контексту
TOP_K = 5

# Максимальна кількість повторних спроб при 429/503
MAX_RETRIES = 2


# ---------------------------------------------------------------------------
# Генерація відповіді
# ---------------------------------------------------------------------------

async def generate_response(user_text: str) -> str:
    """Повний RAG-пайплайн: пошук → промпт → LLM → відповідь.

    Стратегія при помилках:
    - 429 per-minute: чекає retryDelay із відповіді і повторює.
    - 429 per-day / limit=0: пропускає до наступної моделі.
    - 503 UNAVAILABLE: чекає і повторює (тимчасове перевантаження).
    - 404 NOT_FOUND: пропускає модель одразу.
    - Інша помилка: пропускає до наступного API-ключа.
    """
    # 1. Знаходимо релевантні чанки з БД
    chunks = await asyncio.to_thread(search_chunks, user_text, TOP_K)
    print(f"[agent] Found {len(chunks)} chunks for query: {user_text!r}")

    # 2. Будуємо системний промпт із контекстом
    system_prompt = build_system_prompt(chunks)

    # 3. Перебираємо комбінації ключ × модель
    response = await LLM().generate_content(user_text,
                                           types.GenerateContentConfig(
                                               system_instruction=system_prompt,
                                               temperature=0.3,
                                               max_output_tokens=2048
                                           ),
                                           MAX_RETRIES)

    text = (response.text or "").strip()
    if not text:
        raise RuntimeError(f"[agent] LLM повернув порожній текст. finish_reason={getattr(response.candidates[0], 'finish_reason', 'unknown') if response.candidates else 'unknown'}")

    print(f"[agent] Response len={len(text)} chars")
    return text
"""
Сервіс генерації відповідей AI-агента.

Пайплайн:
    1. Пошук релевантних чанків у pgvector (RAG)
    2. Формування системного промпту з контекстом
    3. Виклик Gemini для генерації відповіді
    4. Повернення тексту відповіді

Використання:
    from src.agent import generate_response

    answer = await generate_response("Що таке лаванда?")
"""

# Standard
import os
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

GENERATION_MODEL = "gemini-2.0-flash"

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


# ---------------------------------------------------------------------------
# Генерація відповіді
# ---------------------------------------------------------------------------

async def generate_response(user_text: str) -> str:
    """Повний RAG-пайплайн: пошук → промпт → LLM → відповідь.

    Args:
        user_text: текст повідомлення від користувача.

    Returns:
        Текст відповіді від моделі.

    Raises:
        RuntimeError: якщо всі Gemini API-ключі недоступні.
    """
    # 1. Знаходимо релевантні чанки з БД
    chunks = await asyncio.to_thread(search_chunks, user_text, TOP_K)

    print(f"[agent] Found {len(chunks)} chunks for query: {user_text!r}")

    # 2. Будуємо системний промпт із контекстом
    system_prompt = build_system_prompt(chunks)

    # 3. Генеруємо відповідь через Gemini (fallback по ключах)
    last_error: Exception | None = None

    for api_key in GEMINI_API_KEYS:
        try:
            response = await asyncio.to_thread(
                _call_gemini,
                api_key=api_key,
                system_prompt=system_prompt,
                user_text=user_text,
            )
            return response

        except Exception as e:
            print(f"[agent] API key failed: {e}")
            last_error = e

    raise RuntimeError(f"Усі Gemini API-ключі недоступні. Остання помилка: {last_error}")


def _call_gemini(api_key: str, system_prompt: str, user_text: str) -> str:
    """Синхронний виклик Gemini API (запускається через asyncio.to_thread).

    Args:
        api_key:       Gemini API ключ.
        system_prompt: системний промпт із RAG-контекстом.
        user_text:     повідомлення користувача.

    Returns:
        Текст відповіді моделі.
    """
    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=GENERATION_MODEL,
        contents=user_text,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.3,   # менше "фантазій", більше точності
            max_output_tokens=1024,
        ),
    )

    return response.text

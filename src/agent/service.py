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
# Актуально на серпень 2026.
GENERATION_MODELS: list[str] = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
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
                    print(f"[agent] ✅ Success: key=...{api_key[-6:]}, model={model}")

                    # Перевіряємо завершеність відповіді
                    if not _is_complete(response):
                        print(f"[agent] ⚠️ Response incomplete, requesting completion...")
                        response = await asyncio.to_thread(
                            _complete_response,
                            api_key=api_key,
                            model=model,
                            system_prompt=system_prompt,
                            user_text=user_text,
                            partial_response=response,
                        )
                        print(f"[agent] ✅ Completion done")

                    return response

                except Exception as e:
                    error_str = str(e)
                    last_error = e

                    is_404 = "404" in error_str or "NOT_FOUND" in error_str
                    is_429 = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str
                    is_503 = "503" in error_str or "UNAVAILABLE" in error_str

                    # 404 — модель застаріла або не існує, пропускаємо одразу
                    if is_404:
                        print(f"[agent] 404 model not found, skip: {model}")
                        break

                    # 503 — тимчасове перевантаження, чекаємо і повторюємо
                    if is_503:
                        if attempt <= MAX_RETRIES:
                            delay = attempt * 10
                            print(f"[agent] 503 on model={model}, retry in {delay}s (attempt {attempt})")
                            await asyncio.sleep(delay)
                            continue
                        print(f"[agent] 503 retries exhausted for model={model} → next model")
                        break

                    # 429 — розрізняємо per-day і per-minute
                    if is_429:
                        is_per_day = (
                            "GenerateRequestsPerDay" in error_str
                            or '"limit": 0' in error_str
                            or "limit: 0" in error_str
                        )
                        if is_per_day:
                            print(f"[agent] Per-day quota exhausted, model={model} → next model")
                            break

                        # per-minute — чекаємо retryDelay і повторюємо
                        if attempt <= MAX_RETRIES:
                            delay = _parse_retry_delay(error_str) or (attempt * 15)
                            print(f"[agent] Per-minute 429, model={model}, retry in {delay}s (attempt {attempt})")
                            await asyncio.sleep(delay)
                            continue
                        print(f"[agent] Retries exhausted for model={model} → next model")
                        break

                    # Невідома помилка — наступний ключ
                    print(f"[agent] Unknown error on model={model}: {e}")
                    break

    raise RuntimeError(
        f"Усі Gemini API-ключі та моделі недоступні. "
        f"Остання помилка: {last_error}"
    )


def _parse_retry_delay(error_str: str) -> float | None:
    """Витягує retryDelay із тексту помилки Gemini (формат: 'N.NNs' або 'Ns')."""
    match = re.search(r"retryDelay['\"\]?\s*[:=]\s*['\"]?(\d+\.?\d*)\s*s", error_str)
    if match:
        return float(match.group(1)) + 1.0  # +1с буфер
    return None


# ---------------------------------------------------------------------------
# Контролер завершеності відповіді
# ---------------------------------------------------------------------------

# Символи та емодзі, якими має закінчуватись повна відповідь
_COMPLETE_ENDINGS: tuple[str, ...] = (
    ".", "!", "?",
    "💛", "🌿", "✨", "🌸", "💧", "💚", "🍃", "🌱", "🌼", "🌻", "🪴", "🫧", "🫂",
    "😊", "🙌", "👌", "☀️", "🌞",
)

# Символи, які однозначно вказують на обрив посеред речення
_INCOMPLETE_ENDINGS: tuple[str, ...] = (",", ":", "—", "-", "і", "та", "або", "що", "як")


def _is_complete(text: str) -> bool:
    """Перевіряє, чи є відповідь завершеною.

    Відповідь вважається незавершеною, якщо:
    - закінчується на кому, двокрапку або тире (обрив)
    - не закінчується жодним із відомих завершальних символів
    """
    stripped = text.strip()
    if not stripped:
        return False

    # Явна ознака обриву — закінчується на "небезпечний" символ
    for bad in _INCOMPLETE_ENDINGS:
        if stripped.endswith(bad):
            print(f"[completion] ❌ Ends with incomplete marker: '{bad}'")
            return False

    # Перевіряємо чи є завершальний символ
    for ending in _COMPLETE_ENDINGS:
        if stripped.endswith(ending):
            return True

    # Якщо закінчується на ] (chunk_id мітка) — вважаємо незавершеним,
    # бо після джерела має бути ще closing phrase
    if stripped.endswith("]"):
        print("[completion] ⚠️ Ends with chunk_id — missing closing phrase")
        return False

    print(f"[completion] ⚠️ Unknown ending, treating as incomplete")
    return False


def _complete_response(
    api_key: str,
    model: str,
    system_prompt: str,
    user_text: str,
    partial_response: str,
) -> str:
    """Надсилає повторний запит щоб дописати незавершену відповідь.

    Формує контекст із часткової відповіді та просить модель завершити її,
    зберігаючи тон і стиль.

    Args:
        api_key:          Gemini API ключ.
        model:            назва моделі Gemini.
        system_prompt:    системний промпт із RAG-контекстом.
        user_text:        оригінальне повідомлення користувача.
        partial_response: незавершена відповідь яку треба дописати.

    Returns:
        Повна відповідь (partial_response + дописана частина).
    """
    client = genai.Client(api_key=api_key)

    completion_prompt = (
        f"Запит користувача: {user_text}\n\n"
        f"Ти вже почав відповідати, але відповідь обірвалась. "
        f"Ось незавершена відповідь:\n\n{partial_response}\n\n"
        "Продовж і ДОВЕРШИ цю відповідь з того місця де вона обірвалась. "
        "Не повторюй те що вже написано — лише допиши решту. "
        "Обов'язково завершити закінчувальною теплою фразою з 💛 або 🌿. "
        "Якщо потрібен дисклеймер — додай його в кінці."
    )

    response = client.models.generate_content(
        model=model,
        contents=completion_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
            max_output_tokens=512,
        ),
    )

    if response.text is None:
        # Якщо дописати не вдалось — повертаємо оригінал із мінімальним закінченням
        print("[completion] ❌ Completion call returned None, using fallback")
        return partial_response.rstrip(",:-— ") + " 💛"

    completed = partial_response.rstrip() + "\n" + response.text.strip()
    return completed


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
            max_output_tokens=600,
        ),
    )

    if response.text is None:
        candidates = response.candidates or []
        finish_reason = candidates[0].finish_reason if candidates else "unknown"
        raise ValueError(f"response.text=None, finish_reason={finish_reason}, model={model}")

    return response.text

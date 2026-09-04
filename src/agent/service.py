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
from .specialist import (
    is_consultation_query,
    is_low_context,
    is_health_complaint_query,
    has_red_flags,
    MEDICAL_DISCLAIMER,
)
from ..storage import search_chunks
from src.LLMProvider import GeminiFlashProvider as LLM


# ---------------------------------------------------------------------------
# Конфігурація
# ---------------------------------------------------------------------------
# Кількість чанків для RAG-контексту
TOP_K = 5

# Максимальна кількість повторних спроб при 429/503
MAX_RETRIES = 2

# Фолбек-відповідь при повністю порожній базі знань (0 чанків)
# LLM не викликається взагалі — повертається ця статична відповідь
EMPTY_CONTEXT_FALLBACK: str = (
    "🌿 На жаль, я не знайшов інформації з цього запиту в базі знань.\n\n"
    "Спробуй переформулювати запит або запитати про конкретний продукт чи олію — "
    "я пошукаю тільки в нашій базі doTERRA.\n\n"
    "📸 Якщо питання складніше або потребуєш індивідуальної поради щодо олій — "
    "звернись до Наталії Котелянської: https://www.instagram.com/nkotelianska/ 💛\n\n"
    "🩺 З питань здоров'я, симптомів або лікування — обов'язково проконсультуйся з лікарем."
)


# ---------------------------------------------------------------------------
# Генерація відповіді
# ---------------------------------------------------------------------------

async def generate_response(
    user_text: str,
    screening_mode: str | None = None,
    conversation_context: str | None = None,
) -> str:
    """Повний RAG-пайплайн: пошук → промпт → LLM → відповідь.

    Args:
        user_text:            Поточне повідомлення користувача.
        screening_mode:       Режим скринінгу з FSMContext ('inactive'|'active'|'red_flag').
                              Якщо None — визначається автоматично за текстом.
        conversation_context: Накопичений текст розмови (скарга + відповіді на скринінг).
                              Використовується для RAG-пошуку та як вхід для LLM.

    Стратегія при помилках:
    - 429 per-minute: чекає retryDelay із відповіді і повторює.
    - 429 per-day / limit=0: пропускає до наступної моделі.
    - 503 UNAVAILABLE: чекає і повторює (тимчасове перевантаження).
    - 404 NOT_FOUND: пропускає модель одразу.
    - Інша помилка: пропускає до наступного API-ключа.
    """
    # Для RAG-пошуку використовуємо накопичений контекст діалогу якщо є
    rag_query = conversation_context or user_text

    # 1. Знаходимо релевантні чанки з БД
    chunks = await asyncio.to_thread(search_chunks, rag_query, TOP_K)
    print(f"[agent] Found {len(chunks)} chunks for query: {rag_query[:80]!r}")

    # 2. Жорсткий фолбек: база повністю порожня — повертаємо статичну відповідь без виклику LLM
    if not chunks:
        print(f"[agent] 0 chunks found — returning EMPTY_CONTEXT_FALLBACK")
        return EMPTY_CONTEXT_FALLBACK

    # 3. Визначаємо режим скринінгу
    low_ctx = is_low_context(chunks)
    consult_req = is_consultation_query(user_text)

    if screening_mode is not None:
        # Режим переданий з FSMContext — довіряємо йому (скринінг між повідомленнями)
        final_mode = screening_mode
        # Перевіряємо чи в новому повідомленні з'явились червоні прапори
        if final_mode == "active" and has_red_flags(user_text):
            final_mode = "red_flag"
        suggest_specialist = final_mode in ("active", "red_flag") or low_ctx or consult_req
    else:
        # Перше повідомлення — визначаємо автоматично
        health_complaint = is_health_complaint_query(user_text)
        red_flag = has_red_flags(user_text)
        if health_complaint and red_flag:
            final_mode = "red_flag"
            suggest_specialist = True
        elif health_complaint:
            final_mode = "active"
            suggest_specialist = low_ctx or consult_req
        else:
            final_mode = "inactive"
            suggest_specialist = low_ctx or consult_req

    print(f"[agent] screening_mode={final_mode!r} suggest_specialist={suggest_specialist}")

    # 4. Будуємо системний промпт із контекстом + режимом скринінгу
    system_prompt = build_system_prompt(
        chunks,
        suggest_specialist=suggest_specialist,
        screening_mode=final_mode,
    )

    # 5. Текст для LLM: якщо є накопичений контекст діалогу — передаємо його
    llm_input = conversation_context if conversation_context else user_text

    # 6. Виклик LLM
    response = await LLM().generate_content(
        llm_input,
        types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.3,
            max_output_tokens=4096,
        ),
        MAX_RETRIES,
    )

    text = (response.text or "").strip()
    if not text:
        raise RuntimeError(f"[agent] LLM повернув порожній текст. finish_reason={getattr(response.candidates[0], 'finish_reason', 'unknown') if response.candidates else 'unknown'}")

    # Виявлення витоку промпту: якщо модель вивела інструкції замість відповіді
    leakage_markers = [
        "(no `**`",
        "- List uses emojis",
        "- Warm opening",
        "- Disclaimer present",
        "- Ends with support",
        "- Context only",
        "КРИТИЧНО —",
        "RETRIEVED_CONTEXT",
    ]
    if any(marker in text for marker in leakage_markers):
        raise RuntimeError(f"[agent] Виявлено витік промпту у відповіді моделі — пропускаємо")

    # Додаємо дисклеймер хардкодом (гарантовано, незалежно від LLM)
    # Якщо LLM вже додав схожий текст — уникаємо дублювання
    disclaimer_core = "не є медичною консультацією"
    if disclaimer_core not in text.lower():
        text = text + MEDICAL_DISCLAIMER

    print(f"[agent] Response len={len(text)} chars")
    return text
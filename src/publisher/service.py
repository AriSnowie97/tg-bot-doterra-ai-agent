"""
Сервіс генерації та публікації постів у Telegram-канал.

Пайплайн:
    1. Рандомно обирає тему з TOPIC_SEEDS
    2. Шукає релевантні чанки у pgvector (RAG, TOP_K=12)
    3. Генерує пост через Gemini (з POST_SYSTEM_PROMPT)
    4. Публікує через Bot API: bot.send_message(CHANNEL_ID, text)

Використання:
    from src.publisher import publish_channel_post

    await publish_channel_post(bot)
"""

# Standard
import os
import random
import asyncio
# Special
from aiogram import Bot
# Local
from ..agent.post_prompt import build_post_prompt, TOPIC_SEEDS
from ..agent.service import _call_gemini, GEMINI_API_KEYS, GENERATION_MODELS, MAX_RETRIES, _parse_retry_delay
from ..storage import search_chunks


# ---------------------------------------------------------------------------
# Конфігурація
# ---------------------------------------------------------------------------

CHANNEL_ID: str = os.getenv("CHANNEL_ID", "")

# Більший контекст для посту (vs 5 для чат-бота)
POST_TOP_K: int = 12

# Температура для постів — трохи вище, щоб текст був живішим
POST_TEMPERATURE: float = 0.7

# Максимальна довжина посту (символів) — лімітуємо для Telegram (max 4096)
MAX_POST_LENGTH: int = 3800


# ---------------------------------------------------------------------------
# Генерація тексту посту
# ---------------------------------------------------------------------------

async def _generate_post_text(topic_query: str) -> str:
    """RAG-пайплайн для генерації посту: пошук чанків → промпт → Gemini.

    Args:
        topic_query: seed-запит для пошуку релевантних чанків.

    Returns:
        Текст згенерованого посту.

    Raises:
        RuntimeError: якщо всі Gemini API-ключі та моделі недоступні.
    """
    # 1. Знаходимо релевантні чанки
    chunks = await asyncio.to_thread(search_chunks, topic_query, POST_TOP_K)
    print(f"[publisher] Found {len(chunks)} chunks for topic: {topic_query!r}")

    # 2. Будуємо системний промпт для посту
    system_prompt = build_post_prompt(chunks)

    # 3. Запит до Gemini — той самий механізм retry/fallback що в agent/service.py
    user_instruction = (
        f"Напиши розгорнутий пост для Telegram-каналу на тему: «{topic_query}». "
        "Використай всі надані факти з бази знань, додай структуру, емодзі та заклик до дії в кінці."
    )

    last_error: Exception | None = None

    for api_key in GEMINI_API_KEYS:
        for model in GENERATION_MODELS:
            for attempt in range(1, MAX_RETRIES + 2):
                try:
                    text = await asyncio.to_thread(
                        _call_gemini,
                        api_key=api_key,
                        model=model,
                        system_prompt=system_prompt,
                        user_text=user_instruction,
                    )
                    print(f"[publisher] ✅ Generated post: key=...{api_key[-6:]}, model={model}, len={len(text)}")
                    return text

                except Exception as e:
                    error_str = str(e)
                    last_error = e

                    is_404 = "404" in error_str or "NOT_FOUND" in error_str
                    is_429 = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str
                    is_503 = "503" in error_str or "UNAVAILABLE" in error_str

                    if is_404:
                        print(f"[publisher] 404 model not found, skip: {model}")
                        break

                    if is_503:
                        if attempt <= MAX_RETRIES:
                            delay = attempt * 10
                            print(f"[publisher] 503 retry in {delay}s (attempt {attempt})")
                            await asyncio.sleep(delay)
                            continue
                        break

                    if is_429:
                        is_per_day = (
                            "GenerateRequestsPerDay" in error_str
                            or '"limit": 0' in error_str
                        )
                        if is_per_day:
                            print(f"[publisher] Per-day quota, skip model={model}")
                            break
                        if attempt <= MAX_RETRIES:
                            delay = _parse_retry_delay(error_str) or (attempt * 15)
                            print(f"[publisher] Per-minute 429, retry in {delay}s (attempt {attempt})")
                            await asyncio.sleep(delay)
                            continue
                        break

                    print(f"[publisher] Unknown error on model={model}: {e}")
                    break

    raise RuntimeError(
        f"[publisher] Всі Gemini API-ключі та моделі недоступні. "
        f"Остання помилка: {last_error}"
    )


# ---------------------------------------------------------------------------
# Публікація посту у канал
# ---------------------------------------------------------------------------

def _truncate_post(text: str, max_len: int = MAX_POST_LENGTH) -> str:
    """Обрізає пост до max_len символів по межі абзацу, зберігаючи цілісність."""
    if len(text) <= max_len:
        return text
    # Знаходимо останній повний абзац в межах ліміту
    truncated = text[:max_len]
    last_newline = truncated.rfind("\n\n")
    if last_newline > max_len // 2:
        return truncated[:last_newline].rstrip()
    return truncated.rstrip()


async def publish_channel_post(bot: Bot) -> None:
    """Генерує та публікує один пост у Telegram-канал.

    Алгоритм:
    1. Перевіряє наявність CHANNEL_ID.
    2. Рандомно обирає тему з TOPIC_SEEDS.
    3. Генерує текст посту через RAG + Gemini.
    4. Публікує через bot.send_message.

    Args:
        bot: Aiogram Bot instance.

    Logs:
        Усі кроки логуються через print для Railway/Docker logs.
    """
    if not CHANNEL_ID:
        print("[publisher] ⚠️  CHANNEL_ID не задано — публікацію скасовано.")
        return

    # Обираємо рандомну тему
    topic = random.choice(TOPIC_SEEDS)
    print(f"[publisher] 🎯 Selected topic: {topic!r}")

    try:
        # Генеруємо текст
        post_text = await _generate_post_text(topic)
        post_text = _truncate_post(post_text)

        # Публікуємо у канал
        # parse_mode=None — бо промпт вже забороняє markdown-символи
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=post_text,
            parse_mode=None,
        )
        print(f"[publisher] ✅ Post published to {CHANNEL_ID!r} ({len(post_text)} chars)")

    except Exception as e:
        # Не падаємо — просто логуємо помилку та продовжуємо роботу бота
        print(f"[publisher] ❌ Failed to publish post: {e}")

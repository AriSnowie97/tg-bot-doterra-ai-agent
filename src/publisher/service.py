"""
Сервіс генерації та публікації постів у Telegram-канал.

Пайплайн:
    1. Рандомно обирає тему з TOPIC_SEEDS
    2. Шукає релевантні чанки у pgvector (RAG, TOP_K=12)
    3. Генерує пост через GeminiFlashProvider (LLMProvider)
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
from google.genai import types
# Local
from ..agent.post_prompt import build_post_prompt, TOPIC_SEEDS
from ..storage import search_chunks
from src.LLMProvider import GeminiFlashProvider as LLM


# ---------------------------------------------------------------------------
# Конфігурація
# ---------------------------------------------------------------------------

CHANNEL_ID: str = os.getenv("CHANNEL_ID", "")

# Більший контекст для посту (vs 5 для чат-бота)
POST_TOP_K: int = 12

# Максимальна кількість повторних спроб
MAX_RETRIES: int = 2

# Максимальна довжина посту (символів) — лімітуємо для Telegram (max 4096)
MAX_POST_LENGTH: int = 3800


# ---------------------------------------------------------------------------
# Генерація тексту посту
# ---------------------------------------------------------------------------

async def _generate_post_text(topic_query: str) -> str:
    """RAG-пайплайн для генерації посту: пошук чанків → промпт → LLM.

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

    # 3. Запит до LLM через GeminiFlashProvider (той самий механізм retry/fallback)
    user_instruction = (
        f"Напиши розгорнутий пост для Telegram-каналу на тему: «{topic_query}». "
        "Використай всі надані факти з бази знань, додай структуру, емодзі та заклик до дії в кінці."
    )

    response = await LLM().generate_content(
        user_instruction,
        types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.7,
            max_output_tokens=2048,
        ),
        MAX_RETRIES,
    )

    print(f"[publisher] ✅ Post generated, len={len(response.text)}")
    return response.text


# ---------------------------------------------------------------------------
# Публікація посту у канал
# ---------------------------------------------------------------------------

def _truncate_post(text: str, max_len: int = MAX_POST_LENGTH) -> str:
    """Обрізає пост до max_len символів по межі абзацу, зберігаючи цілісність."""
    if len(text) <= max_len:
        return text
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
    3. Генерує текст посту через RAG + GeminiFlashProvider.
    4. Публікує через bot.send_message.

    Args:
        bot: Aiogram Bot instance.
    """
    if not CHANNEL_ID:
        print("[publisher] ⚠️  CHANNEL_ID не задано — публікацію скасовано.")
        return

    # Обираємо рандомну тему
    topic = random.choice(TOPIC_SEEDS)
    print(f"[publisher] 🎯 Selected topic: {topic!r}")

    try:
        post_text = await _generate_post_text(topic)
        post_text = _truncate_post(post_text)

        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=post_text,
            parse_mode=None,
        )
        print(f"[publisher] ✅ Post published to {CHANNEL_ID!r} ({len(post_text)} chars)")

    except Exception as e:
        print(f"[publisher] ❌ Failed to publish post: {e}")

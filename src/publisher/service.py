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
import re
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

# Маркери «вигаданих досліджень» — слова, що сигналізують про наукові твердження
_RESEARCH_MARKERS: tuple[str, ...] = (
    "дослідження", "дослідженн", "вчені", "вчених", "науковці",
    "науково доведено", "науково підтверджено", "клінічн",
    "study", "studies", "scientists", "researchers", "research",
    "журнал", "публікац", "експеримент",
)

# Редирект-фраза, що замінює вигадані дослідження
_REDIRECT_PHRASE: str = (
    "\n\n💬 Якщо тебе цікавить більше деталей або індивідуальні рекомендації — "
    "зверніться до Наталії Котелянської або свого лікаря. "
    "Вони допоможуть підібрати саме те, що підійде саме тобі 🌿"
)


# ---------------------------------------------------------------------------
# Детектор вигаданих досліджень
# ---------------------------------------------------------------------------

def _has_research_in_chunks(chunks: list[dict]) -> bool:
    """Повертає True, якщо хоча б один RAG-чанк містить реальні дані про дослідження."""
    joined = " ".join(c.get("content", "") for c in chunks).lower()
    return any(marker in joined for marker in _RESEARCH_MARKERS)


def _has_research_in_text(text: str) -> bool:
    """Повертає True, якщо у тексті є маркери досліджень."""
    lower = text.lower()
    return any(marker in lower for marker in _RESEARCH_MARKERS)


def _sanitize_research_claims(text: str) -> str:
    """Видаляє речення, що містять вигадані маркери досліджень.

    Замінює їх редирект-фразою до Наталії Котелянської / лікаря.
    Зберігає решту посту повністю.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text)
    clean = []
    removed_count = 0
    for sentence in sentences:
        if any(marker in sentence.lower() for marker in _RESEARCH_MARKERS):
            removed_count += 1
        else:
            clean.append(sentence)

    result = " ".join(clean).strip()
    if removed_count > 0:
        result += _REDIRECT_PHRASE
        print(f"[publisher] ⚠️  Sanitized {removed_count} sentence(s) with fabricated research claims.")
    return result


# ---------------------------------------------------------------------------
# Генерація тексту посту
# ---------------------------------------------------------------------------

async def _generate_post_text(topic_query: str) -> str:
    """RAG-пайплайн для генерації посту: пошук чанків → промпт → LLM.

    Включає захист від вигаданих досліджень:
    1. Перевіряє, чи RAG-чанки містять реальні наукові дані.
    2. Якщо LLM усе одно додала маркери досліджень без бази — робить retry.
    3. Якщо після retry проблема залишилась — санітизує текст і додає
       редирект до Наталії Котелянської / лікаря.

    Args:
        topic_query: seed-запит для пошуку релевантних чанків.

    Returns:
        Текст згенерованого посту (чистий або санітизований).

    Raises:
        RuntimeError: якщо всі Gemini API-ключі та моделі недоступні.
    """
    # 1. Знаходимо релевантні чанки
    chunks = await asyncio.to_thread(search_chunks, topic_query, POST_TOP_K)
    print(f"[publisher] Found {len(chunks)} chunks for topic: {topic_query!r}")

    chunks_have_research = _has_research_in_chunks(chunks)
    print(f"[publisher] RAG chunks contain research data: {chunks_have_research}")

    # 2. Будуємо системний промпт для посту
    system_prompt = build_post_prompt(chunks)

    # 3. Запит до LLM (з можливим retry, якщо виявлено вигадані дослідження)
    for attempt in range(1, MAX_RETRIES + 2):  # +1 перший запит + MAX_RETRIES повторів
        user_instruction = (
            f"Напиши розгорнутий пост для Telegram-каналу на тему: «{topic_query}». "
            "Використай всі надані факти з бази знань, додай структуру, емодзі та заклик до дії в кінці."
        )
        if attempt > 1:
            # Посилюємо інструкцію при retry
            user_instruction += (
                " ВАЖЛИВО: у базі знань немає наукових досліджень з цієї теми — "
                "жодних слів 'дослідження', 'вчені', 'науково', 'доведено'. "
                "Якщо потрібні поради — скеруй читача до Наталії Котелянської або лікаря."
            )

        response = await LLM().generate_content(
            user_instruction,
            types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,
                max_output_tokens=8192,
            ),
            MAX_RETRIES,
        )

        post_text = (response.text or "").strip()

        # 4. Перевірка: чи LLM додала маркери досліджень без бази?
        if not chunks_have_research and _has_research_in_text(post_text):
            if attempt <= MAX_RETRIES:
                print(
                    f"[publisher] ⚠️  Attempt {attempt}: fabricated research detected, retrying..."
                )
                continue
            else:
                # Всі спроби вичерпано — санітизуємо текст і публікуємо з redirect
                print(
                    f"[publisher] ⚠️  All {MAX_RETRIES + 1} attempts had fabricated research. "
                    "Sanitizing post before publishing."
                )
                post_text = _sanitize_research_claims(post_text)

        print(f"[publisher] ✅ Post generated, len={len(post_text)}")
        return post_text

    # Fallback (не повинен досягатися)
    return post_text


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

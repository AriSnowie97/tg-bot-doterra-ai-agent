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
import sys
import html
from typing import Any
from dotenv import load_dotenv

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
# Special
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from google.genai import types
# Local
from ..agent.post_prompt import build_post_prompt, TOPIC_SEEDS
from ..agent.specialist import (
    MEDICAL_DISCLAIMER,
    EN_MEDICAL_DISCLAIMER,
    SPECIALIST_LINKS,
)
from ..storage import search_chunks
from src.LLMProvider import GeminiFlashProvider as LLM
from src.safety import redact

load_dotenv()


# ---------------------------------------------------------------------------
# Конфігурація
# ---------------------------------------------------------------------------

def get_channel_id() -> str:
    """Отримує актуальний CHANNEL_ID із змінних середовища."""
    return os.getenv("CHANNEL_ID", "").strip()


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


# Валідні завершальні знаки та емодзі для кінця посту
_VALID_POST_ENDINGS: tuple[str, ...] = (
    ".", "!", "?", "…",
    "❤️", "🔥", "🌿", "💧", "✨", "💛", "👇", "🌸", "🌱", "🙏", "😊", "👍"
)

# Слова, що сигналізують про обірване на півслові речення
_DANGLING_END_WORDS: tuple[str, ...] = (
    "та", "і", "й", "з", "із", "зі", "в", "у", "на", "о", "до", "від",
    "для", "як", "що", "або", "чи", "не", "ні", "через", "при", "під",
    "над", "без", "по", "про", "а", "але", "щоб", "якщо"
)


def _is_post_complete(text: str) -> tuple[bool, str]:
    """Перевіряє, чи пост є цілісним та повністю завершеним."""
    if not text or len(text.strip()) < 500:
        return False, "Текст занадто короткий (менше 500 символів)"

    trimmed = text.strip()

    # Перевірка на обірвані знаки пунктуації в самому кінці
    if trimmed[-1] in (",", ";", ":", "-", "—", "(", "[", "{", "/"):
        return False, f"Текст закінчується на незавершений знак '{trimmed[-1]}'"

    # Останнє слово не повинно бути прийменником/сполучником
    words = re.findall(r'[\w]+', trimmed)
    if words and words[-1].lower() in _DANGLING_END_WORDS:
        return False, f"Текст закінчується на незавершене слово '{words[-1]}'"

    # Перевірка кінцевого символу (знак пунктуації або емодзі)
    if not any(trimmed.endswith(ending) for ending in _VALID_POST_ENDINGS):
        return False, "Останнє речення не завершене (немає крапки, знака оклику/питання або емодзі)"

    # Перевірка наявності інтерактивного заклику / завершення в останньому абзаці
    last_block = trimmed.split("\n\n")[-1].lower()
    has_cta = any(w in last_block for w in ("?", "коментар", "діліться", "ставте", "❤️", "🔥", "рутині", "напишіть"))
    if not has_cta and len(trimmed) > 1200:
        return False, "У фіналі відсутній заклик до дії або запитання до підписників"

    return True, "OK"


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

        # 5. Перевірка: чи пост повністю завершений?
        is_complete, reason = _is_post_complete(post_text)
        if not is_complete:
            if attempt <= MAX_RETRIES:
                print(f"[publisher] ⚠️  Attempt {attempt}: post is incomplete ({reason}), retrying...")
                user_instruction += (
                    f" ВАЖЛИВО: Твій попередній пост був незавершеним ({reason})! "
                    "Напиши повністю ЗАВЕРШЕНИЙ пост обсягом 1800-2400 символів, який обов'язково закінчується запитанням або закликом до реакції (❤️/🔥)."
                )
                continue
            else:
                print(f"[publisher] ⚠️  Post incomplete after retries ({reason}). Cleaning up.")
                post_text = _ensure_clean_post(post_text)

        print(f"[publisher] ✅ Post generated, len={len(post_text)}")
        return post_text

    # Fallback (не повинен досягатися)
    return _ensure_clean_post(post_text)


# ---------------------------------------------------------------------------
# Публікація посту у канал
# ---------------------------------------------------------------------------

def _strip_disclaimer(text: str) -> str:
    """Видаляє медичний дисклеймер із тексту посту, якщо він там з'явився."""
    if not text:
        return ""

    for d in (MEDICAL_DISCLAIMER, EN_MEDICAL_DISCLAIMER):
        if d in text:
            text = text.replace(d, "")

    lines = text.split("\n")
    cleaned_lines: list[str] = []
    for line in lines:
        l_lower = line.lower().strip()
        if not l_lower:
            cleaned_lines.append(line)
            continue
        if "не є медичною консультацією" in l_lower or "medical consultation" in l_lower or "medical advice" in l_lower:
            continue
        if "перед застосуванням проконсультуйтеся з лікарем" in l_lower or "consult a healthcare professional" in l_lower or "consult a doctor" in l_lower:
            continue
        if l_lower.startswith("ℹ️") and ("ознайомлювальний характер" in l_lower or "інформаційний характер" in l_lower):
            continue
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _build_post_url(channel_id: str | int, sent_msg: Any = None) -> str:
    """Будує пряме посилання на опублікований пост у Telegram-каналі."""
    msg_id = getattr(sent_msg, "message_id", None)
    chat = getattr(sent_msg, "chat", None)
    chat_username = getattr(chat, "username", None) if chat else None

    # 1. Якщо у чату є публічний username (наприклад nkotelianskablog)
    if chat_username:
        clean = chat_username.lstrip("@").strip()
        return f"https://t.me/{clean}/{msg_id}" if msg_id else f"https://t.me/{clean}"

    cid_str = str(channel_id).strip()

    # 2. Якщо channel_id містить повний URL на канал
    if cid_str.startswith("https://t.me/"):
        base = cid_str.rstrip("/")
        return f"{base}/{msg_id}" if msg_id else base

    # 3. Якщо channel_id починається з @ (публічний юзернейм)
    if cid_str.startswith("@"):
        clean_user = cid_str.lstrip("@")
        return f"https://t.me/{clean_user}/{msg_id}" if msg_id else f"https://t.me/{clean_user}"

    # 4. Якщо channel_id числовий ID (-100xxxx або xxxx)
    clean_id = cid_str
    if clean_id.startswith("-100"):
        clean_id = clean_id[4:]
    elif clean_id.startswith("-"):
        clean_id = clean_id[1:]

    if clean_id.isdigit():
        return f"https://t.me/c/{clean_id}/{msg_id}" if msg_id else f"https://t.me/c/{clean_id}"

    # 5. Якщо текстовий рядок без @ (наприклад 'nkotelianskablog')
    if re.match(r"^[a-zA-Z0-9_]{4,}$", cid_str):
        return f"https://t.me/{cid_str}/{msg_id}" if msg_id else f"https://t.me/{cid_str}"

    # 6. Fallback на канал спеціаліста
    fallback = SPECIALIST_LINKS.get("Telegram", "https://t.me/nkotelianskablog").rstrip("/")
    return f"{fallback}/{msg_id}" if msg_id else fallback


def _ensure_clean_post(text: str, max_len: int = MAX_POST_LENGTH) -> str:
    """Обрізає пост за потреби та гарантує відсутність обірваних речень і слів."""
    if not text:
        return ""

    text = _strip_disclaimer(text)
    if len(text) <= max_len:
        is_ok, _ = _is_post_complete(text)
        if is_ok:
            return _strip_disclaimer(text)

    # Якщо текст довший або обірваний — шукаємо останню безпечну межу
    truncated = text[:max_len]
    last_newline = truncated.rfind("\n\n")
    if last_newline > max_len // 2:
        candidate = truncated[:last_newline].rstrip()
    else:
        # Шукаємо кінець останнього речення
        sentence_ends = [m.end() for m in re.finditer(r'[.!?]\s+', truncated)]
        if sentence_ends:
            candidate = truncated[:sentence_ends[-1]].rstrip()
        else:
            candidate = truncated.rstrip()

    # Очищуємо висячі знаки
    while candidate and candidate[-1] in (",", ";", ":", "-", "—", "/", "(", "[", "{"):
        candidate = candidate[:-1].rstrip()

    # Очищуємо висяче останнє слово, якщо воно неповне
    words = re.findall(r'[\w]+', candidate)
    if words and words[-1].lower() in _DANGLING_END_WORDS:
        candidate = candidate[:candidate.rfind(words[-1])].rstrip()
        while candidate and candidate[-1] in (",", ";", ":", "-", "—", "/", "(", "[", "{"):
            candidate = candidate[:-1].rstrip()

    # Перевіряємо, чи є заклик до дії; якщо фінал обрізався — додаємо акуратний фінал
    last_block = candidate.split("\n\n")[-1].lower() if candidate else ""
    if not any(w in last_block for w in ("?", "коментар", "діліться", "ставте", "❤️", "🔥")):
        candidate += (
            "\n\nЧи використовуєте ви такі практики у своїй рутині? "
            "Поділіться у коментарях та ставте ❤️ або 🔥, якщо пост був корисним!"
        )

    return _strip_disclaimer(candidate)


async def publish_channel_post(bot: Bot) -> str | None:
    """Генерує та публікує один пост у Telegram-канал.

    Алгоритм:
    1. Перевіряє наявність CHANNEL_ID.
    2. Рандомно обирає тему з TOPIC_SEEDS.
    3. Генерує текст посту через RAG + GeminiFlashProvider.
    4. Гарантує повну завершеність посту без медичного дисклеймера.
    5. Публікує через bot.send_message.
    6. Сповіщає адміністраторів про успіх (із посиланням на пост) або помилку.

    Args:
        bot: Aiogram Bot instance.

    Returns:
        URL опублікованого посту в Telegram або None.

    Raises:
        ValueError: якщо CHANNEL_ID не задано.
        Exception: якщо виникла помилка генерації або відправки.
    """
    channel_id = get_channel_id()
    if not channel_id:
        print("[publisher] ⚠️ CHANNEL_ID не задано — публікацію скасовано.")
        raise ValueError("CHANNEL_ID environment variable is not set")

    # Обираємо рандомну тему
    topic = random.choice(TOPIC_SEEDS)
    print(f"[publisher] 🎯 Selected topic: {topic!r}")

    admin_ids_str = os.getenv("ADMIN_IDS", "")
    admin_ids = [
        int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()
    ]

    try:
        post_text = await _generate_post_text(topic)
        post_text = _ensure_clean_post(post_text)
        post_text = _strip_disclaimer(post_text)

        sent_msg = await bot.send_message(
            chat_id=channel_id,
            text=post_text,
            parse_mode=None,
        )
        print(f"[publisher] ✅ Post published to {channel_id!r} ({len(post_text)} chars)")

        post_url = _build_post_url(channel_id, sent_msg)

        # Сповіщаємо адмінів про успішну публікацію з посиланням на пост
        preview_text = html.escape(post_text[:300].rstrip())
        admin_text = (
            f"📢 <b>Опубліковано новий пост у канал!</b>\n\n"
            f"{preview_text}...\n\n"
            f"👉 <a href=\"{post_url}\">Читати далі</a>"
        )
        admin_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📖 Читати далі в каналі", url=post_url)]
            ]
        )

        for a_id in admin_ids:
            try:
                await bot.send_message(
                    chat_id=a_id,
                    text=admin_text,
                    parse_mode="HTML",
                    reply_markup=admin_kb,
                )
            except Exception:
                pass

        return post_url

    except Exception as e:
        print(f"[publisher] ❌ Failed to publish post: {redact(e)}")
        for a_id in admin_ids:
            try:
                await bot.send_message(
                    chat_id=a_id,
                    text=f"⚠️ <b>Помилка автопублікації посту в канал:</b>\n{redact(e)}",
                    parse_mode="HTML",
                )
            except Exception:
                pass
        raise

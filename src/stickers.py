"""
Модуль для роботи зі стікерпаком бота doTERRA (aromaaitgbot).

Керує завантаженням, кешуванням та логікою відправки стікерів на короткі питання,
привітання, подяки, реакції та стікери користувачів.

Посилання на стікерпак: https://t.me/addstickers/aromaaitgbot
"""

# Standard
import os
import random
import re
from typing import Optional, List, Dict
# Special
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.types import Sticker
# Local
from src.safety import redact

# Завантажуємо .env змінні
load_dotenv()

# ---------------------------------------------------------------------------
# Конфігурація
# ---------------------------------------------------------------------------

# Назва стікерпаку в Telegram
STICKER_SET_NAME: str = os.getenv("STICKER_SET_NAME", "aromaaitgbot").strip()

# Ймовірність відправки стікера при короткому питанні (0.0 - 1.0)
PROB_SHORT_QUESTION: float = float(os.getenv("STICKER_PROB_SHORT_QUESTION", "0.35"))

# Ймовірність відповіді стікером на привітання / подяку / реакцію (0.0 - 1.0)
PROB_CASUAL: float = float(os.getenv("STICKER_PROB_CASUAL", "0.65"))

# Ймовірність взаємної відповіді стікером, якщо користувач надіслав стікер
PROB_USER_STICKER: float = float(os.getenv("STICKER_PROB_USER_STICKER", "0.85"))

# Максимальна довжина тексту для визначення "короткого запитання"
MAX_SHORT_QUERY_LEN: int = int(os.getenv("MAX_SHORT_QUERY_LEN", "45"))
MAX_SHORT_QUERY_WORDS: int = int(os.getenv("MAX_SHORT_QUERY_WORDS", "6"))


# ---------------------------------------------------------------------------
# Кеш стікерів
# ---------------------------------------------------------------------------
_cached_stickers: List[Sticker] = []
_cached_file_ids: List[str] = []
_stickers_by_emoji: Dict[str, List[str]] = {}
_is_loaded: bool = False


async def load_stickers(bot: Bot, force_refresh: bool = False) -> List[str]:
    """Завантажує та кешує список стікерів із заданого стікерпаку через Telegram API.

    Якщо запит не вдається (наприклад, тимчасова помилка мережі або недійсний токен),
    безпечно логує помилку та не зупиняє роботу бота.
    """
    global _cached_stickers, _cached_file_ids, _stickers_by_emoji, _is_loaded

    if _is_loaded and not force_refresh and _cached_file_ids:
        return _cached_file_ids

    try:
        sticker_set = await bot.get_sticker_set(name=STICKER_SET_NAME)
        _cached_stickers = list(sticker_set.stickers)
        _cached_file_ids = [s.file_id for s in _cached_stickers]

        _stickers_by_emoji.clear()
        for s in _cached_stickers:
            if s.emoji:
                _stickers_by_emoji.setdefault(s.emoji, []).append(s.file_id)

        _is_loaded = True
        print(
            f"[stickers] [OK] Loaded {len(_cached_file_ids)} stickers "
            f"from set '{STICKER_SET_NAME}' (title: '{sticker_set.title}')"
        )
        return _cached_file_ids

    except Exception as e:
        _is_loaded = False
        print(f"[stickers] [WARN] Could not load sticker set '{STICKER_SET_NAME}': {redact(e)}")
        return _cached_file_ids




def get_random_sticker(preferred_emojis: Optional[List[str]] = None) -> Optional[str]:
    """Повертає file_id випадкового стікера із кешу.

    Якщо вказано preferred_emojis, спочатку шукає стікер з цими емодзі.
    Якщо таких немає або preferred_emojis не задано, повертає випадковий стікер з усього паку.
    """
    if not _cached_file_ids:
        return None

    if preferred_emojis:
        for emoji in preferred_emojis:
            matches = _stickers_by_emoji.get(emoji)
            if matches:
                return random.choice(matches)

    return random.choice(_cached_file_ids)


async def get_or_load_sticker(bot: Bot, preferred_emojis: Optional[List[str]] = None) -> Optional[str]:
    """Повертає випадковий стікер, за потреби завантажуючи пак, якщо кеш ще порожній."""
    global _cached_file_ids
    if not _cached_file_ids:
        await load_stickers(bot)
    return get_random_sticker(preferred_emojis)



# ---------------------------------------------------------------------------
# Шаблони для класифікації повідомлень
# ---------------------------------------------------------------------------
_RE_GREETING = re.compile(
    r"^(привіт|добрий\s+(ранок|день|вечір)|віта(ю|ємо)|хай|хелло|hello|hi|hey|привет|доброе\s+утро|добрый\s+(день|вечер)|здравствуй(те)?|dobr[yý](j)?\s+(den|den\'|ranok|vechir)|pryvit|privet)\b",
    re.IGNORECASE,
)

_RE_GRATITUDE = re.compile(
    r"\b(дяку(ю|єм)|спасиб(і|о)|дяка|благодар(ю|им)|thanks|thank\s+you|thx)\b",
    re.IGNORECASE,
)

_RE_REACTION = re.compile(
    r"^(ок|окей|добре|зрозумів|зрозуміло|поняв|понятно|супер|клас|класно|круто|чудово|отлично|кайф|ого|вау|цікаво|ясно|гарно|\+|👍|👌|❤️|🔥)$",
    re.IGNORECASE,
)

_RE_FAREWELL = re.compile(
    r"^(бувай|до\s+побачення|папа|на\s+добраніч|до\s+зустрічі|пока|до\s+свидания|спокойной\s+ночи|до\s+скорого|bye|goodbye)\b",
    re.IGNORECASE,
)

_QUESTION_STARTERS = (
    "що", "як", "чому", "де", "коли", "хто", "чи", "куди", "звідки", "який", "яка", "яке", "які",
    "что", "как", "почему", "где", "когда", "кто", "куда", "откуда", "какой", "какая", "какие",
    "підкажи", "порадь", "скажи", "можна", "чи можна", "подскажи", "посоветуй", "можно",
)


def is_greeting(text: str) -> bool:
    """Перевіряє, чи є текст коротким привітанням."""
    cleaned = text.strip()
    words = cleaned.split()
    return len(words) <= 4 and bool(_RE_GREETING.search(cleaned))


def is_gratitude(text: str) -> bool:
    """Перевіряє, чи висловлює текст подяку."""
    cleaned = text.strip()
    words = cleaned.split()
    return len(words) <= 5 and bool(_RE_GRATITUDE.search(cleaned))


def is_reaction(text: str) -> bool:
    """Перевіряє, чи є текст короткою схвальною реакцією або згодою."""
    cleaned = text.strip()
    return bool(_RE_REACTION.match(cleaned))


def is_farewell(text: str) -> bool:
    """Перевіряє, чи є текст коротким прощанням."""
    cleaned = text.strip()
    words = cleaned.split()
    return len(words) <= 4 and bool(_RE_FAREWELL.search(cleaned))


def is_short_question(text: str) -> bool:
    """Перевіряє, чи є текст коротким запитанням.

    Критерії:
    1. Довжина <= MAX_SHORT_QUERY_LEN і кількість слів <= MAX_SHORT_QUERY_WORDS.
    2. Містить знак '?' АБО починається з питального слова/прохання.
    """
    cleaned = text.strip()
    if not cleaned:
        return False

    if len(cleaned) > MAX_SHORT_QUERY_LEN:
        return False

    words = cleaned.split()
    if not (1 <= len(words) <= MAX_SHORT_QUERY_WORDS):
        return False

    lower = cleaned.lower()
    if "?" in cleaned:
        return True

    for starter in _QUESTION_STARTERS:
        if lower.startswith(starter):
            return True

    # Короткі запити з 1-2 слів (наприклад, назва олії "Лаванда", "М'ята", "Чайне дерево")
    if len(words) <= 2 and not is_reaction(cleaned):
        return True

    return False


def should_accompany_with_sticker(text: str, is_complaint: bool = False, is_red_flag: bool = False) -> bool:
    """Визначає, чи варто додати стікер до звичайної відповіді на коротке питання.
    
    Якщо є скарга на здоров'я або червоний прапор — стікери НЕ додаються.
    """
    if is_red_flag or is_complaint:
        return False

    if not _cached_file_ids:
        return False

    if is_short_question(text):
        return random.random() < PROB_SHORT_QUESTION

    return False



def classify_casual_interaction(
    text: str,
    is_complaint: bool = False,
    is_red_flag: bool = False,
) -> tuple[bool, Optional[str], Optional[str]]:
    """Визначає, чи є повідомлення повсякденною реплікою (привітання, подяка, реакція),
    на яку бот може відповісти стікером замість важкого звернення до LLM.

    Повертає:
        (should_reply_sticker, reply_text, preferred_emoji)
    """
    if is_complaint or is_red_flag:
        return False, None, None

    if not _cached_file_ids:
        return False, None, None

    # Перевірка ймовірності для повсякденних повідомлень
    if random.random() >= PROB_CASUAL:
        return False, None, None

    cleaned = text.strip()

    if is_gratitude(cleaned):
        replies = [
            "Радий допомогти! 🌿 Звертайся, якщо будуть ще запитання.",
            "Будь ласка! Завжди радий підказати про олії doTERRA 💚",
            "На здоров'я! 🌸 Якщо знадобиться ще порада — пиши!",
        ]
        return True, random.choice(replies), "❤️"

    if is_greeting(cleaned):
        replies = [
            "Привіт! 🌿 Я Aroma Assistant, помічниця Наталії Котелянської. Чим можу допомогти тобі сьогодні?",
            "Вітаю! 🌸 Запитуй будь-що про ефірні олії та продукти doTERRA, які у нас є.",
            "Привіт! 💛 Я помічниця Наталії Котелянської. З радістю підкажу про олії та продукцію doTERRA ✨",
        ]
        return True, random.choice(replies), "👋"

    if is_farewell(cleaned):
        replies = [
            "Бувай! Гарного та ароматного дня! 🌿",
            "До зустрічі! Нехай день буде спокійним та затишним 🌸",
        ]
        return True, random.choice(replies), "👋"

    if is_reaction(cleaned):
        return True, None, "👍"

    return False, None, None


def should_reply_to_user_sticker() -> bool:
    """Визначає, чи відповісти стікером на стікер від користувача."""
    if not _cached_file_ids:
        return False
    return random.random() < PROB_USER_STICKER

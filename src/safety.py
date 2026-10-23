"""Захист від витоку секретів у логи та чат.

- redact(text)      — маскує рядки підключення до БД, API-ключі та токени ботів.
- safe_error(e)     — короткий безпечний опис помилки (лише тип) для відповіді користувачу.
- key_fingerprint() — стійкий ідентифікатор ключа для логів без жодного фрагмента самого ключа.
"""

# Standard
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import re
import unicodedata

_PATTERNS: list[tuple[re.Pattern, str]] = [
    # scheme://user:password@host → scheme://user:***@host
    (re.compile(r"([a-zA-Z][a-zA-Z0-9+.\-]*://[^:/\s@]+:)[^@\s/]+(@)"), r"\1***\2"),
    # DSN, query params та JSON: BOT_TOKEN=..., password="secret", ?key=..., 'token': '...'
    (
        re.compile(
            r"""(?i)(["']?(?:[a-z0-9_-]*(?:password|passwd|pwd|token|secret)|(?:[a-z0-9_-]*[_-]|[?&]|\b)key)["']?\s*[=:]\s*)(?:["'][^"']+["']|[^\s,;&'"\\]+)"""
        ),
        r"\g<1>***",
    ),
    # Google API keys
    (re.compile(r"AIza[0-9A-Za-z_\-]{20,}"), "***"),
    # OpenAI / Anthropic style keys
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), "***"),
    # Telegram bot token 123456789:AA... (включаючи URL-шляхи на кшталт /bot123456:...)
    (re.compile(r"(?:(?<=[bB][oO][tT])|\b)\d{6,}:[A-Za-z0-9_\-]{20,}"), "***"),
    # Bearer-токени
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{16,}"), r"\1***"),
]


def redact(value: object) -> str:
    """Повертає текст із замаскованими секретами. Приймає будь-який об'єкт (напр. виняток)."""
    text = str(value)
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return text


def redact_db_url(url: str | None) -> str:
    """Для логів: лише host/db без логіна та пароля."""
    if not url:
        return "<not set>"
    m = re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://(?:[^@/]*@)?([^/?]+)(/[^?]*)?", url)
    return f"{m.group(1)}{m.group(2) or ''}" if m else "<invalid url>"


def safe_error(e: BaseException) -> str:
    """Безпечний опис помилки для користувача: лише тип, без тексту виключення."""
    return type(e).__name__


def key_fingerprint(api_key: str | None) -> str:
    """Короткий хеш ключа: дозволяє розрізняти ключі в логах, не розкриваючи жодного символу."""
    if not api_key:
        return "none"
    return hashlib.sha256(api_key.encode()).hexdigest()[:6]


_ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\ufeff\u00ad\u2060-\u206f\u202a-\u202e]")

_ROLE_INJECTION_RE = re.compile(
    r"(?im)^[ \t>*#\-_*`'\"\[(]*"
    r"(?:"
    r"[БбВвBb][ОоOo0][ТтTt]"
    r"|[AaАа][SsСсCc]{1,2}[IiІіИи1][SsСсCc][TtТт][AaАаEeЕе][NnНн][TtТт]"
    r"|[KkКк][ОоOo0][RrРр][IiІіИи1][SsСсCc][TtТт][UuУу][VvВв][AaАа][ЧчChch]"
    r"|[UuУу][SsСс][EeЕе][RrРр]"
    r"|[SsСс][YyУуIiІіИи1][SsСс][TtТт][EeЕе][MmМм][AaАа]?"
    r"|[AaАа][IiІі1]"
    r"|[MmМм][ОоOo0][DdДд][EeЕе][LlЛл][Ьь]?"
    r"|[Gg][EeЕе][MmМм][IiІі1][NnНн][IiІі1]"
    r"|[HhНн][UuУу][MmМм][AaАа][NnНн]"
    r")"
    r"[ \t*`'\"\])]*"
    r"[:：=\u002d\u2010-\u2015\u2212]+"
    r"[ \t*`'\"\])]*",
)


def sanitize_dialogue_text(text: str, max_chars: int = 500) -> str:
    """Очищає текст користувача від спроб підробки ролей бота у діалозі (role injection)."""
    if not text:
        return ""
    # 1. Видаляємо невидимі та нульової ширини керуючі символи
    cleaned = _ZERO_WIDTH_RE.sub("", text)
    # 2. Нормалізація Unicode NFKC (повноширинні Ｂｏｔ → Bot, ： → : тощо)
    cleaned = unicodedata.normalize("NFKC", cleaned)
    # 3. Нейтралізуємо фальшиві заголовки реплік на початку рядків (з омогліфами кирилиця/латиниця)
    cleaned = _ROLE_INJECTION_RE.sub("(ввід користувача)", cleaned)
    cleaned = cleaned.strip()
    return cleaned[:max_chars]


def append_and_format_dialogue(
    turns: list[dict[str, str]] | None,
    new_user_text: str | None = None,
    bot_response: str | None = None,
    max_turns: int = 3,
    max_chars: int = 1500,
) -> tuple[list[dict[str, str]], str]:
    """Додає нові репліки, обмежує глибину історії (FIFO) та повертає (turns, context_str).

    - Обмежує кількість реплік (не більше max_turns діалогових пар).
    - Захищає від безкінечного зростання пам'яті FSM та контексту LLM.
    - Форматує рядок для RAG та LLM із чіткими префіксами.
    """
    safe_turns = [dict(t) for t in (turns or []) if isinstance(t, dict)]

    if new_user_text is not None:
        safe_user = sanitize_dialogue_text(new_user_text)
        if safe_user:
            safe_turns.append({"role": "user", "text": safe_user})

    if bot_response is not None:
        safe_bot = bot_response.strip()[:400]
        if safe_bot:
            safe_turns.append({"role": "bot", "text": safe_bot})

    # Обмежуємо кількість повідомлень (max_turns пар = 2 * max_turns повідомлень)
    max_msgs = max_turns * 2
    if len(safe_turns) > max_msgs:
        safe_turns = safe_turns[-max_msgs:]

    parts = []
    for t in safe_turns:
        prefix = "Користувач:" if t.get("role") == "user" else "Бот:"
        parts.append(f"{prefix} {t.get('text', '')}")

    context_str = "\n\n".join(parts)
    if len(context_str) > max_chars:
        context_str = context_str[-max_chars:]

    return safe_turns, context_str


def sanitize_ai_response_text(text: str) -> str:
    """Нормалізує та очищає згенерований AI текст від глітчів та спотворених символів.

    - Замінює арабські/перські символи (наприклад, арабську 'ي' у 'менي' замість української 'і' у 'мені').
    - Видаляє невидимі керуючі Bidi-символи (LRM, RLM, ZWSP тощо).
    - Нормалізує сабскрипти (ᵢ -> і, ₑ -> е тощо).
    - Замінює поодинокі латинські 'i' / 'I' всередині кириличних слів на українські 'і' / 'І'.
    """
    if not text:
        return text or ""

    # Невидимі та керуючі Bidi-символи, що ламають відображення в Telegram
    bidi_and_invisible = [
        "\u200b", "\u200c", "\u200d", "\u200e", "\u200f",
        "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
        "\u2066", "\u2067", "\u2068", "\u2069", "\ufeff",
    ]
    for char in bidi_and_invisible:
        text = text.replace(char, "")

    # Арабські/перські символи, які модель іноді помилково генерує замість кирилиці
    arabic_homoglyphs = {
        "\u064a": "і",  # Arabic Yeh (наприклад, 'менي' -> 'мені')
        "\u0649": "і",  # Alef Maksura
        "\u06cc": "і",  # Farsi Yeh
        "\u06d2": "і",  # Urdu Yeh
        "\u0626": "ї",  # Yeh with hamza
        "\u0647": "е",  # Heh
        "\u0648": "у",  # Waw
        "\u0627": "а",  # Alef
        "\u0631": "р",  # Reh
        "\u062f": "д",  # Dal
        "\u0643": "к",  # Kaf
        "\u0645": "м",  # Meem
        "\u0646": "н",  # Noon
        "\u0628": "б",  # Beh
        "\u062a": "т",  # Teh
        "\u0633": "с",  # Seen
        "\u0632": "з",  # Zain
    }
    for ar_char, cyr_char in arabic_homoglyphs.items():
        text = text.replace(ar_char, cyr_char)

    # Сабскрипти
    subscripts = {
        "\u1d62": "і",
        "\u2091": "е",
        "\u2090": "а",
        "\u2092": "о",
        "\u2093": "х",
        "\u2094": "е",
        "\u207f": "н",
    }
    for sub_char, norm_char in subscripts.items():
        text = text.replace(sub_char, norm_char)

    # Видаляємо залишки арабського та єврейського блоків (включно з Presentation Forms)
    text = re.sub(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\u0590-\u05FF\uFB50-\uFDFF\uFE70-\uFEFF]", "", text)

    # Латинська 'i' / 'I' всередині або поряд із кириличними літерами
    cyr = r"[а-яА-ЯіїєґІЇЄҐ]"
    for _ in range(3):
        text = re.sub(rf"(?<={cyr})i", "і", text)
        text = re.sub(rf"i(?={cyr})", "і", text)
        text = re.sub(rf"(?<={cyr})I", "І", text)
        text = re.sub(rf"I(?={cyr})", "І", text)

    return text


def get_kyiv_time_of_day(now: datetime | None = None) -> tuple[str, str]:
    """Повертає ідентифікатор часу доби та відповідне привітання за київським часом.

    Орієнтири за часом:
        - Ранок: до 12:00 (05:00 - 11:59) -> 'morning', 'Доброго ранку! ☀️'
        - День: після 12:00 до 18:00 (12:00 - 17:59) -> 'day', 'Доброго дня! 🌿'
        - Ніч: після 18:00 до 12 ночі та нічний час (18:00 - 04:59) -> 'night', 'Доброї ночі! 🌙'

    Повертає:
        (time_id, greeting_phrase):
        'morning': 'Доброго ранку! ☀️'
        'day':     'Доброго дня! 🌿'
        'night':   'Доброї ночі! 🌙'
    """
    if now is None:
        try:
            now = datetime.now(ZoneInfo("Europe/Kyiv"))
        except Exception:
            now = datetime.now()
    hour = now.hour
    if 5 <= hour < 12:
        return "morning", "Доброго ранку! ☀️"
    elif 12 <= hour < 18:
        return "day", "Доброго дня! 🌿"
    else:
        # Після 18:00 до 12 ночі (18 <= hour < 24) та до ранку
        return "night", "Доброї ночі! 🌙"


_REDUNDANT_GREETING_PREFIX_RE = re.compile(
    r"^(?:\s*(?:"
    r"привіт(?:ік)?|вітаю|доброго\s+(?:ранку|дня|вечора)|добрий\s+(?:ранок|день|вечір)|доброї\s+ночі|hello|hi"
    r")[!., \-—–~*]*"
    r"[\U00010000-\U0010ffff\u2600-\u26ff\u2700-\u27bf\s]*"
    r"(?:(?:я\s*[-—–]?\s*арома|мене\s+звати\s+арома|я\s+(?:твоя\s+)?помічниця\s+наталії(?:\s+котелянської)?)[^.!?\n]*[.!?\n]+\s*)?"
    r")+\s*",
    re.IGNORECASE,
)

_REDUNDANT_INTRO_STANDALONE_RE = re.compile(
    r"^(?:\s*(?:я\s*[-—–]?\s*арома|мене\s+звати\s+арома|я\s+(?:твоя\s+)?помічниця\s+наталії(?:\s+котелянської)?)[^.!?\n]*[.!?\n]+\s*)",
    re.IGNORECASE,
)


def strip_redundant_greetings(text: str) -> str:
    """Видаляє повторні привітання та самопрезентації на початку тексту у триваючому діалозі."""
    if not text:
        return text or ""
    res = _REDUNDANT_GREETING_PREFIX_RE.sub("", text)
    res = _REDUNDANT_INTRO_STANDALONE_RE.sub("", res)
    return res if res.strip() else text


UNSUPPORTED_CONTENT_REPLY: str = (
    "Я розумію лише текст… 💬 Будь ласка, напиши своє запитання текстом 🌸"
)


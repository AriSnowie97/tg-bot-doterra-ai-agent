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

# Ключові стікери набору aromaaitgbot (де кілька стікерів мають однакове емодзі 👋):
# 0: «Привіт!» (дівчинка махає рукою з пляшечкою олії)
WELCOME_STICKER_FILE_ID: str = "CAACAgIAAxUAAWrbKIYm3QeIG_mhAVeWS9HCtk8FAAJsowACDJ5ZSOjEm6o-dy33PQQ"
# 24: «Гарного дня!» (дівчинка у бузковій ковдрі зі свічкою)
GOOD_DAY_STICKER_FILE_ID: str = "CAACAgIAAxUAAWrbKIa9rbJQbTF_bv8xdfCZK-ZNAAL_nAACFi9ZSOsM6G3dtaPrPQQ"
# 25: «До побачення!» (дівчинка йде та махає рукою)
FAREWELL_STICKER_FILE_ID: str = "CAACAgIAAxUAAWrbKIZzAAEsh6yTx45frRh966g0IwACBqsAAvFP0Up0RYfJZuq6uj0E"

# Негативні / відмовні / конфліктні емодзі (наприклад, червоний хрест ❌ або схрещені руки 🙅)
# Їх КАТЕГОРИЧНО НЕ МОЖНА відправляти у випадковому порядку чи на звичайні дружні запитання!
NEGATIVE_EMOJIS: set[str] = {
    "❌", "🙅", "🙅‍♀️", "🙅‍♂️", "🚫", "⛔", "👎", "😡", "🤬", "💔", "👿", "✖️"
}

# Безпечні дружні та позитивні емодзі для загальних відповідей та випадкового вибору
SAFE_DEFAULT_EMOJIS: list[str] = [
    "🌿", "✨", "😊", "🌸", "🌱", "💧", "💛", "👋", "🤔", "🍃", "🥰"
]

# Словник синонімів та споріднених емодзі, прив'язаних до 28 стікерів набору aromaaitgbot:
# [👋, 😊, 🌿, 😶‍🌫️, ☺️, 🍋‍🟩, 😍, 😃, 🥳, 🎄, 😷, 👍, 💆‍♀️, ☀️, 🌓, 😴, 🤟, 😌, 🤔, 🙏, 🥺, ☝️, 👌, 👎]
EMOJI_SYNONYMS: dict[str, list[str]] = {
    "👋": ["👋", "😊", "☺️", "🌿"],
    "🌿": ["🌿", "🌱", "🍃", "🍋‍🟩", "🎄", "✨", "💚"],
    "🤔": ["🤔", "☝️", "💡", "💭", "🧐", "🌿", "😊"],
    "😊": ["😊", "☺️", "😃", "😌", "🌿", "✨"],
    "☺️": ["☺️", "😊", "😌", "🌿", "👋"],
    "❤️": ["😍", "❤️", "🥰", "💖", "🙏", "😊"],
    "😍": ["😍", "❤️", "🥰", "✨", "😊"],
    "👍": ["👍", "👌", "🤟", "😃", "😊"],
    "👌": ["👌", "👍", "🤟", "😊"],
    "🤟": ["🤟", "👍", "👌", "😃", "🥳"],
    "🥳": ["🥳", "😃", "🤟", "😍", "👍"],
    "😴": ["😴", "🌓", "😌", "💆‍♀️"],
    "💆‍♀️": ["💆‍♀️", "😌", "🌿", "🌸"],
    "☀️": ["☀️", "🍋‍🟩", "😃", "🌿"],
    "🍋‍🟩": ["🍋‍🟩", "☀️", "🌿", "😃"],
    "🍋": ["🍋‍🟩", "☀️", "🌿"],
    "🍊": ["🍋‍🟩", "☀️", "🌿"],
    "🎄": ["🎄", "🌿", "😌"],
    "🌲": ["🎄", "🌿"],
    "😷": ["😷", "🌿", "☝️", "🍋‍🟩"],
    "😶‍🌫️": ["😶‍🌫️", "🌿", "😌"],
    "😌": ["😌", "🌿", "🌓", "💆‍♀️", "☺️"],
    "🌓": ["🌓", "😴", "😌"],
    "🌙": ["🌓", "😴", "😌"],
    "💤": ["😴", "🌓", "😌"],
    "🙏": ["🙏", "😊", "☺️", "❤️"],
    "🥺": ["🥺", "🙏", "😊", "☺️"],
    "☝️": ["☝️", "🤔", "🌿", "💡"],
    "🌸": ["💆‍♀️", "🌿", "😊", "☺️"],
    "✨": ["✨", "🌿", "😊", "☀️", "🍋‍🟩"],
    "💧": ["🌿", "🍋‍🟩", "😶‍🌫️"],
    "💡": ["🤔", "☝️", "🌿"],
    "👎": ["👎", "❌", "🙅", "🙅‍♀️", "🚫"],
    "❌": ["👎", "❌", "🙅"],
    "🙅": ["👎", "❌"],
}


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
                # Зберігаємо повний рядок емодзі та кожен окремий символ
                _stickers_by_emoji.setdefault(s.emoji, []).append(s.file_id)
                for char in s.emoji:
                    if char != s.emoji:
                        _stickers_by_emoji.setdefault(char, []).append(s.file_id)

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


def get_random_sticker(preferred_emojis: Optional[list[str] | str] = None) -> Optional[str]:
    """Повертає file_id найбільш доречного стікера із кешу.

    1. Якщо вказано preferred_emojis (одне емодзі або список пріоритетних):
       - Розширює список спорідненими емодзі (EMOJI_SYNONYMS).
       - Шукає точний збіг стікерів за цими емодзі по черзі.
       - Якщо знайдено — повертає випадковий із них.
       - Для емодзі 👋 виключає стікери прощання/побажання дня («До побачення!», «Гарного дня!»),
         щоб не вітати користувача стікером прощання.
    2. Якщо точного збігу за preferred_emojis немає:
       - Шукає серед безпечних позитивних емодзі (SAFE_DEFAULT_EMOJIS).
       - У жодному разі не повертає негативні/заборонні стікери (👎, ❌, 🙅) як випадковий фолбек!
    """
    if not _cached_file_ids:
        return None

    if preferred_emojis:
        raw_list = [preferred_emojis] if isinstance(preferred_emojis, str) else list(preferred_emojis)
        expanded_emojis: list[str] = []
        for e in raw_list:
            if not e:
                continue
            expanded_emojis.append(e)
            if e in EMOJI_SYNONYMS:
                expanded_emojis.extend(EMOJI_SYNONYMS[e])

        # Усуваємо дублікати, зберігаючи пріоритетний порядок
        seen = set()
        ordered_emojis = [x for x in expanded_emojis if not (x in seen or seen.add(x))]

        for emoji in ordered_emojis:
            matches = _stickers_by_emoji.get(emoji)
            if matches:
                # Якщо шукаємо '👋' (вітання/помах), виключаємо стікери прощання та побажання дня
                if emoji == "👋" and len(matches) > 1:
                    greeting_matches = [
                        m for m in matches if m not in (GOOD_DAY_STICKER_FILE_ID, FAREWELL_STICKER_FILE_ID)
                    ]
                    if greeting_matches:
                        return random.choice(greeting_matches)
                return random.choice(matches)

    # Якщо preferred_emojis не задано або не знайдено збігу:
    # 1. Пробуємо знайти стікери з безпечними позитивними емодзі (виключаючи прощання)
    safe_matches: list[str] = []
    for safe_emoji in SAFE_DEFAULT_EMOJIS:
        if safe_emoji in _stickers_by_emoji:
            for fid in _stickers_by_emoji[safe_emoji]:
                if fid not in (GOOD_DAY_STICKER_FILE_ID, FAREWELL_STICKER_FILE_ID):
                    safe_matches.append(fid)

    if safe_matches:
        return random.choice(safe_matches)

    # 2. Якщо серед емодзі немає SAFE_DEFAULT_EMOJIS, беремо будь-який стікер,
    # чий emoji НЕ містить жодного з NEGATIVE_EMOJIS (❌, 🙅 тощо) і не є прощанням
    non_negative: list[str] = []
    for s in _cached_stickers:
        if s.emoji and not any(neg in s.emoji for neg in NEGATIVE_EMOJIS):
            if s.file_id not in (GOOD_DAY_STICKER_FILE_ID, FAREWELL_STICKER_FILE_ID):
                non_negative.append(s.file_id)

    if non_negative:
        return random.choice(non_negative)

    return random.choice(_cached_file_ids)


async def get_or_load_sticker(bot: Bot, preferred_emojis: Optional[list[str] | str] = None) -> Optional[str]:
    """Повертає випадковий стікер, за потреби завантажуючи пак, якщо кеш ще порожній."""
    global _cached_file_ids
    if not _cached_file_ids:
        await load_stickers(bot)
    return get_random_sticker(preferred_emojis)


async def get_welcome_sticker(bot: Bot) -> Optional[str]:
    """Повертає file_id вітального стікера («Привіт!»).

    Спеціально призначений для команди /start та первинних привітань,
    гарантуючи, що користувач отримає саме стікер із написом «Привіт!»,
    а не «Гарного дня!» чи «До побачення!», які мають однакове емодзі 👋 в паку.
    """
    global _cached_stickers, _cached_file_ids
    if not _cached_file_ids:
        await load_stickers(bot)

    # 1. Якщо у кеші є перевірений WELCOME_STICKER_FILE_ID
    if WELCOME_STICKER_FILE_ID in _cached_file_ids:
        return WELCOME_STICKER_FILE_ID

    # 2. Якщо це пак aromaaitgbot — перший стікер у ньому це «Привіт!»
    if _cached_stickers and STICKER_SET_NAME == "aromaaitgbot":
        return _cached_stickers[0].file_id

    # 3. Фолбек для aromaaitgbot при тимчасових збоях зв'язку
    if STICKER_SET_NAME == "aromaaitgbot":
        return WELCOME_STICKER_FILE_ID

    # 4. Для інших кастомних паків: шукаємо перше емодзі 👋 без стікерів прощання
    wave_stickers = [
        fid for fid in _stickers_by_emoji.get("👋", [])
        if fid not in (GOOD_DAY_STICKER_FILE_ID, FAREWELL_STICKER_FILE_ID)
    ]
    if wave_stickers:
        return wave_stickers[0]

    return get_random_sticker(preferred_emojis=["👋", "🌿", "😊", "✨"])


async def get_farewell_sticker(bot: Bot) -> Optional[str]:
    """Повертає file_id стікера прощання («До побачення!» або «Гарного дня!»)."""
    global _cached_file_ids
    if not _cached_file_ids:
        await load_stickers(bot)

    farewell_options = [
        fid for fid in (FAREWELL_STICKER_FILE_ID, GOOD_DAY_STICKER_FILE_ID)
        if fid in _cached_file_ids
    ]
    if farewell_options:
        return random.choice(farewell_options)

    if STICKER_SET_NAME == "aromaaitgbot":
        return random.choice([FAREWELL_STICKER_FILE_ID, GOOD_DAY_STICKER_FILE_ID])

    return get_random_sticker(preferred_emojis=["👋", "😊", "☺️"])


# ---------------------------------------------------------------------------
# Шаблони та правила для класифікації емоцій, тем та ключових слів
# ---------------------------------------------------------------------------

_RULE_PROHIBITION = [
    re.compile(
        r"\b(не\s+можна|нельзя|заборонен[оа-я]*|запрещен[оа-я]*|небезпечн[оа-я]*|опасн[оа-я]*)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(в\s+оч[іи]|в\s+глаза|в\s+уш[іи]|в\s+уши|не\s+капа[йт]|не\s+пей[те]*|не\s+пити|чистому\s+вигляді|чистом\s+виде)\b",
        re.IGNORECASE,
    ),
]

# Багаторівневий список правил (категорія, список compiled regex, пріоритетні емодзі з паку)
STICKER_TOPIC_RULES: list[tuple[str, list[re.Pattern], list[str]]] = [
    # 1. Сувора заборона / застереження (НЕ можна капати в очі/вуха тощо)
    (
        "prohibition",
        _RULE_PROHIBITION,
        ["👎"],
    ),
    # 2. Улюблене масло Ароми, Лайм, "Ні, я не буду це пити без Lime"
    (
        "favorite_oil",
        [
            re.compile(r"\b((най)?улюблен\w*|(най)?любим\w*)\s+(ол\w+|масл\w+|аромат\w*)", re.IGNORECASE),
            re.compile(r"\b(favorite\s+oil|тв[оі][єя]\s+(най)?улюблен\w*|тво[еёя]\s+(най)?любим\w*)\b", re.IGNORECASE),
            re.compile(r"\b(лайм\w*|lime|не\s+буду\s+(це\s+)?пити\s+без\s+lime|без\s+лайм\w*)\b", re.IGNORECASE),
        ],
        ["🍋‍🟩", "😍", "🌿", "😊"],
    ),
    # 3. Асортимент, що є, каталог, що маєш, що вмієш, покажи
    (
        "assortment",
        [
            re.compile(r"\b(що\s+(ти\s+)?маєш|что\s+(ты\s+)?имеешь|что\s+есть|що\s+є|каталог|асортимент|ассортимент)\b", re.IGNORECASE),
            re.compile(r"\b(що\s+вмієш|что\s+умеешь|які\s+є\s+олії|какие\s+есть\s+масла|список\s+(олій|масел)|продукці[яї]|продукци[яи])\b", re.IGNORECASE),
            re.compile(r"\b(покажи|розкажи\s+про\s+олії|расскажи\s+про\s+масла|допоможи\s+вибрати|помоги\s+выбрать)\b", re.IGNORECASE),
        ],
        ["🤔", "🌿", "☝️", "😊"],
    ),
    # 3. Сон, безсоння, ніч, вечір, відпочинок (Serenity, Lavender)
    (
        "sleep",
        [
            re.compile(r"\b(сон[а-я]*|сн[аеиуоя][а-я]*|засин[а-я]*|засып[а-я]*|сп[ая][тл][а-я]*|безсонн[яі]|бессонниц[ае]|заснут[иь]|уснуть|ніч|ноч[ьюи]|вечір[а-я]*|вечер[а-я]*)\b", re.IGNORECASE),
            re.compile(r"\b(сереніті|серен[иі]ти|serenity|лаванд[аеиу]|lavender|спокійн[оа-я]*|спокойн[оа-я]*|заспокоїт[иь]|успокоит[иь])\b", re.IGNORECASE),
        ],
        ["😴", "🌓", "😌", "💆‍♀️"],
    ),
    # 4. Головний біль, напруга, масаж, SPA, м'язи, догляд за шкірою (PastTense, Deep Blue, AromaTouch)
    (
        "massage_spa",
        [
            re.compile(r"\b(голов[а-я]*\s+болить|головн[оа-я]*\s+б[іи]л[ья]|скрон[іях]|виск[а-я]*|масаж[а-я]*|массаж[а-я]*|спа\b|spa\b)\b", re.IGNORECASE),
            re.compile(r"\b(ши[яїе]|ше[еия]|м['’]?яз[а-я]*|мышц[а-я]*|напруг[а-я]*|напряжен[а-я]*|паст\s*тенс|past\s*tense|aromatouch|ароматач)\b", re.IGNORECASE),
            re.compile(r"\b(шкір[а-я]*|кож[а-я]*|обличч[яі]|лиц[оеа]|догляд[а-я]*|уход[а-я]*)\b", re.IGNORECASE),
        ],
        ["💆‍♀️", "😌", "🌿"],
    ),
    # 5. Застуда, імунітет, кашель, горло, вірус, захист (On Guard, Чайне дерево)
    (
        "immunity_cold",
        [
            re.compile(r"\b(імунітет[а-я]*|иммунитет[а-я]*|застуд[а-я]*|простуд[а-я]*|хвороб[а-я]*|болезн[а-я]*|горл[оа-я]*|каш[еі]л[ья]*)\b", re.IGNORECASE),
            re.compile(r"\b(нежит[ья]|насморк[а-я]*|вірус[а-я]*|вирус[а-я]*|температур[а-я]*|он\s*гард|on\s*guard|онгард|профілактик[а-я]*)\b", re.IGNORECASE),
            re.compile(r"\b(чайн[ое][ея]\s+дерев[оа]|масло\s+чайного\s+дерева|чайне\s+дерево|melaleuca|маск[а-я]*)\b", re.IGNORECASE),
        ],
        ["😷", "🌿", "☝️", "🍋‍🟩"],
    ),
    # 6. Енергія, бадьорість, ранок, тонус, втома (Wild Orange, Peppermint)
    (
        "energy_morning",
        [
            re.compile(r"\b(енергі[яїею]|энерги[яиею]|ранок|ранк[уа]|утр[оа-я]*|бадьор[іе][сз][ть]*|бодрост[ьюи]|тонус[а-я]*|прокинут[иь]ся|проснут[иь]ся)\b", re.IGNORECASE),
            re.compile(r"\b(втом[а-я]*|усталост[ьюи]|сонлив[іи]ст[ьюи]|дик[ийая]\s+апельсин|wild\s+orange|мотиваці[яї]|мотиваци[яи]|активн[іи]ст[ьюи])\b", re.IGNORECASE),
        ],
        ["☀️", "🍋‍🟩", "😃", "🌿"],
    ),
    # 7. Цитрусові, лимон, лайм, свіжість, вода з лимоном, детокс
    (
        "citrus_fresh",
        [
            re.compile(r"\b(цитрус[а-я]*|лимон[а-я]*|lemon|лайм[а-я]*|lime|апельсин[а-я]*|orange|грейпфрут[а-я]*|grapefruit|бергамот[а-я]*|bergamot)\b", re.IGNORECASE),
            re.compile(r"\b(свіж[іе][сз][ть]*|свежест[ьюи]|детокс[а-я]*|вода\s+з\s+лимоном|вода\s+с\s+лимоном|мандарин[а-я]*)\b", re.IGNORECASE),
        ],
        ["🍋‍🟩", "☀️", "🌿", "😃"],
    ),
    # 8. Хвойні, ялиця, ліс, зима, кедр, кипарис (Siberian Fir, Cypress, Cedarwood)
    (
        "conifers_forest",
        [
            re.compile(r"\b(хвойн[а-я]*|ялиц[яіе]|пихт[а-я]*|сибірськ[а-я]*\s+ялиц|сибирск[а-я]*\s+пихт|сосн[а-я]*|кедр[а-я]*|cedarwood)\b", re.IGNORECASE),
            re.compile(r"\b(ялівець|можжевельник[а-я]*|кипарис[а-я]*|cypress|ліс[а-я]*|лес[а-я]*|ялинк[а-я]*|елк[а-я]*|зима|зимн[а-я]*)\b", re.IGNORECASE),
        ],
        ["🎄", "🌿", "😌"],
    ),
    # 9. Дифузор, розпилення, вдихання, ароматна пара, туман
    (
        "diffuser_steam",
        [
            re.compile(r"\b(дифузор[а-я]*|диффузор[а-я]*|розпилювач[а-я]*|аромаламп[а-я]*|інгаляці[яї]|ингаляци[яи]|вдихат[иь]|дышат[иь])\b", re.IGNORECASE),
            re.compile(r"\b(ароматн[а-я]*\s+пар[а-я]*|туман[а-я]*|хмарк[а-я]*|облачк[а-я]*)\b", re.IGNORECASE),
        ],
        ["😶‍🌫️", "🌿", "😌"],
    ),
    # 10. Спокій, релакс, антистрес, гармонія, медитація (Balance, Adaptiv)
    (
        "calm_zen",
        [
            re.compile(r"\b(спок[іи][йяе]|поко[йяе]|дзен|гармоні[яї]|гармони[яи]|медитаці[яї]|медитаци[яи]|стрес[а-я]*|стресс[а-я]*)\b", re.IGNORECASE),
            re.compile(r"\b(тривожн[іи]ст[ьюи]|тревог[а-я]*|баланс[а-я]*|balance|адаптів|adaptiv|нерв[иа-я]*|вдих|выдох)\b", re.IGNORECASE),
        ],
        ["😌", "🌿", "🌓", "💆‍♀️"],
    ),
    # 11. Важливі правила, дозування, техніка безпеки, базове масло
    (
        "rules_safety",
        [
            re.compile(r"\b(як\s+приймати|как\s+принимать|як\s+наносити|как\s+наносить|дозуванн[яі]|дозировк[а-я]*)\b", re.IGNORECASE),
            re.compile(r"\b(базов[а-я]*\s+ол[іе][яї]|базов[а-я]*\s+масл[оа]|розведенн[яі]|разведен[иі][ея]|правил[оа-я]*|важлив[оа-я]*|важн[оа-я]*)\b", re.IGNORECASE),
            re.compile(r"\b(зверни\s+увагу|обрати\s+внимание|застереженн[яі]|предостережен[иі][ея]|фракціонован[а-я]*|фракционированн[а-я]*)\b", re.IGNORECASE),
        ],
        ["☝️", "🤔", "🌿"],
    ),
    # 12. Захоплення, любов, найкраща, магія, краса
    (
        "delight_love",
        [
            re.compile(r"\b(обожню[ює]|обожа[юе]|любл[юе]|любов[ью]*|красив[оа-я]*|неймовірн[оа-я]*|невероятн[оа-я]*)\b", re.IGNORECASE),
            re.compile(r"\b(захват[а-я]*|восторг[а-я]*|прекрасн[оа-я]*|чудов[оа-я]*|чудесн[оа-я]*|ідеальн[оа-я]*|идеальн[оа-я]*|улюблен[а-я]*|любим[а-я]*|магі[яїе]|маги[яие])\b", re.IGNORECASE),
        ],
        ["😍", "❤️", "😊", "✨"],
    ),
    # 13. Свято, подарунок, знижка, акція, радість
    (
        "celebration_gift",
        [
            re.compile(r"\b(свят[оа-я]*|праздник[а-я]*|віта[ює]мо|поздравля[юе]|подарун[оа]к[а-я]*|подар[оа]к[а-я]*|знижк[а-я]*|скидк[а-я]*)\b", re.IGNORECASE),
            re.compile(r"\b(акці[яїе]|акци[яие]|промо\b|бонус[а-я]*|ура\b|день\s+народження|день\s+рождения)\b", re.IGNORECASE),
        ],
        ["🥳", "😃", "🤟", "✨"],
    ),
    # 14. Подяка
    (
        "gratitude",
        [
            re.compile(r"\b(дяку[ює]|спасиб[оі]|вдячн[а-я]*|благодар[юя]|thanks|thank\s+you|thx|будь\s+ласка|пожалуйста)\b", re.IGNORECASE),
        ],
        ["🙏", "😊", "☺️", "❤️"],
    ),
    # 15. Привітання, знайомство, Арома
    (
        "greeting_intro",
        [
            re.compile(r"\b(привіт|привет|добрий\s+(день|ранок|вечір)|добрый\s+(день|вечер)|доброе\s+утро|віта[ює]|здравствуй[те]*|hello|hi|hey)\b", re.IGNORECASE),
            re.compile(r"\b(хто\s+ти|кто\s+ты|знайом[а-я]*|познакомим[ся]*|арома\b|aroma\b)\b", re.IGNORECASE),
        ],
        ["👋", "😊", "☺️", "🌿"],
    ),
    # 16. Питання, роздуми, цікавість, підкажи
    (
        "curious_question",
        [
            re.compile(r"\?"),
            re.compile(r"\b(підкажи|подскажи|розкажи|расскажи|як\s+саме|как\s+именно|чому|почему|що\s+таке|что\s+такое|цікав[оа-я]*|интересн[оа-я]*)\b", re.IGNORECASE),
        ],
        ["🤔", "🌿", "☝️", "😊"],
    ),
    # 17. Загальні ефірні олії / doTERRA
    (
        "oils_general",
        [
            re.compile(r"\b(ол[іе][яїею]|масл[оауе]|дотерра|doterra|ефірн[а-я]*|эфирн[а-я]*|крапл[іея]|капл[иейя]|суміш[іей]*|смес[ьия]|ролик|роллер)\b", re.IGNORECASE),
        ],
        ["🌿", "😊", "✨", "🌱"],
    ),
    # 18. Схвалення, згода, супер, клас
    (
        "approval_cool",
        [
            re.compile(r"\b(так\b|да\b|згод[аен]|домовились|договорились|круто|клас[но]*|супер|чудово|отлично|добре|хорошо|кайф|вау)\b", re.IGNORECASE),
        ],
        ["👍", "👌", "🤟", "😊"],
    ),
]


def detect_sticker_emojis_for_text(text: str, response_text: str = "") -> list[str]:
    """Визначає список релевантних емодзі стікерів на основі тексту запиту та/або відповіді.

    Аналізує ключові слова, тематику (сон, імунітет, енергія, догляд, цитруси, асортимент тощо),
    емоційне забарвлення та виключає недоречні або заборонні стікери.
    """
    combined = f"{text}\n{response_text}".lower().strip()
    if not combined:
        return list(SAFE_DEFAULT_EMOJIS)

    # 1. Перевіряємо сувору заборону (наприклад, не капати в очі/вуха).
    # Якщо це сувора заборона — вона має найвищий пріоритет.
    for pattern in _RULE_PROHIBITION:
        if pattern.search(combined):
            return ["👎"]

    matched_emojis: list[str] = []

    # 2. Перевіряємо всі тематичні правила за чергою
    for rule_name, patterns, emojis in STICKER_TOPIC_RULES:
        if rule_name == "prohibition":
            continue
        for pat in patterns:
            if pat.search(combined):
                for e in emojis:
                    if e not in matched_emojis:
                        matched_emojis.append(e)
                break

    if matched_emojis:
        return matched_emojis

    # Якщо нічого специфічного не знайшли, повертаємо безпечні позитивні емодзі
    return list(SAFE_DEFAULT_EMOJIS)


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
) -> tuple[bool, Optional[str], Optional[list[str]]]:
    """Визначає, чи є повідомлення повсякденною реплікою (привітання, подяка, реакція),
    на яку бот може відповісти стікером замість важкого звернення до LLM.

    Повертає:
        (should_reply_sticker, reply_text, preferred_emojis)
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
            "Рада допомогти! 🌿 Звертайся, якщо будуть ще запитання.",
            "Будь ласка! Завжди рада підказати про олії doTERRA 💚",
            "На здоров'я! 🌸 Якщо знадобиться ще порада — пиши!",
        ]
        return True, random.choice(replies), ["🙏", "😊", "☺️", "❤️"]

    if is_greeting(cleaned):
        replies = [
            "Привіт! 🌿 Мене звати Арома, я помічниця Наталії Котелянської у боті Aroma Assistant. Чим можу допомогти тобі сьогодні?",
            "Вітаю! 🌸 Я Арома, затишна помічниця Наталії. Запитуй будь-що про ефірні олії та продукти doTERRA!",
            "Привіт! 💛 Я Арома, помічниця Наталії Котелянської. З радістю підкажу про олії та продукцію doTERRA ✨",
        ]
        return True, random.choice(replies), ["👋", "😊", "☺️", "🌿"]

    if is_farewell(cleaned):
        replies = [
            "Бувай! Гарного та ароматного дня! 🌿",
            "До зустрічі! Нехай день буде спокійним та затишним 🌸",
        ]
        return True, random.choice(replies), ["👋", "😊", "☺️"]

    if is_reaction(cleaned):
        return True, None, ["👍", "👌", "🤟", "😊"]

    return False, None, None


def should_reply_to_user_sticker() -> bool:
    """Визначає, чи відповісти стікером на стікер від користувача."""
    if not _cached_file_ids:
        return False
    return random.random() < PROB_USER_STICKER


"""
Контакти спеціаліста та логіка виявлення ситуацій,
коли бот має проактивно запропонувати зв'язок з ним.

Використання:
    from src.agent.specialist import (
        SPECIALIST_CONTACT_BLOCK,
        is_consultation_query,
        is_low_context,
    )
"""

import re

# ---------------------------------------------------------------------------
# Контактні дані спеціаліста
# ---------------------------------------------------------------------------

SPECIALIST_NAME: str = "Наталія Котелянська"

SPECIALIST_LINKS: dict[str, str] = {
    "Instagram": "https://www.instagram.com/nkotelianska/",
    "Facebook":  "https://www.facebook.com/people/Nataliia-Kotelianska/100075977371849/",
    "Telegram":  "https://t.me/nkotelianskablog",
    "YouTube":   "https://www.youtube.com/channel/UCnI0gmLL6nUhjzyLB69KBkQ",
}

# Готовий блок для вставки в промпт та відповіді
SPECIALIST_CONTACT_BLOCK: str = (
    f"📩 Для персональної консультації, підбору продуктів або будь-яких "
    f"питань щодо послуг — зв'яжіться з {SPECIALIST_NAME} напряму:\n"
    f"📸 Instagram: {SPECIALIST_LINKS['Instagram']}\n"
    f"👥 Facebook: {SPECIALIST_LINKS['Facebook']}\n"
    f"💬 Telegram-канал: {SPECIALIST_LINKS['Telegram']}\n"
    f"▶️ YouTube: {SPECIALIST_LINKS['YouTube']}"
)

# Коротка версія для вбудовування в кінець відповіді LLM
SPECIALIST_SHORT_BLOCK: str = (
    f"\n\n🌿 Якщо хочеш персональну консультацію або маєш питання щодо "
    f"підбору продуктів — звертайся до {SPECIALIST_NAME}:\n"
    f"💬 Telegram: {SPECIALIST_LINKS['Telegram']}\n"
    f"📸 Instagram: {SPECIALIST_LINKS['Instagram']}"
)

# ---------------------------------------------------------------------------
# Скринінг: категорії скарг і червоні прапори
# ---------------------------------------------------------------------------

# Категорії проблем, з якими звертаються клієнти
COMPLAINT_CATEGORIES: tuple[str, ...] = (
    "сон", "стрес", "тривожність", "тривога", "біль", "шкіра", "жкт",
    "травлення", "шлунок", "кишечник", "імунітет", "застуда", "грип",
    "енергія", "втома", "головний біль", "мігрень", "гормони",
    "жіноче здоров'я", "суглоби", "м'язи", "дихання", "настрій",
    "концентрація", "пам'ять", "алергія", "шкірні висипання",
)

# Текст редіректу при наявності червоних прапорів (вагітність, ліки тощо)
RED_FLAG_REDIRECT_BLOCK: str = (
    f"🌿 У твоїй ситуації я не можу підібрати олію самостійно — "
    f"це важливо зробити разом зі спеціалістом, який знає всі деталі. "
    f"Рекомендую написати {SPECIALIST_NAME} — вона допоможе підібрати "
    f"безпечний варіант саме для тебе 💛\n"
    f"💬 Telegram: {SPECIALIST_LINKS['Telegram']}\n"
    f"📸 Instagram: {SPECIALIST_LINKS['Instagram']}"
)

EN_RED_FLAG_REDIRECT_BLOCK: str = (
    f"🌿 In your situation, I cannot recommend essential oils independently — "
    f"this should be done together with a specialist who understands all the details. "
    f"I recommend reaching out to {SPECIALIST_NAME} — she can help you select "
    f"a safe option tailored specifically to your needs 💛\n"
    f"💬 Telegram: {SPECIALIST_LINKS['Telegram']}\n"
    f"📸 Instagram: {SPECIALIST_LINKS['Instagram']}"
)

# Коти: для них є обмеження щодо ефірних олій — самостійних порад бот не дає, лише скеровує до Наталії.
CAT_REDIRECT_REPLY: str = (
    f"🐾 Для котиків є обмеження щодо використання ефірних олій, тому тут я не даю "
    f"самостійних порад. Щоб не нашкодити твоєму улюбленцю, будь ласка, спершу "
    f"проконсультуйся з {SPECIALIST_NAME} — вона підкаже, що буде безпечно саме для вашого котика 💛\n"
    f"💬 Telegram: {SPECIALIST_LINKS['Telegram']}\n"
    f"📸 Instagram: {SPECIALIST_LINKS['Instagram']}"
)

EN_CAT_REDIRECT_REPLY: str = (
    f"🐾 There are restrictions on using essential oils around cats, so I don't give "
    f"independent advice here. To keep your pet safe, please consult {SPECIALIST_NAME} first — "
    f"she will tell you what is safe for your cat 💛\n"
    f"💬 Telegram: {SPECIALIST_LINKS['Telegram']}\n"
    f"📸 Instagram: {SPECIALIST_LINKS['Instagram']}"
)

# Групові чати: хронічні захворювання не обговорюються публічно — людину скеровуємо
# в особисті повідомлення (опис ситуації та, за потреби, перенаправлення) або одразу до Наталії.
GROUP_CHRONIC_REPLY: str = (
    "🌿 Теми хронічних захворювань потребують індивідуального підходу, тому в груповому чаті "
    "я їх не обговорюю — це особиста інформація, яку краще розбирати наодинці.\n\n"
    "Обери зручний варіант:\n"
    "💬 напиши мені в особисті повідомлення й опиши свою ситуацію — якщо там є ознаки, "
    f"що потребують уваги спеціаліста, я одразу перенаправлю тебе до {SPECIALIST_NAME};\n"
    f"👩‍⚕️ або звернись напряму за консультацією до {SPECIALIST_NAME}:\n"
    f"💬 Telegram: {SPECIALIST_LINKS['Telegram']}\n"
    f"📸 Instagram: {SPECIALIST_LINKS['Instagram']}"
)

EN_GROUP_CHRONIC_REPLY: str = (
    "🌿 Chronic health conditions need an individual approach, so I don't discuss them in a group chat — "
    "this is personal information that is better handled privately.\n\n"
    "Please choose what suits you:\n"
    "💬 message me privately and describe your situation — if there are signs that need a specialist's "
    f"attention, I will redirect you to {SPECIALIST_NAME} right away;\n"
    f"👩‍⚕️ or contact {SPECIALIST_NAME} directly for a consultation:\n"
    f"💬 Telegram: {SPECIALIST_LINKS['Telegram']}\n"
    f"📸 Instagram: {SPECIALIST_LINKS['Instagram']}"
)

# Відповідь у приваті після переходу з групи (deep link /start chronic)
PRIVATE_CHRONIC_INTRO: str = (
    "🌿 Дуже рада, що ми можемо поспілкуватися в особистих повідомленнях 💛 Розкажи, будь ласка, що тебе турбує: "
    "який діагноз або стан, як давно триває, чи приймаєш ліки. "
    f"Якщо в твоїй ситуації будуть ознаки, що потребують уваги спеціаліста, я перенаправлю тебе до {SPECIALIST_NAME}."
)

EN_PRIVATE_CHRONIC_INTRO: str = (
    "🌿 I'm glad you wrote to me privately 💛 Please tell me what is bothering you: "
    "the diagnosis or condition, how long it has lasted, and whether you take any medication. "
    f"If your situation shows signs that need a specialist's attention, I will redirect you to {SPECIALIST_NAME}."
)

# Невідкладні стани: бот не радить олії і не відсилає до аромапрактика, а скеровує до швидкої.
# Номери та формулювання потрібно погодити з клієнткою (Q-08).
EMERGENCY_REPLY: str = (
    "🚨 Це може бути невідкладна ситуація. Будь ласка, негайно телефонуй 112 "
    "(або 103 — швидка допомога) і не чекай на пораду щодо олій.\n\n"
    "Якщо поруч є хтось дорослий — попроси допомогти. "
    "Олії в такій ситуації не застосовуй. Пиши мені після того, як отримаєш допомогу 💛"
)

EN_EMERGENCY_REPLY: str = (
    "🚨 This may be an emergency. Please call your local emergency number right now "
    "(112 in Ukraine, or 103 for an ambulance) and do not wait for advice about essential oils.\n\n"
    "If someone is nearby, ask them to help. Do not use any oils in this situation. "
    "Come back to me once you have received help 💛"
)

# Кризові повідомлення (думки про самоушкодження): без порад щодо олій.
# Контакти довіри потрібно погодити з клієнткою (Q-09).
CRISIS_REPLY: str = (
    "💛 Мені дуже шкода, що тобі зараз так важко. Ти не сама і не повинна проходити це наодинці.\n\n"
    "Будь ласка, зв'яжись із людьми, які можуть допомогти просто зараз: "
    "«Лайфлайн Україна» — 7333 (безкоштовно з мобільного, щодня), "
    "а якщо ти в небезпеці — 112.\n\n"
    "Якщо є близька людина, розкажи їй, як ти почуваєшся. Я поруч, але тут потрібна жива підтримка 🌿"
)

EN_CRISIS_REPLY: str = (
    "💛 I'm really sorry you're feeling this way. You don't have to go through this alone.\n\n"
    "Please reach out to someone who can help right now: Lifeline Ukraine — 7333 "
    "(free from a mobile phone), or 112 if you are in danger.\n\n"
    "If there is someone close to you, tell them how you feel. I'm here, but you deserve real human support 🌿"
)

# ---------------------------------------------------------------------------
# Медичний дисклеймер
# ---------------------------------------------------------------------------

# Фінальний текст, що гарантовано додається до КОЖНОЇ відповіді бота.
# Не покладайся на LLM — він додається хардкодом у service.py.
MEDICAL_DISCLAIMER: str = (
    "\n\nℹ️ "
    "Ця інформація має ознайомлювальний характер і не є медичною консультацією. "
    "Перед застосуванням проконсультуйтеся з лікарем."
)

EN_MEDICAL_DISCLAIMER: str = (
    "\n\nℹ️ "
    "This information is for educational purposes only and does not constitute medical advice. "
    "Consult a qualified healthcare professional before use."
)


def get_disclaimer_for_text(text: str) -> str:
    """Повертає відповідний дисклеймер (UK або EN) залежно від наявності кирилиці в тексті."""
    import re
    has_cyrillic = bool(re.search(r'[а-яА-ЯіїєґІЇЄҐ]', text))
    return MEDICAL_DISCLAIMER if has_cyrillic else EN_MEDICAL_DISCLAIMER


# ---------------------------------------------------------------------------
# Детектор питань про персону / образ помічниці Ароми
# ---------------------------------------------------------------------------

def is_persona_query(text: str) -> bool:
    """Визначає, чи є запит питанням про саму помічницю, її ім'я, образ, розробників або улюблені олії."""
    import re
    low = text.lower()
    return bool(re.search(
        r"\b(хто\s+ти|кто\s+ты|як\s+тебе\s+звати|как\s+тебя\s+зовут|хто\s+ви|кто\s+вы|"
        r"розкажи\s+про\s+себе|расскажи\s+о\s+себе|який\s+твій\s+образ|як\s+ти\s+виглядаєш|как\s+ты\s+выглядишь|"
        r"(най)?улюблен\w*\s+(масл\w+|ол\w+|аромат\w*)|(най)?любим\w*\s+(масл\w+|аромат\w*)|favorite\s+oil|"
        r"аріна|арину|арина|разработчик\w*|розробниц\w*|who\s+are\s+you|what\s+is\s+your\s+name)\b",
        low
    ))


# Паттерни для повсякденних вітань, подяк та загальних мета-питань
_CASUAL_CHAT_REGEX = re.compile(
    r"^[\s\W]*("
    r"привіт|добрий\s+день|доброго\s+дня|добрий\s+ранок|доброго\s+ранку|добрий\s+вечір|доброго\s+вечора|"
    r"здравствуйте|привет|хай|хеллоу|салют|hello|hi|hey|good\s+morning|good\s+evening|"
    r"дякую|дякуємо|дяка|спасибі|спасибо|благодарю|thanks|thank\s+you|"
    r"до\s+побачення|бувай|бувайте|пока|прощавай|bye|goodbye|have\s+a\s+nice\s+day|"
    r"гарного\s+дня|чудового\s+дня|надобраніч|спокійної\s+ночі|доброї\s+ночі|"
    r"як\s+справи|як\s+ти|как\s+дела|how\s+are\s+you|"
    r"що\s+ти\s+вмієш|чим\s+ти\s+допомагаєш|чим\s+можеш\s+допомогти|як\s+користуватися|що\s+ти\s+робиш|what\s+can\s+you\s+do"
    r")[\s\W]*$",
    re.IGNORECASE,
)

# Паттерни для виявлення рекомендацій щодо застосування олій, дозувань, протоколів (UK, RU, EN)
_APPLICATION_REGEX = re.compile(
    r"("
    # Способи застосування, нанесення, дозування
    r"\bзастосув\w*|\bприменен\w*|\bнанесен\w*|\bнаносити\b|\bнанесіть\b|\bнаносить\b|\bнанесите\b"
    r"|\bдозуван\w*|\bдозировк\w*|\bкрапл\w*|\bкапл\w*|\bкапель\b|\bкрапель\b"
    r"|\bрозведен\w*|\bрозводити\b|\bразведен\w*|\bразбавлять\b"
    r"|\bдифузор\w*|\bдиффузор\w*|\bдифузі\w*|\bдиффузи\w*|\bаромаламп\w*"
    r"|\bінгаляц\w*|\bингаляц\w*|\bвдихан\w*|\bвдыхан\w*"
    r"|\bвсередину\b|\bвнутрь\b|прийом\w*\s+всередину|прием\w*\s+внутрь"
    r"|\bрослинн\w+\s+капсул\w*|\bвегетаріанськ\w+\s+капсул\w*|\bsoftgel\w*|\bveggie\s+caps?\b"
    r"|\bпротокол\w*|\bсимфоні\w+\s+клітин\w*|\bсимфони\w+\s+клеток\w*"
    r"|\bбазов\w+\s+олі\w*|\bбазов\w+\s+масл\w*|\bфракціонован\w*|\bфракционирован\w*"
    r"|\bпротипоказан\w*|\bпротивопоказан\w*|\bзастережен\w*|\bпредостережен\w*"
    r"|\bчутливіст\w+\s+шкір\w*|\bчувствительност\w+\s+кож\w*"
    # English terms
    r"|\bapply\b|\bapplied\b|\bapplying\b|\btopical\w*|\binternal(ly)?\b|\bingest\w*"
    r"|\bdiffus\w*|\baromatic(ally)?\b|\bdrops?\b|\bdilut\w*|\bdosage\w*|\bdose\w*"
    r"|\bprotocol\w*|\bcontraindicat\w*|\bprecaution\w*|\bsafety\s+guideline\w*"
    r")",
    re.IGNORECASE,
)


def should_include_medical_disclaimer(
    response_text: str,
    user_query: str = "",
    screening_mode: str | None = None,
    conversation_context: str | None = None,
) -> bool:
    """Визначає, чи потрібен медичний дисклеймер у відповіді бота.

    Дисклеймер додається коли:
    1. Виявлено червоний прапор (ризики/протипоказання) або скринінг у режимі 'red_flag'.
    2. Є скарга на здоров'я / симптоми або активний скринінг стану ('active').
    3. У тексті відповіді чи запиту обговорюється застосування олій, дозування,
       протоколи (напр. Симфонія клітин), нанесення на шкіру, дифузія, вживання всередину,
       застереження або протипоказання.

    Дисклеймер НЕ додається коли:
    - Це звичайна повсякденна розмова (привітання, подяка, бувай, як справи).
    - Питання про саму помічницю Арому, її образ, розробників (Аріну) чи улюблене масло.
    - Загальні мета-питання про бота («хто ти?», «що ти вмієш?», «як користуватися?»).
    - Суто контактні запити чи ціни без медичних порад чи застосування.
    """
    # 1. Червоні прапори: абсолютний пріоритет безпеки — завжди з дисклеймером
    if (
        screening_mode == "red_flag"
        or has_red_flags(user_query)
        or has_red_flags(response_text)
        or (screening_mode == "active" and bool(conversation_context) and has_red_flags(extract_user_text_from_context(conversation_context)))
    ):
        return True

    # 2. Активний скринінг симптомів або скарга на здоров'я — завжди з дисклеймером
    if (
        screening_mode == "active"
        or is_health_complaint_query(user_query)
    ):
        return True

    # 3. Питання про персону / образ / розробницю Аріну / улюблені олії помічниці
    # (навіть якщо у відповіді Арома згадує крапельку лайму — це її образ і не медична рекомендація)
    if user_query and is_persona_query(user_query):
        return False

    # 4. Повсякденні вітання, подяка, коротка розмова
    if user_query and _CASUAL_CHAT_REGEX.match(user_query.strip()):
        return False

    # 5. Чистий запит контактів / консультації / цін Наталії (без обговорення рецептів чи застосування)
    if user_query and is_consultation_query(user_query):
        if not _APPLICATION_REGEX.search(response_text):
            return False

    # 6. Перевіряємо наявність інструкцій із застосування, дозувань, протоколів або застережень
    if _APPLICATION_REGEX.search(response_text) or _APPLICATION_REGEX.search(user_query):
        return True

    # За замовчуванням для загальних запитів без рекомендацій застосування
    return False


# ---------------------------------------------------------------------------
# Детектор запитів про консультацію / послуги / покупку
# ---------------------------------------------------------------------------

# Слова, що чітко вказують: людина хоче консультацію або послугу,
# а не відповідь з бази знань.
_CONSULTATION_KEYWORDS: tuple[str, ...] = (
    # Ціна / покупка
    "скільки коштує", "ціна", "прайс", "вартість", "де купити",
    "як купити", "де замовити", "як замовити", "замовити", "придбати",
    # Консультація
    "хочу консультацію", "запишіть мене", "записатись", "запис",
    "особиста консультація", "онлайн консультація", "консультація",
    "зв'язатись", "контакти", "написати", "як зв'язатись",
    # Послуги
    "стати партнером", "партнерство", "реєстрація", "вступити",
    "вступ до команди", "доєднатись до команди",
    # Підбір
    "підбери мені", "підібрати", "порекомендуй персонально",
    "індивідуально для мене",
)


def is_consultation_query(text: str) -> bool:
    """Повертає True, якщо запит явно про консультацію, ціни або послуги.

    Args:
        text: текст повідомлення користувача.

    Returns:
        True якщо знайдено ключове слово-тригер.
    """
    lower = text.lower()
    return any(kw in lower for kw in _CONSULTATION_KEYWORDS)


# ---------------------------------------------------------------------------
# Детектор низького контексту (RAG не знайшов достатньо даних)
# ---------------------------------------------------------------------------

# Якщо знайдено менше цього числа чанків — вважаємо контекст недостатнім
LOW_CONTEXT_THRESHOLD: int = 2


def is_low_context(chunks: list[dict]) -> bool:
    """Повертає True, якщо RAG знайшов замало релевантних чанків.

    Args:
        chunks: список чанків, повернутих search_chunks.

    Returns:
        True якщо кількість чанків нижче LOW_CONTEXT_THRESHOLD.
    """
    return len(chunks) < LOW_CONTEXT_THRESHOLD


# ---------------------------------------------------------------------------
# Детектор запитів-скарг на здоров'я (тригер для скринінгу)
# ---------------------------------------------------------------------------

# Ключові слова, що вказують на скаргу/симптом, а не загальне питання
_HEALTH_COMPLAINT_KEYWORDS: tuple[str, ...] = (
    # Симптоми
    "не можу спати", "не можу заснути", "заснути", "засинаю", "не сплю", "не спиться",
    "не могу уснуть", "не могу спать", "не спится", "can't sleep", "cant sleep", "trouble sleeping",
    "погано сплю", "безсоння", "безсонн", "тривога", "тривожність",
    "стрес", "паніка", "панічні атаки", "депресія", "поганий настрій",
    "болить", "біль", "болі", "набряки", "запалення", "свербіж",
    "висипання", "акне", "прищі", "екзема", "псоріаз",
    "втома", "немає сил", "хронічна втома", "немає енергії",
    "проблеми з травленням", "здуття", "запор", "пронос", "нудота",
    "застуда", "грип", "кашель", "нежить", "імунітет",
    "головний біль", "мігрень", "запаморочення",
    "гормони", "місячні", "клімакс", "пмс",
    # Запити на підбір під проблему
    "що допоможе від", "що взяти від", "що радите від",
    "підібрати від", "порекомендуй від", "яка олія від",
    "яке масло від", "масло від", "олія від",
    "допоможіть з", "допоможе при", "при болі", "при стресі",
    "при безсонні", "при тривозі", "при застуді",
    # Загальний підбір під ситуацію
    "підібрати масло", "підібрати олію", "хочу підібрати",
    "порадьте масло", "порадьте олію", "що підійде для",
)

# Ключові слова-«червоні прапори» — ситуації, коли бот НЕ підбирає самостійно
RED_FLAG_KEYWORDS: tuple[str, ...] = (
    # Вагітність / лактація
    "вагітна", "вагітність", "годую груддю", "лактація", "годуючій",
    "годуюча мама", "мама годує", "грудне вигодовування",
    # Діти більше не є червоним прапором: ефірні олії можна використовувати з 0 років,
    # усе залежить від концентрації продукції (див. правила в prompt.py).
    # Хронічні хвороби та невідкладні стани
    "епілепсія", "епілептик", "астма", "астматик",
    "тиск", "гіпертонія", "гіпотонія", "серцева недостатність",
    "аритмія", "цукровий діабет", "діабет",
    "онкологія", "рак", "хіміотерап", "інфаркт", "інсульт", "судоми",
    "ниркова недостатність", "печінкова недостатність", "кровотеча",
    # Ліки
    "приймаю ліки", "п'ю ліки", "антидепресанти", "антикоагулянти",
    "варфарин", "аспірин", "кроворозріджувальні", "знеболювальні",
    "антибіотики постійно", "гормональні таблетки",
    # Чутлива шкіра / алергія / невідкладні реакції
    "сильна алергія", "анафілакт", "набряк квінке", "дуже чутлива шкіра",
    "хімічна чутливість",
    # Похилий вік
    "пенсіонер", "пенсіонерці", "80 років", "90 років", "70 років",
    "старенька", "старенький", "бабуся", "дідусь",
)



import re
import unicodedata

# Регулярні вирази для детермінованої детекції червоних прапорів (UK / RU / EN)
_RED_FLAG_REGEX = re.compile(
    r"("
    # Вагітність та лактація
    r"\bвагітн\w*|\bгодую\w*|\bлактац\w*|грудн\w+\s+вигодовуван\w*"
    r"|\bберемен\w*|\bлактац\w*|грудн\w+\s+вскармливан\w*|кормл\w+\s+груд\w*"
    r"|\bpregnan\w*|\blactat\w*|\bbreastfeed\w*|nursing\s+m\w*"
    # Діти та немовлята навмисно НЕ входять до червоних прапорів (олії можна з 0 років).
    # Хронічні та невідкладні стани
    r"|\bастм\w*|\bепілеп\w*|\bгіпертон\w*|\bгіпотон\w*|\bаритмі\w*|\bдіабет\w*|\bінфаркт\w*|\bінсульт\w*|\bсудом\w*|\bкровотеч\w*"
    r"|\bэпилеп\w*|\bгипертон\w*|\bгипотон\w*|\bаритми\w*|\bдиабет\w*|\bинфаркт\w*|\bинсульт\w*|\bсудорог\w*|\bкровотечен\w*|\bдавлен\w*"
    r"|\basthm\w*|\bepilep\w*|\bhypertens\w*|\bdiabet\w*|\binfarct\w*|\bstroke\w*|\bseizur\w*|\bconvuls\w*|\bbleeding"
    # Серце / органи / онкологія
    r"|серцев\w+\s+недостатн\w*|\bонколог\w*|\bрак\b|\bхіміотерап\w*|нирков\w+\s+недостатн\w*|печінков\w+\s+недостатн\w*"
    r"|сердечн\w+\s+недостаточн\w*|\bхимиотерап\w*|почечн\w+\s+недостаточн\w*|печеночн\w+\s+недостаточн\w*"
    r"|heart\s+failure|\boncolog\w*|\bcancer\b|\bchemo\w*|kidney\s+failure|liver\s+failure|high\s+blood\s+pressure"
    # Ліки
    r"|приймаю\s+ліки|п'ю\s+ліки|\bантидепресант\w*|\bантикоагулянт\w*|\bварфарин\w*|\bаспірин\w*|кроворозрідж\w*|знеболювальн\w*|гормональн\w+\s+таблетк\w*"
    r"|принимаю\s+лекарств\w*|пью\s+лекарств\w*|\bантидепрессант\w*|\bаспирин\w*|кроворазжижающ\w*|обезболивающ\w*"
    r"|\bmedicat\w*|\bantidepress\w*|\banticoagulant\w*|\bwarfarin\b|\baspirin\b|blood\s+thinner\w*|\bpainkiller\w*"
    # Алергії / анафілаксія
    r"|\bанафілакт\w*|набряк\s+квінке|сильн\w+\s+алергі\w*|хімічн\w+\s+чутливіст\w*"
    r"|\bанафилакт\w*|отек\s+квинке|сильн\w+\s+аллерги\w*|химическ\w+\s+чувствительност\w*"
    r"|\banaphyla\w*|quincke|\bsevere\s+allerg\w*"
    # Похилий вік
    r"|\bпенсіонер\w*|\bбабус\w*|\bдідус\w*|\b(7[5-9]|[89]\d)\s*рок\w*"
    r"|\bпенсионер\w*|\bбабушк\w*|\bдедушк\w*|\b(7[5-9]|[89]\d)\s*лет"
    r"|\belderly\b|\bsenior\b|\bgrandm\w*|\bgrandp\w*|\b(7[5-9]|[89]\d)\s*years?\s*old"
    # Ліки, що вказують на хронічний стан
    r"|\bінсулін\w*|\bинсулин\w*|\binsulin\b|\bметформін\w*|\bметформин\w*|\bmetformin\b"
    r"|п'ю\s+таблетк\w*|пью\s+таблетк\w*|\bприйма\w+\s+(?:таблетк\w*|препарат\w*)"
    # Транслітерація
    r"|\bvag?h?itn\w*|\bberemenn\w*"
    r")",
    re.IGNORECASE,
)

# Невідкладні стани: потрібна швидка, а не аромапрактик
_EMERGENCY_REGEX = re.compile(
    r"("
    r"\bкровотеч\w*|\bінфаркт\w*|\bинфаркт\w*|\bінсульт\w*|\bинсульт\w*|\bсудом\w*|\bсудорог\w*"
    r"|\bанафілакт\w*|\bанафилакт\w*|набряк\w*\s+(?:обличч\w*|горл\w*|язик\w*|губ\w*)"
    r"|отек\w*\s+(?:лица|горла|языка|губ)|\bпроковтн\w*|\bпроглот\w*"
    r"|не\s+можу\s+дихати|\bзадихаю\w*|не\s+могу\s+дышать|\bзадыхаю\w*"
    r"|втрат\w+\s+свідомост\w*|потерял\w*\s+сознан\w*"
    r"|\bswallowed\b|can'?t\s+breathe|\bchoking\b|\bunconscious\b|\banaphyla\w*"
    r"|heart\s+attack|\bseizure\w*|\bbleeding\b"
    r")",
    re.IGNORECASE,
)

# Кризові повідомлення: думки про смерть або самоушкодження
_CRISIS_REGEX = re.compile(
    r"("
    r"не\s+хочу\s+(?:більше\s+)?жит\w*|не\s+хочу\s+жить|хочу\s+померти|хочу\s+умереть"
    r"|вбити\s+себе|покінчити\s+з\s+собою|убить\s+себя|покончить\s+с\s+собой"
    r"|\bсуїцид\w*|\bсуицид\w*|\bсамогубств\w*|\bсамоубийств\w*"
    r"|(?:нашкодити|зашкодити|навредить)\s+(?:собі|себе)|(?:собі|себе)\s+(?:нашкодити|зашкодити|навредить)"
    r"|\bkill\s+myself|\bsuicid\w*|want\s+to\s+die|hurt\s+myself|harm\s+myself|end\s+my\s+life"
    r")",
    re.IGNORECASE,
)

_INVISIBLE_CHARS = re.compile("[\u200b\u200c\u200d\u2060\ufeff\u00ad]")
_SPACED_LETTERS = re.compile(r"(?<!\w)(?:\w\s){3,}\w(?!\w)")
_CYRILLIC_LETTER = re.compile("[а-яіїєґ]")
_LATIN_TO_CYRILLIC = str.maketrans("iaoepcxy", "іаоерсху")


def _normalize_for_detection(text: str) -> str:
    """Нормалізує текст перед пошуком тригерів: NFKC, невидимі символи, апострофи, регістр,
    латинські двійники в кириличних словах («вагiтна») та розряджені слова («в а г і т н а»)."""
    s = unicodedata.normalize("NFKC", text)
    s = _INVISIBLE_CHARS.sub("", s)
    s = s.replace("’", "'").replace("ʼ", "'").replace("`", "'").lower()
    s = re.sub(r"\w+", lambda m: m.group().translate(_LATIN_TO_CYRILLIC)
               if _CYRILLIC_LETTER.search(m.group()) else m.group(), s)
    return _SPACED_LETTERS.sub(lambda m: re.sub(r"\s", "", m.group()), s)

# Шаблони явних заперечень протипоказань (наприклад: "не вагітна", "без ліків", "діабету немає", "немає астми").
# Їх необхідно нейтралізувати перед пошуком червоних прапорів, щоб заперечення не вважалося прапором.
_NEGATED_RED_FLAGS = re.compile(
    r"("
    # 1. Заперечення перед словом (не / немає / без / не маю / не приймаю / не п'ю / not / no / without ...)
    r"\b(?:не\s+(?:є\s+|маю\s+|прийма\w*\s+|п['’`]?ю\s+|вжива\w*\s+|колю\s+|страждаю\s+на\s+|хворію\s+на\s+)?|"
    r"немає\s+|нема\s+|нет\s+|без\s+|"
    r"not\s+|no\s+|not\s+a\s+|not\s+taking\s+(?:any\s+)?|without\s+)"
    r"(?:хронічн\w*\s+|цукров\w*\s+|проблем\s+з\s+|жодних\s+|ніяких\s+)?(?:\w+\s+)?"
    r"(?:вагітн\w*|годуван\w*|годую\w*|лактац\w*|беремен\w*|pregnant|pregnancy|breastfeed\w*|nursing|"
    r"діабет\w*|диабет\w*|diabet\w*|тиск\w*|давлен\w*|гіпертон\w*|гіпотон\w*|гипертон\w*|гипотон\w*|hypertens\w*|blood\s+pressure|"
    r"астм\w*|asthm\w*|епілеп\w*|эпилеп\w*|epilep\w*|судом\w*|судорог\w*|seizur\w*|"
    r"алергі\w*|аллерги\w*|allerg\w*|"
    r"ліків|ліки|ліках|таблет\w*|препарат\w*|медикамент\w*|лекарств\w*|medicat\w*|meds|"
    r"хвороб\w*|захворюван\w*|болезн\w*|chronic\s+disease\w*|дитин\w*|діт\w*|ребен\w*|дет\w*|child\w*|kids?)\b"
    # 2. Заперечення або норма після слова (... немає / відсутній / в нормі / не приймаю / none / normal)
    r"|"
    r"\b(?:вагітност\w*|вагітна|лактаці\w*|беременност\w*|беременна|pregnancy|"
    r"діабет\w*|диабет\w*|diabetes|тиск\w*|давлен\w*|гіпертоні\w*|гипертони\w*|blood\s+pressure|"
    r"астм\w*|астма|asthma|епілепсі\w*|эпилепси\w*|epilepsy|судом\w*|судорог\w*|seizures?|"
    r"алергі\w*|аллерги\w*|allergies|ліків|ліки|таблет\w*|препарат\w*|медикамент\w*|лекарств\w*|"
    r"хвороб\w*|захворюван\w*|болезн\w*|дитин\w*|діт\w*|ребен\w*|дет\w*)\s+"
    r"(?:не\s+прийма\w*|не\s+п['’`]?ю|не\s+вжива\w*|не\s+колю|не\s+маю|не\s+страждаю|немає|нема|нет|"
    r"відсутн\w*|отсутству\w*|в\s+нормі|у\s+нормі|нормальн\w*|стабільн\w*|none|normal)\b"
    # 3. Додаткові ідіоматичні вирази (діабетик, астматик, дорослий тощо)
    r"|"
    r"\b(?:не\s+діабетик|не\s+диабетик|not\s+diabetic|не\s+астматик|not\s+asthmatic|"
    r"не\s+епілептик|не\s+гіпертонік|не\s+алергік|not\s+allergic|"
    r"я\s+доросла|я\s+дорослий|для\s+дорослого|для\s+дорослих|для\s+себе|"
    r"не\s+для\s+дитини|не\s+для\s+дітей|дитини\s+немає|дітей\s+немає|"
    r"я\s+взрослый|я\s+взрослая|для\s+взрослого|for\s+(?:an?\s+)?adult|for\s+myself)\b"
    # 4. Універсальні патерни: слово + немає / немає + слово
    r"|"
    r"\b\w+\s+(?:немає|нема|нет)\b|\b(?:немає|нема|нет)\s+\w+\b"
    r")",
    re.IGNORECASE,
)


# Додаткові основи слів скарг (відмінки, російська, англійська) з межею слова на початку
_COMPLAINT_EXTRA_REGEX = re.compile(
    r"\b(?:кашл\w*|тривог\w*|тривож\w*|нервую\w*|напруг\w*|втомил\w*|втомл\w*|печі[яюїє]\b"
    r"|колік\w*|діаре\w*|нудит\w*|температур\w*|болит\b|бессонн\w*|тревог\w*|устал\w*|насморк\w*"
    r"|tired\b|stress\w*|cough\w*|anxi\w*|insomnia|headache|migraine|sore\s+throat|stomach\s*ache"
    r"|head\s+hurts)",
    re.IGNORECASE,
)


def extract_user_text_from_context(context: str) -> str:
    """Витягує тільки репліки користувача з діалогового контексту, ігноруючи запитання бота."""
    if not context:
        return ""
    user_lines = []
    is_user = False
    for line in context.splitlines():
        if line.startswith("Користувач:"):
            is_user = True
            user_lines.append(line[len("Користувач:"):].strip())
        elif line.startswith("Бот:"):
            is_user = False
        elif is_user:
            user_lines.append(line.strip())
    return " ".join(user_lines)


def is_health_complaint_query(text: str) -> bool:
    """Повертає True, якщо запит схожий на скаргу про здоров'я або запит підбору.

    Тригер для увімкнення скринінгу в системному промпті.

    Args:
        text: текст повідомлення користувача.

    Returns:
        True якщо знайдено ключове слово-тригер скарги/симптому.
    """
    lower = _normalize_for_detection(text)
    # «стресостійкість» — не скарга, хоча містить основу «стрес»
    lower = re.sub(r"стресо?стійк\w*|стрессоустойчив\w*", "", lower)
    return any(kw in lower for kw in _HEALTH_COMPLAINT_KEYWORDS) or bool(_COMPLAINT_EXTRA_REGEX.search(lower))


def is_emergency(text: str) -> bool:
    """True, якщо повідомлення описує невідкладний стан (потрібна швидка допомога)."""
    return bool(text) and bool(_EMERGENCY_REGEX.search(_normalize_for_detection(text)))


def is_crisis(text: str) -> bool:
    """True, якщо повідомлення містить думки про смерть чи самоушкодження."""
    return bool(text) and bool(_CRISIS_REGEX.search(_normalize_for_detection(text)))


def has_red_flags(text: str) -> bool:
    """Повертає True, якщо в тексті є ознаки протипоказань (червоні прапори).
    Працює детерміновано за основами слів трьома мовами (UK, RU, EN),
    враховуючи заперечення (наприклад «не вагітна» або «без ліків»).

    Args:
        text: текст повідомлення користувача (може бути діалог).

    Returns:
        True якщо знайдено червоний прапор.
    """
    if not text:
        return False
    lower = _normalize_for_detection(text)
    if _EMERGENCY_REGEX.search(lower) or _CRISIS_REGEX.search(lower):
        return True
    cleaned = _NEGATED_RED_FLAGS.sub("", lower)
    if _RED_FLAG_REGEX.search(cleaned):
        return True
    # Ключові слова збігаються лише з початку слова: «рак» не повинен спрацьовувати на «Дракон»
    # (окремо слово «рак» уже покрите регулярним виразом з межею слова).
    return any(
        re.search(r"(?<!\w)" + re.escape(kw), cleaned)
        for kw in RED_FLAG_KEYWORDS
        if kw != "рак"
    )



# ---------------------------------------------------------------------------
# Хронічні захворювання (для групових чатів)
# ---------------------------------------------------------------------------

_CHRONIC_REGEX = re.compile(
    r"("
    # Прямі згадки «хронічне захворювання / хвороба / стан»
    r"хронічн\w*\s+(?:\w+\s+)?(?:захворюван\w*|хвороб\w*|недуг\w*|патолог\w*|стан\w*|гастрит\w*|бронхіт\w*"
    r"|панкреатит\w*|цистит\w*|гепатит\w*|коліт\w*|синусит\w*|тонзиліт\w*|дерматит\w*|пієлонефрит\w*)"
    r"|хроническ\w*\s+(?:\w+\s+)?(?:заболевани\w*|болезн\w*|недуг\w*|патологи\w*|гастрит\w*|бронхит\w*|панкреатит\w*)"
    r"|\bchronic\s+(?:\w+\s+)?(?:diseases?|illness\w*|conditions?|disorders?|gastritis|bronchitis|pancreatitis)"
    # Поширені хронічні діагнози (UK / RU / EN)
    r"|\bдіабет\w*|\bдиабет\w*|\bdiabet\w*|\bінсулін\w*|\bинсулин\w*"
    r"|\bастм\w*|\basthm\w*|\bхозл\b|\bcopd\b"
    r"|\bгіпертон\w*|\bгипертон\w*|\bhypertens\w*|\bгіпотон\w*|\bгипотон\w*|\bаритмі\w*|\bаритми\w*"
    r"|\bепілеп\w*|\bэпилеп\w*|\bepilep\w*"
    r"|серцев\w+\s+недостатн\w*|нирков\w+\s+недостатн\w*|печінков\w+\s+недостатн\w*"
    r"|сердечн\w+\s+недостаточн\w*|почечн\w+\s+недостаточн\w*|печеночн\w+\s+недостаточн\w*"
    r"|\bонколог\w*|\bрак\b|\bcancer\b|\boncolog\w*"
    r"|\bпсоріаз\w*|\bпсориаз\w*|\bекзем\w*|\bэкзем\w*|\barthritis\b|\bартрит\w*|\bартроз\w*"
    r"|\bгепатит\w*|\bрозсіян\w+\s+склероз\w*|\bрассеян\w+\s+склероз\w*|\bмультиплекс\w*"
    r"|\bгіпотиреоз\w*|\bгипотиреоз\w*|\bхашимото\b|\bтиреоїдит\w*|\bтиреоидит\w*|\bвіл\b|\bвич\b|\bhiv\b"
    r"|\bвиразк\w*|\bязв\w+\s+(?:желудк\w*|кишечник\w*)|\bхвороб\w+\s+крон\w*|\bcrohn\w*"
    r")",
    re.IGNORECASE,
)


def has_chronic_condition(text: str) -> bool:
    """True, якщо людина пише про хронічне захворювання (з урахуванням заперечень на кшталт «діабету немає»).

    Використовується в групових чатах: такі теми не обговорюються публічно — людину скеровують
    в особисті повідомлення або до Наталії Котелянської.
    """
    if not text:
        return False
    lower = _normalize_for_detection(text)
    cleaned = _NEGATED_RED_FLAGS.sub("", lower)
    return bool(_CHRONIC_REGEX.search(cleaned))


# ---------------------------------------------------------------------------
# Тварини: собаки — майже всі олії; коти — обмеження та консультація Наталії
# ---------------------------------------------------------------------------

_CAT_REGEX = re.compile(
    r"("
    r"\bкіт(?:а|у|ом|і|ові|ів|ам|ами|ах)?\b|\bкот(?:а|у|ом|ові|ів|ам|ами|ах)?\b"
    r"|\bкотик\w*|\bкотів\b|\bкотяч\w*|\bкотен\w*|\bкотят\w*|\bкошен\w*|\bкошеня\w*"
    r"|\bкішк\w*|\bкіш(?:ці|ок|ками|ках)\b|\bкошк\w*|\bкошач\w*"
    r"|\bcats?\b|\bkitten\w*|\bkitty\b|\bkitties\b|\bfeline\w*"
    r")",
    re.IGNORECASE,
)

_PET_REGEX = re.compile(
    r"("
    r"\bсобак\w*|\bсобац\w*|\bсобач\w*|\bпес(?:а|у|ом|і|ик\w*|ів)?\b|\bпсів\b|\bпсом\b|\bщен(?:ят\w*|ик\w*|я\b)|\bцуцен\w*"
    r"|\bтварин\w*|\bулюбленц\w*|\bпитомц\w*|\bживотн\w*|\bпітомц\w*"
    r"|\bdogs?\b|\bpupp(?:y|ies)\b|\bpets?\b|\banimals?\b"
    r")",
    re.IGNORECASE,
)


def has_cat_mention(text: str) -> bool:
    """True, якщо в повідомленні йдеться про котів/кішок (для них є обмеження — лише консультація Наталії)."""
    if not text:
        return False
    return bool(_CAT_REGEX.search(_normalize_for_detection(text)))


def is_pet_query(text: str) -> bool:
    """True, якщо запит стосується домашніх тварин (собак, інших улюбленців)."""
    if not text:
        return False
    return bool(_PET_REGEX.search(_normalize_for_detection(text)))

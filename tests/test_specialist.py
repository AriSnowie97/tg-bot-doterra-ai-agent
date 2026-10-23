"""
Unit-тести для скринінгу симптомів, виявлення червоних прапорів та медичної безпеки.
"""

import pytest
from src.agent.specialist import (
    is_health_complaint_query,
    has_red_flags,
    is_consultation_query,
    MEDICAL_DISCLAIMER,
    RED_FLAG_KEYWORDS,
)


class TestSpecialistScreening:
    """Тестування виявлення медичних скарг та червоних прапорів."""

    @pytest.mark.parametrize("query", [
        "У мене сильно болить голова і мігрень",
        "Що допоможе від безсоння та тривожності?",
        "Яка олія підійде від стресу на роботі?",
        "Порадьте масло від застуди та кашлю",
        "Що прийняти при болі в м'язах?",
    ])
    def test_detects_health_complaints(self, query: str):
        assert is_health_complaint_query(query) is True

    @pytest.mark.parametrize("query", [
        "Який склад суміші On Guard?",
        "Скільки крапель капати в дифузор?",
        "Розкажи про історію компанії doTERRA",
        "Як видобувають олію ладану?",
    ])
    def test_ignores_general_questions_as_complaints(self, query: str):
        assert is_health_complaint_query(query) is False

    @pytest.mark.parametrize("query", [
        "Я вагітна на 6 місяці, чи можна м'яту?",
        "Дитині 2 місяці, що можна від застуди?",
        "У моєї бабусі гіпертонія та високий тиск",
        "Приймаю антидепресанти та ліки щодня",
        "У мене епілепсія та астма",
    ])
    def test_detects_red_flags_triggers(self, query: str):
        assert has_red_flags(query) is True

    @pytest.mark.parametrize("query", [
        "Чи можна додавати лимон у воду дорослому?",
        "Який термін придатності у лаванди?",
        "Де росте чайне дерево?",
    ])
    def test_safe_queries_have_no_red_flags(self, query: str):
        assert has_red_flags(query) is False

    def test_medical_disclaimer_content(self):
        assert "не є медичною консультацією" in MEDICAL_DISCLAIMER
        assert "проконсультуйтеся з лікарем" in MEDICAL_DISCLAIMER

    def test_en_medical_disclaimer_content(self):
        from src.agent.specialist import EN_MEDICAL_DISCLAIMER
        assert "medical advice" in EN_MEDICAL_DISCLAIMER
        assert "healthcare professional" in EN_MEDICAL_DISCLAIMER

    def test_get_disclaimer_for_text(self):
        from src.agent.specialist import get_disclaimer_for_text, EN_MEDICAL_DISCLAIMER
        # Український текст містить кирилицю
        ua_text = "Лаванда чудово підходить для релаксації та спокійного сну."
        assert get_disclaimer_for_text(ua_text) == MEDICAL_DISCLAIMER

        # Англійський текст не містить кирилиці
        en_text = "Lavender is wonderful for relaxation and restful sleep."
        assert get_disclaimer_for_text(en_text) == EN_MEDICAL_DISCLAIMER

    @pytest.mark.parametrize("query,expected", [
        ("What is lavender?", True),
        ("Hello, how to use peppermint oil?", True),
        ("Can I take lemon internally?", True),
        ("Is peppermint safe?", True),
        ("Hi", True),
        ("Hello", True),
        ("Thanks!", True),
        ("Thank you", True),
        ("Doterra On Guard", False),
        ("On Guard", False),
        ("on guard touch", False),
        ("Tea tree", False),
        ("Lavender oil", False),
        ("Deep Blue Rub", False),
        ("Air X", False),
        ("doTERRA ZenGest", False),
        ("Dobrý den", False),
        ("dobry den", False),
        ("pryvit", False),
        ("pryvit, shcho take lavanda", False),
        ("Привет, что такое лаванда?", False),
        ("comment utiliser la lavande", False),
        ("Доброго дня! Що таке лаванда?", False),
        ("Ти знаєш Аріну?", False),
    ])
    def test_detect_is_english(self, query: str, expected: bool):
        from src.agent.service import detect_is_english
        assert detect_is_english(query) is expected

    def test_system_prompt_creator_and_emoji_rules(self):
        from src.agent.prompt import SYSTEM_PROMPT
        # Перевірка ролі та імені Арома, помічниці Наталії Котелянської
        assert "Твоє ім'я — Арома" in SYSTEM_PROMPT
        assert "помічниця Наталії Котелянської" in SYSTEM_PROMPT
        assert "Aroma Assistant" in SYSTEM_PROMPT
        assert "КАТЕГОРИЧНО ЗАБОРОНЕНО" in SYSTEM_PROMPT
        assert "Ти НЕ ГІД!" in SYSTEM_PROMPT
        # Перевірка згадки про розробницю та співавторку Аріну
        assert "Аріна" in SYSTEM_PROMPT
        assert "розробниця системи" in SYSTEM_PROMPT
        assert "співавторка" in SYSTEM_PROMPT
        # Перевірка образу дівчинки з аватарки
        assert "лавандова курточка" in SYSTEM_PROMPT
        assert "паростком" in SYSTEM_PROMPT
        # Заборона на глючні емодзі каменю/обіймів
        assert "🪨" in SYSTEM_PROMPT

    @pytest.mark.parametrize("query", [
        "Скільки коштує олія чайного дерева?",
        "Як замовити консультацію у Наталії?",
        "Хочу стати партнером в команді",
        "Де купити стартовий набір?",
    ])
    def test_detects_consultation_and_sales_intent(self, query: str):
        assert is_consultation_query(query) is True

    @pytest.mark.parametrize("query,expected", [
        ("Хто ти?", True),
        ("Як тебе звати?", True),
        ("Розкажи про себе", True),
        ("Яке твоє улюблене масло?", True),
        ("Яка твоя улюблена олія?", True),
        ("Хто така Аріна?", True),
        ("Ти знаєш розробницю?", True),
        ("Лаванда", False),
        ("Як приймати лимон?", False),
    ])
    def test_is_persona_query(self, query: str, expected: bool):
        from src.agent.specialist import is_persona_query
        assert is_persona_query(query) is expected

    @pytest.mark.parametrize("user_query,response_text,screening_mode,context,expected", [
        # 1. Знайомство / персона помічниці -> False
        ("Хто ти?", "Привіт! Мене звати Арома 🌸 Я затишна помічниця Наталії Котелянської у нашому боті Aroma Assistant.", "inactive", None, False),
        ("Яке твоє улюблене масло?", "Моє найулюбленіше масло — це Лайм 🍋‍🟩! Обожнюю крапельку у воді для бадьорості, мій фірмовий вигук: «Ні, я не буду це пити без Lime!» 🍋‍🟩", "inactive", None, False),
        ("Хто така Аріна?", "Аріна — розробниця системи та співавторка нашого бота 💻✨ Вона й дала мені моє чудове ім'я Арома!", "inactive", None, False),
        
        # 2. Повсякденна коротка розмова / привітання / подяка -> False
        ("Привіт!", "Привіт! Рада тебе бачити 🌿 Чим можу допомогти?", "inactive", None, False),
        ("Дякую за відповідь!", "Будь ласка! Завжди рада допомогти 💛", "inactive", None, False),
        ("Бувай!", "На все добре! Затишного дня ✨", "inactive", None, False),
        ("Що ти вмієш?", "Я можу розповісти про продукцію doTERRA, допомогти підібрати ефірні олії та відповісти на питання про них 🌸", "inactive", None, False),

        # 3. Суто контакти / запис на консультацію без інструкцій застосування -> False
        ("Скільки коштує консультація?", "Для персональної консультації звертайся до Наталії Котелянської:\n💬 Telegram: https://t.me/nkotelianskablog", "inactive", None, False),

        # 4. Червоні прапори (вагітність, ліки тощо) -> True
        ("Я вагітна, що порадиш?", "У вашому запиті є ознаки протипоказань. Я не маю права підбирати олії в таких випадках...", "red_flag", None, True),
        ("Чи можна дитині 2 роки м'яту?", "Для маленьких дітей м'ята перцева протипоказана...", "inactive", None, True),

        # 5. Скарги на здоров'я / скринінг стану -> True
        ("Болить голова, не знаю що робити", "Розумію, головний біль може дуже виснажувати. Уточни, будь ласка, як давно він триває?", "active", None, True),
        ("Не можу спати вже тиждень", "Безсоння — поширена проблема. Чи є хронічні стани або вагітність?", "active", None, True),

        # 6. Застосування, дозування, способи вживання -> True
        ("Як приймати лимон?", "Олію лимону doTERRA можна приймати всередину: 1-2 краплі на склянку теплої води або у рослинній капсулі.", "inactive", None, True),
        ("Скільки крапель капати в дифузор?", "Для дифузора зазвичай достатньо 3–5 крапель ефірної олії на стандартну кімнату.", "inactive", None, True),
        ("Розкажи про чайне дерево", "Чайне дерево doTERRA має антисептичні властивості. Наносити на шкіру слід точково, розводячи базовою олією.", "inactive", None, True),
        ("Як наносити Deep Blue?", "Наносити крем або суміш Deep Blue на м'язи та суглоби масажними рухами після навантажень.", "inactive", None, True),
    ])
    def test_should_include_medical_disclaimer(self, user_query, response_text, screening_mode, context, expected):
        from src.agent.specialist import should_include_medical_disclaimer
        assert should_include_medical_disclaimer(
            response_text=response_text,
            user_query=user_query,
            screening_mode=screening_mode,
            conversation_context=context,
        ) is expected

    @pytest.mark.parametrize("query,expected", [
        ("не вагітна", False),
        ("немає вагітності", False),
        ("я не вагітна, болить голова", False),
        ("ліків не приймаю", False),
        ("без ліків", False),
        ("немає алергії", False),
        ("тиск в нормі", False),
        ("ні", False),
        ("вагітність 5 місяців", True),
        ("я вагітна", True),
        ("приймаю ліки щодня", True),
        ("у мене астма та епілепсія", True),
    ])
    def test_has_red_flags_ignores_negations(self, query: str, expected: bool):
        from src.agent.specialist import has_red_flags
        assert has_red_flags(query) is expected

    def test_extract_user_text_from_context(self):
        from src.agent.specialist import extract_user_text_from_context, has_red_flags
        dialogue = (
            "Користувач: Що допоможе від головного болю?\n\n"
            "Бот: Підкажи, будь ласка: Чи є вагітність або період годування груддю? Чи приймаєш якісь ліки?\n\n"
            "Користувач: ні"
        )
        user_only = extract_user_text_from_context(dialogue)
        assert "Чи є вагітність" not in user_only
        assert "Що допоможе від головного болю?" in user_only
        assert "ні" in user_only
        # Сам діалог з питаннями бота не повинен викликати red flag у користувача, який відповів «ні»
        assert has_red_flags(user_only) is False


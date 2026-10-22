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
        ("Hi", True),
        ("Dobrý den", False),
        ("dobry den", False),
        ("pryvit", False),
        ("Доброго дня! Що таке лаванда?", False),
        ("Ти знаєш Аріну?", False),
    ])
    def test_detect_is_english(self, query: str, expected: bool):
        from src.agent.service import detect_is_english
        assert detect_is_english(query) is expected

    def test_system_prompt_creator_and_emoji_rules(self):
        from src.agent.prompt import SYSTEM_PROMPT
        # Перевірка ролі Aroma Assistant Наталії Котелянської
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

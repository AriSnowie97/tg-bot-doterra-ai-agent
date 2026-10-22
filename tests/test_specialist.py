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

    @pytest.mark.parametrize("query", [
        "Скільки коштує олія чайного дерева?",
        "Як замовити консультацію у Наталії?",
        "Хочу стати партнером в команді",
        "Де купити стартовий набір?",
    ])
    def test_detects_consultation_and_sales_intent(self, query: str):
        assert is_consultation_query(query) is True

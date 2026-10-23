"""
Unit-тести для модуля роботи зі стікерами (src/stickers.py).
"""

import pytest
from unittest.mock import MagicMock
from aiogram.types import Sticker
from src.stickers import (
    is_greeting,
    is_gratitude,
    is_reaction,
    is_farewell,
    is_short_question,
    get_random_sticker,
    classify_casual_interaction,
)
import src.stickers as stickers_mod


class TestStickersModule:
    """Тести класифікації запитів та логіки стікерів."""

    @pytest.mark.parametrize("text", [
        "Привіт!", "добрий день", "Хай", "Вітаю", "Hello", "привет",
        "dobry den", "Dobrý den", "pryvit", "dobryj vechir",
    ])
    def test_is_greeting(self, text: str):
        assert is_greeting(text) is True

    @pytest.mark.parametrize("text", [
        "Дякую велике!", "спасибі", "thanks", "благодарю", "дяка!"
    ])
    def test_is_gratitude(self, text: str):
        assert is_gratitude(text) is True

    @pytest.mark.parametrize("text", [
        "ок", "добре", "супер", "клас", "круто", "чудово", "👍", "❤️"
    ])
    def test_is_reaction(self, text: str):
        assert is_reaction(text) is True

    @pytest.mark.parametrize("text", [
        "бувай", "до побачення", "папа", "пока", "до зустрічі"
    ])
    def test_is_farewell(self, text: str):
        assert is_farewell(text) is True

    @pytest.mark.parametrize("text", [
        "Що таке лаванда?",
        "Як приймати лимон?",
        "А м'ята?",
        "Лаванда",
        "Підкажи масло для сну",
    ])
    def test_is_short_question(self, text: str):
        assert is_short_question(text) is True

    def test_long_question_is_not_short(self):
        long_text = (
            "У мене вже тиждень не проходить головний біль, особливо вечорами, "
            "і я хочу дізнатися чи може мені допомогти дифузор з сумішшю лаванди та м'яти"
        )
        assert is_short_question(long_text) is False

    def test_get_random_sticker_with_cache(self, monkeypatch):
        fake_st1 = MagicMock(spec=Sticker, file_id="ID_WAVE", emoji="👋")
        fake_st2 = MagicMock(spec=Sticker, file_id="ID_HEART", emoji="❤️")

        monkeypatch.setattr(stickers_mod, "_cached_file_ids", ["ID_WAVE", "ID_HEART"])
        monkeypatch.setattr(stickers_mod, "_stickers_by_emoji", {
            "👋": ["ID_WAVE"],
            "❤️": ["ID_HEART"],
        })

        assert get_random_sticker(preferred_emojis=["👋"]) == "ID_WAVE"
        assert get_random_sticker(preferred_emojis=["❤️"]) == "ID_HEART"
        assert get_random_sticker() in ["ID_WAVE", "ID_HEART"]

    def test_get_random_sticker_excludes_negative_stickers_on_fallback(self, monkeypatch):
        fake_pos = MagicMock(spec=Sticker, file_id="POS_ID", emoji="🌿")
        fake_neg = MagicMock(spec=Sticker, file_id="NEG_ID", emoji="👎")

        monkeypatch.setattr(stickers_mod, "_cached_stickers", [fake_pos, fake_neg])
        monkeypatch.setattr(stickers_mod, "_cached_file_ids", ["POS_ID", "NEG_ID"])
        monkeypatch.setattr(stickers_mod, "_stickers_by_emoji", {
            "🌿": ["POS_ID"],
            "👎": ["NEG_ID"],
        })

        # Без preferred_emojis негативний стікер не повинен обиратися
        for _ in range(10):
            result = get_random_sticker()
            assert result == "POS_ID"

    @pytest.mark.parametrize("query,expected_emoji,disallowed_emoji", [
        ("что ты имеешь?", "🤔", "👎"),
        ("расскажи какое твое любимое масло?", "🍋‍🟩", "👎"),
        ("яке твоє найулюбленіше масло?", "🍋‍🟩", "👎"),
        ("що маєш в наявності?", "🌿", "👎"),
        ("покажи каталог продукції", "🤔", "👎"),
        ("підкажи масло для сну", "😴", "👎"),
        ("болить голова та напруга в шиї", "💆‍♀️", "👎"),
        ("що допоможе від застуди та кашлю?", "😷", "👎"),
        ("що дасть енергію зранку?", "☀️", "👎"),
        ("хочу лимон для детоксу", "🍋‍🟩", "👎"),
        ("хвойні олії лісу та сибірська ялиця", "🎄", "👎"),
        ("як працює дифузор та пара?", "😶‍🌫️", "👎"),
        ("хочу спокій та гармонію", "😌", "👎"),
        ("як приймати та яке дозування?", "☝️", "👎"),
        ("обожнюю цю олію, це магія!", "😍", "👎"),
        ("зі святом та вітаємо!", "🥳", "👎"),
        ("дякую тобі велике!", "🙏", "👎"),
        ("привіт, хто ти?", "👋", "👎"),
        ("не можна капати в очі", "👎", None),
    ])
    def test_detect_sticker_emojis_for_text(self, query: str, expected_emoji: str, disallowed_emoji: str):
        from src.stickers import detect_sticker_emojis_for_text
        detected = detect_sticker_emojis_for_text(query)
        assert expected_emoji in detected
        if disallowed_emoji:
            assert disallowed_emoji not in detected

    def test_get_welcome_sticker_returns_greeting_not_good_day(self, monkeypatch):
        import asyncio
        from src.stickers import (
            get_welcome_sticker,
            WELCOME_STICKER_FILE_ID,
            GOOD_DAY_STICKER_FILE_ID,
            FAREWELL_STICKER_FILE_ID,
        )
        fake_bot = MagicMock()

        monkeypatch.setattr(stickers_mod, "_cached_file_ids", [
            WELCOME_STICKER_FILE_ID,
            GOOD_DAY_STICKER_FILE_ID,
            FAREWELL_STICKER_FILE_ID,
        ])
        monkeypatch.setattr(stickers_mod, "_stickers_by_emoji", {
            "👋": [WELCOME_STICKER_FILE_ID, GOOD_DAY_STICKER_FILE_ID, FAREWELL_STICKER_FILE_ID],
        })

        for _ in range(10):
            res = asyncio.run(get_welcome_sticker(fake_bot))
            assert res == WELCOME_STICKER_FILE_ID
            assert res != GOOD_DAY_STICKER_FILE_ID
            assert res != FAREWELL_STICKER_FILE_ID

    def test_get_farewell_sticker_returns_farewell_or_good_day(self, monkeypatch):
        import asyncio
        from src.stickers import (
            get_farewell_sticker,
            WELCOME_STICKER_FILE_ID,
            GOOD_DAY_STICKER_FILE_ID,
            FAREWELL_STICKER_FILE_ID,
        )
        fake_bot = MagicMock()

        monkeypatch.setattr(stickers_mod, "_cached_file_ids", [
            WELCOME_STICKER_FILE_ID,
            GOOD_DAY_STICKER_FILE_ID,
            FAREWELL_STICKER_FILE_ID,
        ])

        for _ in range(10):
            res = asyncio.run(get_farewell_sticker(fake_bot))
            assert res in [FAREWELL_STICKER_FILE_ID, GOOD_DAY_STICKER_FILE_ID]
            assert res != WELCOME_STICKER_FILE_ID

    def test_wave_emoji_filters_out_farewell_and_good_day_in_random(self, monkeypatch):
        from src.stickers import (
            WELCOME_STICKER_FILE_ID,
            GOOD_DAY_STICKER_FILE_ID,
            FAREWELL_STICKER_FILE_ID,
        )

        monkeypatch.setattr(stickers_mod, "_cached_file_ids", [
            WELCOME_STICKER_FILE_ID,
            GOOD_DAY_STICKER_FILE_ID,
            FAREWELL_STICKER_FILE_ID,
        ])
        monkeypatch.setattr(stickers_mod, "_stickers_by_emoji", {
            "👋": [WELCOME_STICKER_FILE_ID, GOOD_DAY_STICKER_FILE_ID, FAREWELL_STICKER_FILE_ID],
        })

        for _ in range(10):
            res = get_random_sticker(preferred_emojis=["👋"])
            assert res == WELCOME_STICKER_FILE_ID
            assert res != GOOD_DAY_STICKER_FILE_ID
            assert res != FAREWELL_STICKER_FILE_ID



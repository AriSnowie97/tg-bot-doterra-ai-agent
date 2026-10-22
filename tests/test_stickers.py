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

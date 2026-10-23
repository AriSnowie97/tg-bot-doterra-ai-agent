import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, Chat, User
from aiogram.enums import ChatType

import bot as bot_mod
from src.agent.prompt import build_system_prompt
from src.agent.specialist import has_red_flags, is_health_complaint_query
from src.stickers import is_greeting


@pytest.mark.parametrize("query", [
    "Розкажи про олію Зелений Дракон XYZ",
    "Розкажи детально про всі протоколи Symphony of the Cells",
    "Чи є ризик для kidney health?",
])
def test_no_false_red_flag_on_substrings(query):
    assert has_red_flags(query) is False


@pytest.mark.parametrize("query", [
    "У мене рак",
    "Для дітей можна лаванду?",
    "Is it safe for my kids?",
    "Дитині 3 роки",
])
def test_real_red_flags_still_detected(query):
    assert has_red_flags(query) is True


@pytest.mark.parametrize("query", [
    "Привіт, не можу заснути",
    "Не можу заснути вже тиждень",
])
def test_sleep_complaints_are_detected(query):
    assert is_health_complaint_query(query) is True
    assert is_greeting(query) is False


def test_english_greeting_with_question_is_not_a_greeting():
    assert is_greeting("Hello, is lavender safe?") is False


def test_screening_stage_instructions():
    ask = build_system_prompt([], screening_mode="active", screening_stage="ask")
    answer = build_system_prompt([], screening_mode="active", screening_stage="answer")
    assert "ПЕРШЕ ЗВЕРНЕННЯ" in ask and "КОРИСТУВАЧ ВЖЕ ВІДПОВІВ" not in ask
    assert "КОРИСТУВАЧ ВЖЕ ВІДПОВІВ" in answer and "ПЕРШЕ ЗВЕРНЕННЯ" not in answer
    inactive = build_system_prompt([], screening_mode="inactive", screening_stage="ask")
    assert "ЕТАП СКРИНІНГУ" not in inactive


def test_long_message_is_split_under_telegram_limit():
    text = "\n\n".join(["Абзац " + "слово " * 120] * 12)
    parts = bot_mod._split_message(text)
    assert len(parts) > 1
    assert all(len(p) <= bot_mod.TELEGRAM_MESSAGE_LIMIT for p in parts)


def _private_message(text):
    message = AsyncMock(spec=Message)
    message.chat = MagicMock(spec=Chat, type=ChatType.PRIVATE, id=1)
    message.from_user = MagicMock(spec=User, id=123, is_bot=False)
    message.text = text
    message.reply = AsyncMock()
    message.reply_sticker = AsyncMock()
    return message


@pytest.mark.anyio
async def test_gratitude_gets_matching_sticker(monkeypatch):
    monkeypatch.setattr(bot_mod.random, "random", lambda: 0.0)
    getter = AsyncMock(return_value="STICKER_ID")
    monkeypatch.setattr(bot_mod, "get_or_load_sticker", getter)
    message = _private_message("дякую")
    state = AsyncMock()
    state.get_data.return_value = {"conversation_active": True, "has_introduced": True}

    await bot_mod.on_message(message, MagicMock(), state)

    message.reply.assert_called_once()
    message.reply_sticker.assert_called_once_with("STICKER_ID")
    assert getter.call_args[0][1][0] in ("🙏", "😊", "❤️", "🌿")


@pytest.mark.anyio
async def test_sticker_skipped_when_probability_not_hit(monkeypatch):
    monkeypatch.setattr(bot_mod.random, "random", lambda: 0.999)
    monkeypatch.setattr(bot_mod, "get_or_load_sticker", AsyncMock(return_value="STICKER_ID"))
    message = _private_message("дякую")
    state = AsyncMock()
    state.get_data.return_value = {"conversation_active": True, "has_introduced": True}

    await bot_mod.on_message(message, MagicMock(), state)

    message.reply_sticker.assert_not_called()


@pytest.mark.anyio
async def test_health_complaint_never_gets_sticker(monkeypatch):
    monkeypatch.setattr(bot_mod.random, "random", lambda: 0.0)
    getter = AsyncMock(return_value="STICKER_ID")
    monkeypatch.setattr(bot_mod, "get_or_load_sticker", getter)
    monkeypatch.setattr(bot_mod, "get_welcome_sticker", getter)
    monkeypatch.setattr(bot_mod, "generate_response", AsyncMock(return_value="Розкажи, будь ласка, більше"))
    message = _private_message("Привіт, не можу заснути")
    sent = MagicMock(message_id=1, chat=MagicMock(id=1))
    sent.edit_reply_markup = AsyncMock()
    message.reply = AsyncMock(return_value=sent)
    state = AsyncMock()
    state.get_data.return_value = {}

    await bot_mod.on_message(message, MagicMock(), state)

    message.reply_sticker.assert_not_called()

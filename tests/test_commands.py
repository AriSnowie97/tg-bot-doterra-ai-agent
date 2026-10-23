import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, Chat, User
from aiogram.enums import ChatType
from bot import command_help_handler, command_cancel_handler, unknown_command_handler
from src.agent.service import detect_is_english


def test_detect_is_english_ignores_slash_commands():
    assert detect_is_english("/help") is False
    assert detect_is_english("/start") is False
    assert detect_is_english("/foo") is False
    assert detect_is_english("/ask what is lavender") is False


@pytest.mark.anyio
async def test_command_help_handler():
    message = AsyncMock()
    message.chat = MagicMock(spec=Chat, type=ChatType.PRIVATE)
    message.from_user = MagicMock(spec=User, first_name="TestUser")
    message.reply = AsyncMock()
    state = AsyncMock()
    state.get_state.return_value = None

    await command_help_handler(message, state)

    message.reply.assert_called_once()
    args, kwargs = message.reply.call_args
    reply_text = args[0]
    assert "Чим я можу тобі допомогти" in reply_text
    assert "/start" in reply_text
    assert "/ask" in reply_text
    assert "/help" in reply_text
    assert kwargs.get("parse_mode") == "HTML"
    assert "reply_markup" in kwargs


@pytest.mark.anyio
async def test_command_cancel_handler():
    message = AsyncMock()
    message.reply = AsyncMock()
    state = AsyncMock()

    await command_cancel_handler(message, state)

    state.clear.assert_called_once()
    message.reply.assert_called_once()
    assert "скасовано" in message.reply.call_args[0][0]


@pytest.mark.anyio
async def test_unknown_command_handler_private():
    message = AsyncMock()
    message.text = "/foo"
    message.caption = None
    message.chat = MagicMock(spec=Chat, type=ChatType.PRIVATE)
    message.reply = AsyncMock()
    state = AsyncMock()
    state.get_state.return_value = None

    await unknown_command_handler(message, state)

    message.reply.assert_called_once()
    assert "Невідома команда" in message.reply.call_args[0][0]


@pytest.mark.anyio
async def test_other_bot_command_middleware_ignores_foreign_bot():
    import bot as bot_mod
    from bot import OtherBotCommandFilterMiddleware

    bot_mod._BOT_USERNAME = "doterra_ua_assistant_bot"
    middleware = OtherBotCommandFilterMiddleware()
    handler = AsyncMock()

    # Повідомлення для іншого бота
    msg = AsyncMock()
    msg.text = "/start@shops_json_ua_bot"
    res = await middleware(handler, msg, {})

    assert res is None
    handler.assert_not_called()


@pytest.mark.anyio
async def test_other_bot_command_middleware_allows_own_bot():
    import bot as bot_mod
    from bot import OtherBotCommandFilterMiddleware

    bot_mod._BOT_USERNAME = "doterra_ua_assistant_bot"
    middleware = OtherBotCommandFilterMiddleware()
    handler = AsyncMock(return_value="OK")

    # Повідомлення для нашого бота
    msg = AsyncMock()
    msg.text = "/start@doterra_ua_assistant_bot"
    res = await middleware(handler, msg, {})

    assert res == "OK"
    handler.assert_called_once()


def test_system_prompt_forbids_unprompted_favorite_oil():
    from src.agent.prompt import SYSTEM_PROMPT
    assert "НЕ говори постійно про свій улюблений аромат" in SYSTEM_PROMPT
    assert "КАТЕГОРИЧНО ЗАБОРОНЕНО згадувати про свій улюблений аромат" in SYSTEM_PROMPT


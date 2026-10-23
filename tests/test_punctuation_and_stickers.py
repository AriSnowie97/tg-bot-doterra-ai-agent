import pytest
import time
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, Chat, User
from aiogram.enums import ChatType
from bot import on_message, command_ask_handler, _reply_with_feedback


@pytest.mark.anyio
async def test_single_dot_does_not_hallucinate_rag():
    """Тест скріншоту 1: крапка '.' не викликає RAG та не генерує консультації про On Guard."""
    message = AsyncMock(spec=Message)
    message.chat = MagicMock(spec=Chat, type=ChatType.PRIVATE)
    message.from_user = MagicMock(spec=User, id=123, is_bot=False)
    message.text = "."
    message.reply = AsyncMock()
    message.reply_sticker = AsyncMock()
    state = AsyncMock()
    state.get_data.return_value = {
        "dialogue_turns": [{"role": "assistant", "text": "On Guard Touch"}]
    }

    await on_message(message, MagicMock(), state)

    message.reply.assert_called_once()
    reply_text = message.reply.call_args[0][0]
    assert "напиши своє запитання словами" in reply_text
    assert "On Guard" not in reply_text
    message.reply_sticker.assert_not_called()


@pytest.mark.anyio
async def test_question_mark_no_medical_disclaimer_no_sticker():
    """Тест скріншоту 2: знак питання '?' не додає медичний дисклеймер та не надсилає стікер."""
    message = AsyncMock(spec=Message)
    message.chat = MagicMock(spec=Chat, type=ChatType.PRIVATE)
    message.from_user = MagicMock(spec=User, id=123, is_bot=False)
    message.text = "?"
    message.reply = AsyncMock()
    message.reply_sticker = AsyncMock()
    state = AsyncMock()
    state.get_data.return_value = {
        "screening_mode": None,
        "dialogue_turns": [{"role": "user", "text": "болить голова"}]
    }

    await on_message(message, MagicMock(), state)

    message.reply.assert_called_once()
    reply_text = message.reply.call_args[0][0]
    assert "Чим я можу тобі допомогти?" in reply_text
    assert "медичною консультацією" not in reply_text
    message.reply_sticker.assert_not_called()


@pytest.mark.anyio
async def test_closer_ok_and_thumbs_up_no_stickers_no_duplicate():
    """Тест скріншотів 2 і 3: 'ок' та наступний '👍' не надсилають стікерів і не дублюють полотно тексту."""
    # 1. Перший крок: користувач пише 'ок'
    msg_ok = AsyncMock(spec=Message)
    msg_ok.chat = MagicMock(spec=Chat, type=ChatType.PRIVATE)
    msg_ok.from_user = MagicMock(spec=User, id=123, is_bot=False)
    msg_ok.text = "ок"
    msg_ok.reply = AsyncMock()
    msg_ok.reply_sticker = AsyncMock()
    state = AsyncMock()
    state.get_data.return_value = {
        "conversation_active": True,
        "has_introduced": True,
        "last_interaction_ts": time.time() - 10,
    }

    await on_message(msg_ok, MagicMock(), state)

    msg_ok.reply.assert_called_once()
    msg_ok.reply_sticker.assert_not_called()

    # 2. Другий крок: користувач пише '👍' одразу після 'ок' при закритому діалозі
    msg_thumbs = AsyncMock(spec=Message)
    msg_thumbs.chat = MagicMock(spec=Chat, type=ChatType.PRIVATE)
    msg_thumbs.from_user = MagicMock(spec=User, id=123, is_bot=False)
    msg_thumbs.text = "👍"
    msg_thumbs.reply = AsyncMock()
    msg_thumbs.reply_sticker = AsyncMock()

    # Стан після першого кроку: conversation_active = False
    state.get_data.return_value = {
        "conversation_active": False,
        "has_introduced": True,
        "last_interaction_ts": time.time() - 2,
    }

    await on_message(msg_thumbs, MagicMock(), state)

    msg_thumbs.reply.assert_called_once()
    reply_thumbs = msg_thumbs.reply.call_args[0][0]
    # Коротка ввічлива відповідь, а не дублювання великого тексту "Домовилися! 🌸..."
    assert reply_thumbs in ("Завжди на зв'язку! 🌿🌸", "Завжди рада допомогти! 🌸", "До зустрічі! 🌸")
    msg_thumbs.reply_sticker.assert_not_called()


@pytest.mark.anyio
async def test_emoji_only_leaves_no_sticker():
    """Тест скріншоту 4: '🌿🌿🌿' не викликає стікера 'Треба подумати' та привітання."""
    message = AsyncMock(spec=Message)
    message.chat = MagicMock(spec=Chat, type=ChatType.PRIVATE)
    message.from_user = MagicMock(spec=User, id=123, is_bot=False)
    message.text = "🌿🌿🌿"
    message.reply = AsyncMock()
    message.reply_sticker = AsyncMock()
    state = AsyncMock()
    state.get_data.return_value = {
        "has_introduced": True,
        "conversation_active": True,
    }

    await on_message(message, MagicMock(), state)

    message.reply.assert_called_once()
    reply_text = message.reply.call_args[0][0]
    assert "Запитай мене що-небудь про ефірні олії" in reply_text
    message.reply_sticker.assert_not_called()


@pytest.mark.anyio
async def test_reply_with_feedback_never_sends_sticker():
    """Перевіряє, що _reply_with_feedback взагалі не надсилає стікерів."""
    message = AsyncMock(spec=Message)
    message.reply = AsyncMock(return_value=AsyncMock(message_id=999, chat=MagicMock(id=123)))
    message.reply_sticker = AsyncMock()

    await _reply_with_feedback(message, "Відповідь бота", sticker_id="CAACAgIAAxkBA...")

    message.reply.assert_called_once()
    message.reply_sticker.assert_not_called()

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from bot import _keep_typing
from aiogram.enums import ChatAction


@pytest.mark.anyio
async def test_keep_typing_with_thread_id():
    bot = AsyncMock()
    stop_event = asyncio.Event()

    # Set stop_event after a tiny moment
    async def trigger_stop():
        await asyncio.sleep(0.05)
        stop_event.set()

    asyncio.create_task(trigger_stop())
    await _keep_typing(bot, chat_id=-100123456, stop_event=stop_event, message_thread_id=42)

    bot.send_chat_action.assert_called_with(
        chat_id=-100123456,
        action=ChatAction.TYPING,
        message_thread_id=42,
    )


@pytest.mark.anyio
async def test_keep_typing_fallback_on_topic_error():
    bot = AsyncMock()
    # First call with message_thread_id raises exception, fallback without thread_id succeeds
    bot.send_chat_action.side_effect = [Exception("Topic not found"), None]
    stop_event = asyncio.Event()

    async def trigger_stop():
        await asyncio.sleep(0.05)
        stop_event.set()

    asyncio.create_task(trigger_stop())
    await _keep_typing(bot, chat_id=-100123456, stop_event=stop_event, message_thread_id=42)

    # Should have attempted with thread_id, then without thread_id
    assert bot.send_chat_action.call_count >= 2
    bot.send_chat_action.assert_any_call(
        chat_id=-100123456,
        action=ChatAction.TYPING,
    )

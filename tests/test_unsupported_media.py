import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, Chat, User, MessageEntity
from aiogram.enums import ChatType, MessageEntityType
import bot as bot_mod
from bot import unsupported_content_handler, on_sticker, dp
from src.safety import UNSUPPORTED_CONTENT_REPLY


@pytest.mark.parametrize(
    "media_attr,kwargs",
    [
        ("photo", {"photo": [MagicMock()], "caption": None}),
        ("photo_with_caption", {"photo": [MagicMock()], "caption": "Подивись на фото"}),
        ("voice", {"voice": MagicMock()}),
        ("video", {"video": MagicMock()}),
        ("video_note", {"video_note": MagicMock()}),
        ("audio", {"audio": MagicMock()}),
        ("document", {"document": MagicMock()}),
        ("animation", {"animation": MagicMock()}),
        ("location", {"location": MagicMock()}),
        ("contact", {"contact": MagicMock()}),
        ("poll", {"poll": MagicMock()}),
        ("dice", {"dice": MagicMock()}),
        ("sticker", {"sticker": MagicMock(emoji="🌸")}),
    ],
)
@pytest.mark.anyio
async def test_unsupported_media_in_private_chat(media_attr: str, kwargs: dict):
    """Перевіряє, що будь-який тип нетекстового контенту у приватному чаті отримує коротке повідомлення."""
    message = AsyncMock(spec=Message)
    message.chat = MagicMock(spec=Chat, type=ChatType.PRIVATE)
    message.from_user = MagicMock(spec=User, id=123, is_bot=False)
    message.text = None
    message.caption = kwargs.get("caption")
    message.entities = None
    message.caption_entities = None
    message.reply_to_message = None
    message.reply = AsyncMock()
    message.reply_sticker = AsyncMock()

    for k, v in kwargs.items():
        setattr(message, k, v)

    await unsupported_content_handler(message)

    message.reply.assert_called_once()
    reply_text = message.reply.call_args[0][0]
    assert "Я розумію лише текст…" in reply_text
    assert reply_text == UNSUPPORTED_CONTENT_REPLY
    # Бот НЕ повинен надсилати стікер у відповідь
    message.reply_sticker.assert_not_called()


@pytest.mark.anyio
async def test_on_sticker_alias_behaviour():
    """Перевіряє, що аліас on_sticker тепер повертає текстове повідомлення замість надсилання стікера."""
    message = AsyncMock(spec=Message)
    message.chat = MagicMock(spec=Chat, type=ChatType.PRIVATE)
    message.from_user = MagicMock(spec=User, id=123, is_bot=False)
    message.text = None
    message.caption = None
    message.entities = None
    message.caption_entities = None
    message.reply_to_message = None
    message.sticker = MagicMock(emoji="😊")
    message.reply = AsyncMock()
    message.reply_sticker = AsyncMock()

    await on_sticker(message)

    message.reply.assert_called_once_with(UNSUPPORTED_CONTENT_REPLY)
    message.reply_sticker.assert_not_called()


@pytest.mark.anyio
async def test_unsupported_media_in_group_ignored_if_not_addressed():
    """У групах бот не спамить, якщо повідомлення не адресоване йому."""
    bot_mod._BOT_USERNAME = "aroma_bot"

    message = AsyncMock(spec=Message)
    message.chat = MagicMock(spec=Chat, type=ChatType.GROUP)
    message.from_user = MagicMock(spec=User, id=456, is_bot=False)
    message.text = None
    message.caption = None
    message.entities = None
    message.caption_entities = None
    message.reply_to_message = None
    message.photo = [MagicMock()]
    message.reply = AsyncMock()

    await unsupported_content_handler(message)

    message.reply.assert_not_called()


@pytest.mark.anyio
async def test_unsupported_media_in_group_replies_if_reply_to_bot():
    """У групах бот відповідає, якщо це Reply на його повідомлення."""
    bot_mod._BOT_USERNAME = "aroma_bot"

    bot_user = MagicMock(spec=User, username="aroma_bot")
    replied_msg = MagicMock(spec=Message, from_user=bot_user)

    message = AsyncMock(spec=Message)
    message.chat = MagicMock(spec=Chat, type=ChatType.GROUP)
    message.from_user = MagicMock(spec=User, id=456, is_bot=False)
    message.text = None
    message.caption = None
    message.entities = None
    message.caption_entities = None
    message.reply_to_message = replied_msg
    message.voice = MagicMock()
    message.reply = AsyncMock()

    await unsupported_content_handler(message)

    message.reply.assert_called_once()
    assert "Я розумію лише текст…" in message.reply.call_args[0][0]


@pytest.mark.anyio
async def test_unsupported_media_in_group_replies_if_mention_in_caption():
    """У групах бот відповідає, якщо його згадали через @mention у підписі до фото/відео/документа."""
    bot_mod._BOT_USERNAME = "aroma_bot"

    entity = MagicMock(spec=MessageEntity, type=MessageEntityType.MENTION, offset=0, length=10)

    message = AsyncMock(spec=Message)
    message.chat = MagicMock(spec=Chat, type=ChatType.GROUP)
    message.from_user = MagicMock(spec=User, id=456, is_bot=False)
    message.text = None
    message.caption = "@aroma_bot підкажи"
    message.entities = None
    message.caption_entities = [entity]
    message.reply_to_message = None
    message.photo = [MagicMock()]
    message.reply = AsyncMock()

    await unsupported_content_handler(message)

    message.reply.assert_called_once()
    assert "Я розумію лише текст…" in message.reply.call_args[0][0]

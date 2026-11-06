"""
Unit та асинхронні тести для блоку зворотного зв'язку (FB-01...FB-06, IN-04, AP-14).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import CallbackQuery, Message, User, Chat, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.enums import ChatType

import bot as bot_mod
from src.middleware import CallbackRateLimitMiddleware


def _make_callback(
    data: str,
    user_id: int = 42,
    query_text: str = "Що таке лаванда?",
    bot_text: str = "Лаванда — чудова олія для розслаблення 🌸",
    has_article_button: bool = True,
) -> CallbackQuery:
    user = User(id=user_id, is_bot=False, first_name="Тест")
    chat = Chat(id=100, type="private")

    article_row = (
        [InlineKeyboardButton(text="📖 Лаванда", web_app=WebAppInfo(url="https://example.com/#/article/lavender"))]
        if has_article_button else []
    )
    fb_row = [
        InlineKeyboardButton(text="👍", callback_data="fb:like:123:100"),
        InlineKeyboardButton(text="👎", callback_data="fb:dislike:123:100"),
    ]
    inline_keyboard = [article_row, fb_row] if article_row else [fb_row]
    markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

    reply_msg = MagicMock(spec=Message)
    reply_msg.message_id = 122
    reply_msg.text = query_text
    reply_msg.chat = chat
    reply_msg.from_user = user

    bot_msg = MagicMock(spec=Message)
    bot_msg.message_id = 123
    bot_msg.chat = chat
    bot_msg.from_user = User(id=999, is_bot=True, first_name="Aroma")
    bot_msg.text = bot_text
    bot_msg.reply_to_message = reply_msg
    bot_msg.reply_markup = markup
    bot_msg.edit_reply_markup = AsyncMock()

    cb = MagicMock(spec=CallbackQuery)
    cb.id = "cb_1"
    cb.from_user = user
    cb.chat_instance = "ci_1"
    cb.message = bot_msg
    cb.data = data
    cb.answer = AsyncMock()
    return cb


@pytest.mark.anyio
async def test_fb_01_first_like_toast_and_counter(monkeypatch):
    """FB-01: Перше натискання 👍 показує тост подяки, змінює лічильник на 👍 1 та зберігає статтю."""
    cb = _make_callback("fb:like:123:100")

    monkeypatch.setattr(bot_mod, "save_vote", MagicMock(return_value="inserted"))
    monkeypatch.setattr(bot_mod, "get_vote_counts", MagicMock(return_value={"likes": 1, "dislikes": 0}))

    await bot_mod.feedback_callback(cb)

    # 1. Відповідь (тост)
    cb.answer.assert_called_once_with("👍 Дякую за позитивний відгук!", show_alert=False)
    # 2. Оновлення клавіатури
    cb.message.edit_reply_markup.assert_called_once()
    new_kb = cb.message.edit_reply_markup.call_args.kwargs["reply_markup"]
    # Перевіряємо, що збереглася кнопка статті
    assert new_kb.inline_keyboard[0][0].text == "📖 Лаванда"
    # Перевіряємо оновлений лічильник 👍 1
    assert new_kb.inline_keyboard[1][0].text == "👍 1"
    assert new_kb.inline_keyboard[1][1].text == "👎"


@pytest.mark.anyio
async def test_fb_02_vote_changed_from_like_to_dislike(monkeypatch):
    """FB-02: Потім 👎 на тому ж повідомленні замінює голос (голос змінився)."""
    cb = _make_callback("fb:dislike:123:100")

    monkeypatch.setattr(bot_mod, "save_vote", MagicMock(return_value="updated"))
    monkeypatch.setattr(bot_mod, "get_vote_counts", MagicMock(return_value={"likes": 0, "dislikes": 1}))

    await bot_mod.feedback_callback(cb)

    # 1. Відповідь для дизлайку
    cb.answer.assert_called_once_with("👎 Зрозуміло, постараємось покращити відповіді!", show_alert=False)
    # 2. Оновлення клавіатури на 👎 1
    new_kb = cb.message.edit_reply_markup.call_args.kwargs["reply_markup"]
    assert new_kb.inline_keyboard[1][0].text == "👍"
    assert new_kb.inline_keyboard[1][1].text == "👎 1"


@pytest.mark.anyio
async def test_fb_03_repeat_same_vote_shows_already_voted(monkeypatch):
    """FB-03: Повторний той самий голос повідомляє «Ти вже поставив цю оцінку!»."""
    cb = _make_callback("fb:like:123:100")

    monkeypatch.setattr(bot_mod, "save_vote", MagicMock(return_value="unchanged"))
    monkeypatch.setattr(bot_mod, "get_vote_counts", MagicMock(return_value={"likes": 1, "dislikes": 0}))

    await bot_mod.feedback_callback(cb)

    cb.answer.assert_called_once_with("👍 Ти вже поставив цю оцінку!", show_alert=False)
    # edit_reply_markup не викликається при незмінному голосі
    cb.message.edit_reply_markup.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("query_text", [
    "Я вагітна, що взяти від стресу?",
    "Не можу заснути",
    "в а г і т н а",
    "доньці 5 років болить горло",
])
async def test_fb_04_privacy_masking_for_sensitive_queries(query_text, monkeypatch):
    """FB-04: Питання з червоними прапорами чи скаргами (вагітність, сон) маскуються у БД."""
    cb = _make_callback("fb:like:123:100", query_text=query_text)

    mock_save = MagicMock(return_value="inserted")
    monkeypatch.setattr(bot_mod, "save_vote", mock_save)
    monkeypatch.setattr(bot_mod, "get_vote_counts", MagicMock(return_value={"likes": 1, "dislikes": 0}))

    await bot_mod.feedback_callback(cb)

    # Перевіряємо аргументи збереження у БД
    mock_save.assert_called_once()
    saved_query = mock_save.call_args.kwargs["query_text"]
    assert saved_query == "[Захищено: медичне звернення / червоний прапор]"


@pytest.mark.anyio
async def test_fb_04_non_sensitive_query_not_masked(monkeypatch):
    """FB-04: Звичайні питання зберігаються без маскування."""
    cb = _make_callback("fb:like:123:100", query_text="Що таке лаванда?")

    mock_save = MagicMock(return_value="inserted")
    monkeypatch.setattr(bot_mod, "save_vote", mock_save)
    monkeypatch.setattr(bot_mod, "get_vote_counts", MagicMock(return_value={"likes": 1, "dislikes": 0}))

    await bot_mod.feedback_callback(cb)

    saved_query = mock_save.call_args.kwargs["query_text"]
    assert saved_query == "Що таке лаванда?"


@pytest.mark.anyio
async def test_in_04_rapid_clicking_exceeds_rate_limit():
    """IN-04: Швидке натискання кнопок понад ліміт повертає «Забагато натискань»."""
    middleware = CallbackRateLimitMiddleware()
    cb = _make_callback("fb:like:123:100", user_id=777)

    handler = AsyncMock(return_value="handled")
    # Здійснюємо лімітну кількість запитів (20)
    for _ in range(20):
        res = await middleware(handler, cb, {})
        assert res == "handled"

    # 21-й запит має бути заблокований лімітом
    blocked_cb = _make_callback("fb:like:123:100", user_id=777)
    res_blocked = await middleware(handler, blocked_cb, {})
    assert res_blocked is None
    blocked_cb.answer.assert_called_once_with("⏳ Забагато натискань. Зачекай хвилинку.", show_alert=False)


@pytest.mark.anyio
async def test_fb_06_older_than_48h_or_deleted_message(monkeypatch):
    """FB-06: На повідомленні, де reply_to видалено або edit_reply_markup дає помилку — не падає."""
    cb = _make_callback("fb:like:123:100")
    cb.message.reply_to_message = None  # Видалене повідомлення автора
    # edit_reply_markup кидає помилку (наприклад, TelegramBadRequest "message not found")
    cb.message.edit_reply_markup.side_effect = RuntimeError("message to edit not found")

    mock_save = MagicMock(return_value="inserted")
    monkeypatch.setattr(bot_mod, "save_vote", mock_save)
    monkeypatch.setattr(bot_mod, "get_vote_counts", MagicMock(return_value={"likes": 1, "dislikes": 0}))

    await bot_mod.feedback_callback(cb)

    # Голос все одно збережено
    mock_save.assert_called_once()
    # Користувач все одно отримує підтвердження
    cb.answer.assert_called_once_with("👍 Дякую за позитивний відгук!", show_alert=False)


def test_ap_14_article_button_opens_mini_app():
    """AP-14: Кнопка «📖 …» створює web_app у приватному чаті з посиланням на статтю."""
    btn = bot_mod._open_app_button(
        "📖 Лаванда",
        "https://example.com/#/article/lavender",
        ChatType.PRIVATE,
    )
    assert btn.text == "📖 Лаванда"
    assert btn.web_app is not None
    assert btn.web_app.url == "https://example.com/#/article/lavender"
    assert btn.url is None

    # У групі — direct-посилання на Mini App всередині Telegram замість зовнішнього браузера
    group_btn = bot_mod._open_app_button(
        "📖 Лаванда",
        "https://example.com/#/article/lavender",
        ChatType.SUPERGROUP,
    )
    assert group_btn.web_app is None
    assert "t.me" in group_btn.url
    assert "startapp=article_lavender" in group_btn.url

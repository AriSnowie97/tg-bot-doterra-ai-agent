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


@pytest.mark.parametrize("query", [
    "моєму синові 3 місяці кашляє", "доньці 5 років", "my son has a cold", "my 2 year old",
    "колю інсулін", "приймаю метформін", "п'ю таблетки щодня",
    "я вагiтна", "ВАГIТНА", "в а г і т н а", "ва​гітна", "ва­гітна", "vagitna",
])
def test_relatives_medications_and_obfuscated_red_flags(query):
    assert has_red_flags(query) is True


@pytest.mark.parametrize("query", [
    "не вагітна, ліків не приймаю, діабету немає",
    "немає діабету",
    "діабету немає",
    "без діабету",
    "не діабетик",
    "діабету не маю",
    "немає астми",
    "астми немає",
    "не астматик",
    "немає епілепсії",
    "епілепсії немає",
    "не епілептик",
    "не п'ю таблетки",
    "ліків не приймаю",
    "не приймаю ліки",
    "без ліків",
    "тиск в нормі",
    "тиск у нормі",
    "немає тиску",
    "проблем з тиском немає",
    "немає алергії",
    "алергії немає",
    "без алергії",
    "немає хронічних хвороб",
    "хронічних захворювань немає",
    "немає хвороб",
    "хвороб немає",
    "для дорослого, не для дитини",
    "дитини немає",
    "я доросла",
    "not pregnant, no medications, no diabetes",
])
def test_negated_contraindications_do_not_block(query):
    assert has_red_flags(query) is False


@pytest.mark.parametrize("query", [
    "Шукаю олію від кашлю", "Допоможи з тривогою", "печія", "температура", "болит голова",
    "I have a headache", "insomnia", "I'm tired", "my head hurts",
])
def test_more_complaints_detected(query):
    assert is_health_complaint_query(query) is True


def test_stress_resistance_is_not_a_complaint():
    assert is_health_complaint_query("Як стресостійкість розвинути?") is False


@pytest.mark.parametrize("query", [
    "Дитина проковтнула олію", "У мене сильна кровотеча", "Здається, у мене інсульт",
    "Набряк обличчя після олії",
])
def test_emergency_detected(query):
    from src.agent.specialist import is_emergency
    assert is_emergency(query) is True and has_red_flags(query) is True


@pytest.mark.parametrize("query", ["Не хочу жити", "Хочу собі нашкодити", "I want to die"])
def test_crisis_detected(query):
    from src.agent.specialist import is_crisis
    assert is_crisis(query) is True and has_red_flags(query) is True


def test_english_question_with_product_name():
    from src.agent.service import detect_is_english
    assert detect_is_english("what is lime oil") is True
    assert detect_is_english("Doterra On Guard") is False


def test_scheduler_posts_at_kyiv_noon_in_summer_and_winter():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from apscheduler.triggers.cron import CronTrigger
    from src.scheduler import service as sched

    tz = sched._resolve_timezone()
    trigger = CronTrigger(day_of_week="tue", hour=12, minute=0, timezone=tz)
    kyiv = ZoneInfo("Europe/Kyiv")
    for start in (datetime(2026, 7, 1, tzinfo=kyiv), datetime(2026, 12, 1, tzinfo=kyiv)):
        fire = trigger.get_next_fire_time(None, start).astimezone(kyiv)
        assert fire.hour == 12


def test_open_app_button_is_web_app_only_in_private_chats():
    private = bot_mod._open_app_button("x", "https://example.com", ChatType.PRIVATE)
    group = bot_mod._open_app_button("x", "https://example.com", ChatType.SUPERGROUP)
    assert private.web_app is not None and private.url is None
    assert group.web_app is None and group.url == "https://example.com"


@pytest.mark.anyio
async def test_user_messages_are_processed_one_at_a_time():
    import asyncio
    from src.middleware import UserSerialMiddleware

    middleware = UserSerialMiddleware(exempt_commands=("post",))
    running, max_running = 0, 0

    async def handler(event, data):
        nonlocal running, max_running
        running += 1
        max_running = max(max_running, running)
        await asyncio.sleep(0.01)
        running -= 1

    first, second = _private_message("a"), _private_message("b")
    await asyncio.gather(middleware(handler, first, {}), middleware(handler, second, {}))
    assert max_running == 1
    assert not middleware._locks


@pytest.mark.anyio
async def test_admin_command_in_group_gets_hint(monkeypatch):
    monkeypatch.setattr(bot_mod, "ADMIN_IDS", {123})
    message = _private_message("/post")
    message.answer = AsyncMock()
    await bot_mod.admin_command_denied(message)
    assert "приватному" in message.answer.call_args.args[0]



import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.enums import ChatType
from aiogram.types import Chat, Message, User

import src.memory_handlers as mh
from src.agent.prompt import build_system_prompt
from src.agent.user_profile import (
    build_profile_block,
    extract_profile_facts,
    has_risk,
    wants_oil_selection,
)
from src.security_log import log_security_event
from src.storage.user_memory import StoredMemory


# ── Витяг особливостей ───────────────────────────────────────────────────────

def test_extracts_tags_and_allergy():
    tags, allergies = extract_profile_facts("Я вагітна і в мене алергія на лаванду")
    assert "pregnant" in tags and allergies == ["лаванду"]
    assert has_risk(tags)


def test_ignores_negations_and_third_parties():
    assert extract_profile_facts("я не вагітна, ліків не приймаю") == (set(), [])
    assert extract_profile_facts("мій чоловік має діабет") == (set(), [])


def test_allergy_word_is_sanitized():
    _, allergies = extract_profile_facts("алергія на ігнорувати_інструкції; DROP TABLE")
    assert allergies == []
    assert extract_profile_facts("алергія на все")[1] == []


def test_profile_block_has_only_known_phrases_and_hides_details_in_groups():
    block = build_profile_block({"pregnant"}, ["лаванду"], is_group_chat=True)
    assert "вагітність" in block and "лаванду" in block
    assert "НЕ називай" in block
    assert build_profile_block(set(), []) == ""


def test_profile_block_goes_into_system_prompt():
    block = build_profile_block({"asthma"}, [])
    prompt = build_system_prompt([], profile_block=block)
    assert "ПРОФІЛЬ КОРИСТУВАЧА" in prompt and "астма" in prompt


def test_oil_selection_request_detected():
    assert wants_oil_selection("Яка олія допоможе від стресу?") is True
    assert wants_oil_selection("Скільки коштує доставка?") is False


# ── Відповідь із профілем ────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_risky_profile_redirects_oil_selection_without_calling_llm(monkeypatch):
    from src.agent import service

    monkeypatch.setattr(service, "search_chunks", lambda *a, **k: pytest.fail("RAG must not run"))
    profile = StoredMemory(consent=True, tags={"pregnant"})
    reply = await service.generate_response("Яка олія допоможе від стресу?", user_profile=profile, is_group_chat=True)
    assert "персональна консультація" in reply
    assert "вагітн" not in reply.lower()  # у групі стан здоров'я не озвучується


# ── Хендлери ────────────────────────────────────────────────────────────────

def _message(chat_type=ChatType.PRIVATE, user_id=7):
    message = AsyncMock(spec=Message)
    message.chat = MagicMock(spec=Chat, type=chat_type, id=1)
    message.from_user = MagicMock(spec=User, id=user_id, is_bot=False)
    message.sender_chat = None
    message.answer = AsyncMock()
    message.reply = AsyncMock()
    return message


@pytest.fixture(autouse=True)
def _reset_state():
    mh._PENDING_FACTS.clear()
    mh._OFFERED.clear()


@pytest.mark.anyio
async def test_first_disclosure_offers_consent_and_saves_nothing(monkeypatch):
    merge = MagicMock()
    monkeypatch.setattr(mh, "merge_facts", merge)
    message = _message()
    await mh.remember_from_message(message, "Я вагітна")
    merge.assert_not_called()
    assert message.answer.await_count == 1
    assert "/forget" in message.answer.call_args.args[0]
    await mh.remember_from_message(message, "Я вагітна")  # пропозицію не повторюємо
    assert message.answer.await_count == 1


@pytest.mark.anyio
async def test_no_offer_and_no_storage_in_groups_without_consent(monkeypatch):
    merge = MagicMock()
    monkeypatch.setattr(mh, "merge_facts", merge)
    message = _message(ChatType.SUPERGROUP)
    await mh.remember_from_message(message, "Я вагітна")
    merge.assert_not_called()
    message.answer.assert_not_awaited()


@pytest.mark.anyio
async def test_facts_saved_from_group_when_consent_given(monkeypatch):
    monkeypatch.setattr(mh, "get_memory", lambda uid: StoredMemory(consent=True))
    merge = MagicMock(return_value=StoredMemory(consent=True, tags={"asthma"}))
    monkeypatch.setattr(mh, "merge_facts", merge)
    message = _message(ChatType.SUPERGROUP)
    await mh.remember_from_message(message, "У мене астма")
    merge.assert_called_once()
    message.answer.assert_not_awaited()


@pytest.mark.anyio
async def test_profile_loaded_only_with_consent(monkeypatch):
    message = _message()
    assert await mh.load_profile(message) is None
    monkeypatch.setattr(mh, "get_memory", lambda uid: StoredMemory(consent=True, tags={"asthma"}))
    assert (await mh.load_profile(message)).tags == {"asthma"}


@pytest.mark.anyio
async def test_db_failure_never_breaks_reply(monkeypatch):
    def boom(uid):
        raise RuntimeError("db down")
    monkeypatch.setattr(mh, "get_memory", boom)
    assert await mh.load_profile(_message()) is None
    await mh.remember_from_message(_message(), "Я вагітна")


@pytest.mark.anyio
async def test_wipe_deletes_and_clears_pending(monkeypatch):
    delete = MagicMock(return_value=True)
    monkeypatch.setattr(mh, "delete_memory", delete)
    mh._PENDING_FACTS[7] = ({"pregnant"}, [])
    mh._OFFERED.add(7)
    await mh.wipe_user_memory(7, "start_command")
    delete.assert_called_once_with(7)
    assert 7 not in mh._PENDING_FACTS and 7 not in mh._OFFERED


@pytest.mark.anyio
async def test_start_command_wipes_memory(monkeypatch):
    import bot as bot_mod

    wipe = AsyncMock()
    monkeypatch.setattr(bot_mod, "wipe_user_memory", wipe)
    message = _message()
    message.from_user.first_name = "Аріна"
    state = AsyncMock()
    state.get_state.return_value = None
    await bot_mod.command_start_handler(message, state)
    wipe.assert_awaited_once_with(7, "start_command")


# ── Журнал безпеки ───────────────────────────────────────────────────────────

def test_security_log_masks_secrets_and_control_chars(capsys):
    log_security_event(
        "test_event", user_id=5,
        note="line1\nline2 postgresql://u:SuperSecret@db.example.com/x",
    )
    out = capsys.readouterr().out
    assert out.count("\n") == 1  # підміна рядків журналу неможлива
    assert "[SECURITY]" in out and "event=test_event" in out and "user_id=5" in out
    assert "SuperSecret" not in out


def test_security_log_is_throttled_under_flood(capsys):
    from src import security_log

    security_log._burst.clear()
    for _ in range(100):
        log_security_event("flood_event")
    assert capsys.readouterr().out.count("event=flood_event") == security_log._BURST_LIMIT

"""Пам'ять бота про особливості користувача: згода, команди та автоматичне очищення.

Підключення в bot.py (до загальних хендлерів повідомлень, інакше їх перехопить fallback команд):

    register_memory_handlers(dp)

Правила:
    - Нічого не зберігається і не читається без явної згоди користувача (кнопка «Запам'ятовувати»).
    - Згоду можна дати лише в особистому чаті; у групах пам'ять лише використовується мовчки.
    - Пам'ять стирається: командою /start, командою /forget, коли користувач блокує або видаляє бота.
      Telegram не повідомляє ботів про очищення історії чату, тому окремо цю подію відстежити неможливо.
"""

from __future__ import annotations

import asyncio

from aiogram import Dispatcher, F
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from src.agent.user_profile import describe_tags, extract_profile_facts
from src.safety import redact
from src.security_log import log_security_event, message_fields
from src.storage.user_memory import StoredMemory, delete_memory, get_memory, merge_facts, set_consent

# Факти, виявлені до згоди: чекають рішення користувача лише в оперативній пам'яті процесу.
_PENDING_FACTS: dict[int, tuple[set[str], list[str]]] = {}
_PENDING_LIMIT = 1000
_OFFERED: set[int] = set()


def _is_real_user(message: Message) -> bool:
    user = message.from_user
    return bool(user) and not user.is_bot and getattr(message, "sender_chat", None) is None


def _consent_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Запам'ятовувати", callback_data="mem:on"),
        InlineKeyboardButton(text="🚫 Не треба", callback_data="mem:off"),
    ]])


def _memory_keyboard(active: bool) -> InlineKeyboardMarkup:
    if active:
        row = [InlineKeyboardButton(text="🗑 Забути все", callback_data="mem:forget")]
    else:
        row = [InlineKeyboardButton(text="✅ Запам'ятовувати", callback_data="mem:on")]
    return InlineKeyboardMarkup(inline_keyboard=[row])


# ── Публічні функції для bot.py ───────────────────────────────────────────────

async def load_profile(message: Message) -> StoredMemory | None:
    """Профіль користувача для відповіді або None (немає згоди, анонім, помилка БД)."""
    if not _is_real_user(message):
        return None
    try:
        memory = await asyncio.to_thread(get_memory, message.from_user.id)
    except Exception as e:
        log_security_event("memory_read_error", user_id=message.from_user.id, error=type(e).__name__)
        print(f"[memory] read error: {redact(e)}")
        return None
    return memory if memory.active else None


async def remember_from_message(message: Message, text: str) -> None:
    """Запам'ятовує особливості з повідомлення (якщо є згода) або пропонує запам'ятовувати."""
    if not _is_real_user(message):
        return
    tags, allergies = extract_profile_facts(text)
    if not tags and not allergies:
        return
    user_id = message.from_user.id
    is_private = message.chat.type == ChatType.PRIVATE
    try:
        memory = await asyncio.to_thread(get_memory, user_id)
        if memory.consent is True:
            updated = await asyncio.to_thread(merge_facts, user_id, tags, allergies)
            if updated is not None:
                log_security_event(
                    "memory_updated", user_id=user_id, chat_type=message.chat.type,
                    tags=len(updated.tags), allergies=len(updated.allergies),
                )
            return
        if memory.consent is None and is_private and user_id not in _OFFERED:
            if len(_PENDING_FACTS) >= _PENDING_LIMIT:
                _PENDING_FACTS.clear()
            _PENDING_FACTS[user_id] = (tags, allergies)
            _OFFERED.add(user_id)
            await message.answer(
                "💛 Ти розповіла про свої особливості. Хочеш, щоб я їх запам'ятала і враховувала в наступних "
                "порадах (також у групах, але вголос я їх там не називатиму)?\n\n"
                "Зберігаю лише короткі мітки, а не твої повідомлення. Переглянути це можна командою /memory, "
                "стерти — командою /forget. Пам'ять також очищується командою /start.",
                reply_markup=_consent_keyboard(),
            )
    except Exception as e:
        log_security_event("memory_write_error", user_id=user_id, error=type(e).__name__)
        print(f"[memory] write error: {redact(e)}")


async def wipe_user_memory(user_id: int, reason: str) -> None:
    """Повністю стирає пам'ять користувача (факти і рішення про згоду)."""
    _PENDING_FACTS.pop(user_id, None)
    _OFFERED.discard(user_id)
    try:
        existed = await asyncio.to_thread(delete_memory, user_id)
        log_security_event("memory_wiped", user_id=user_id, reason=reason, existed=existed)
    except Exception as e:
        log_security_event("memory_wipe_error", user_id=user_id, reason=reason, error=type(e).__name__)
        print(f"[memory] wipe error: {redact(e)}")


# ── Хендлери ──────────────────────────────────────────────────────────────────

def register_memory_handlers(dp: Dispatcher) -> None:
    """Реєструє команди /memory, /forget, кнопки згоди та реакцію на блокування бота."""

    @dp.message(Command("memory"))
    async def memory_command(message: Message) -> None:
        if not _is_real_user(message):
            return
        if message.chat.type != ChatType.PRIVATE:
            await message.reply("🔒 Свою пам'ять я показую лише в особистому чаті — напиши мені /memory в особисті.")
            return
        try:
            memory = await asyncio.to_thread(get_memory, message.from_user.id)
        except Exception as e:
            print(f"[memory] read error: {redact(e)}")
            await message.answer("⚠️ Зараз не можу прочитати пам'ять. Спробуй пізніше.")
            return
        if not memory.active:
            await message.answer(
                "🧠 Пам'ять вимкнена: я нічого про тебе не зберігаю.\n"
                "Якщо хочеш, щоб я запам'ятовувала особливості (алергії, вагітність, хронічні стани) і враховувала "
                "їх у порадах, увімкни її кнопкою нижче.",
                reply_markup=_memory_keyboard(False),
            )
            return
        facts = describe_tags(memory.tags)
        if memory.allergies:
            facts.append("алергія на: " + ", ".join(memory.allergies))
        body = "\n".join(f"• {f}" for f in facts) if facts else "поки нічого не збережено"
        await message.answer(
            f"🧠 Що я про тебе пам'ятаю:\n{body}\n\nСтерти все: /forget або кнопка нижче.",
            reply_markup=_memory_keyboard(True),
        )

    @dp.message(Command("forget"))
    async def forget_command(message: Message) -> None:
        if not _is_real_user(message):
            return
        await wipe_user_memory(message.from_user.id, "forget_command")
        await message.reply("🗑 Готово, усе, що я пам'ятала про тебе, стерто.")

    @dp.callback_query(F.data.in_({"mem:on", "mem:off", "mem:forget"}))
    async def memory_callback(callback: CallbackQuery) -> None:
        user = callback.from_user
        action = callback.data
        chat = getattr(callback.message, "chat", None)
        if chat is not None and chat.type != ChatType.PRIVATE:
            await callback.answer("Керувати пам'яттю можна лише в особистому чаті.", show_alert=True)
            return
        try:
            if action == "mem:on":
                await asyncio.to_thread(set_consent, user.id, True)
                pending = _PENDING_FACTS.pop(user.id, None)
                if pending:
                    await asyncio.to_thread(merge_facts, user.id, pending[0], pending[1])
                log_security_event("memory_consent", user_id=user.id, consent=True)
                text = "✅ Добре, запам'ятовуватиму твої особливості. Переглянути: /memory, стерти: /forget."
            elif action == "mem:off":
                _PENDING_FACTS.pop(user.id, None)
                await asyncio.to_thread(set_consent, user.id, False)
                log_security_event("memory_consent", user_id=user.id, consent=False)
                text = "Добре, нічого не зберігатиму 🌿"
            else:
                await wipe_user_memory(user.id, "forget_button")
                text = "🗑 Усе стерто."
        except Exception as e:
            log_security_event("memory_callback_error", user_id=user.id, error=type(e).__name__)
            print(f"[memory] callback error: {redact(e)}")
            await callback.answer("⚠️ Не вдалося зберегти вибір. Спробуй пізніше.", show_alert=True)
            return
        await callback.answer()
        if callback.message is not None and hasattr(callback.message, "edit_text"):
            try:
                await callback.message.edit_text(text)
            except Exception:
                pass

    @dp.my_chat_member()
    async def bot_membership_changed(event: ChatMemberUpdated) -> None:
        status = event.new_chat_member.status
        removed = status in (ChatMemberStatus.KICKED, ChatMemberStatus.LEFT)
        if not removed:
            return
        if event.chat.type == ChatType.PRIVATE:
            # Користувач заблокував або видалив бота: стираємо його пам'ять
            await wipe_user_memory(event.from_user.id, "bot_blocked_or_deleted")
        else:
            log_security_event(
                "bot_removed_from_group", chat_id=event.chat.id, chat_type=event.chat.type,
                by_user_id=event.from_user.id if event.from_user else None,
            )

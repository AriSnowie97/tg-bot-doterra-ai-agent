# Standard
import os
import asyncio
import re
# Special
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import BaseFilter, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, WebAppInfo, MenuButtonWebApp
from aiogram.enums import ChatAction, ChatType, MessageEntityType
# Local
from src.agent import generate_response
from src.publisher import publish_channel_post
from src.scheduler import setup_scheduler
from src.storage.feedback import ensure_feedback_table, save_vote, get_vote_counts
from handlers.states import AskStates, ScreeningStates
from src.content.sync_content import run_sync
from src.middleware import RateLimitMiddleware, CallbackRateLimitMiddleware
from src.safety import redact, safe_error, append_and_format_dialogue
from src.stickers import (
    load_stickers,
    get_or_load_sticker,
    get_welcome_sticker,
    get_farewell_sticker,
    should_accompany_with_sticker,
    classify_casual_interaction,
    is_greeting,
    is_farewell,
    should_reply_to_user_sticker,
    detect_sticker_emojis_for_text,
    STICKER_SET_NAME,
)


# Loading variables from a dotenv file
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

def _get_channel_id() -> str:
    """Отримує актуальний CHANNEL_ID із змінних середовища."""
    return (os.getenv("CHANNEL_ID") or "").strip()


# ID адміністраторів бота, які можуть викликати /post вручну.
# Заповни своїм Telegram user_id (отримати через @userinfobot).
ADMIN_IDS: set[int] = {
    int(uid) for uid in os.getenv("ADMIN_IDS", "").split(",") if uid.strip().isdigit()
}


class AdminFilter(BaseFilter):
    """Пропускає лише адмінів. Порожній ADMIN_IDS = доступу немає ні в кого."""

    async def __call__(self, message: Message) -> bool:
        return bool(message.from_user) and message.from_user.id in ADMIN_IDS

# Creating a dispatcher
dp = Dispatcher(storage=MemoryStorage())
# Ліміт частоти/довжини — лише для повідомлень, які бот реально обробить (адміни без ліміту).
# Звичайні розмови в групі не зараховуються. _is_addressed визначена нижче — викликається пізно.
dp.message.outer_middleware(
    RateLimitMiddleware(
        exempt_ids=ADMIN_IDS,
        should_limit=lambda m: _is_addressed(m) or (m.text or "").startswith("/"),
    )
)
dp.callback_query.outer_middleware(CallbackRateLimitMiddleware(exempt_ids=ADMIN_IDS))

# Кеш username бота — заповнюється при старті
_BOT_USERNAME: str = ""


async def _keep_typing(bot: Bot, chat_id: int, stop_event: asyncio.Event) -> None:
    """Підтримує індикатор 'пише...' у шапці чату поки не встановлено stop_event.

    Telegram автоматично гасить typing через ~5 сек — тому шлємо його
    кожні 4 сек у фоновому таску.
    """
    while not stop_event.is_set():
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(4)


def _feedback_keyboard(message_id: int, chat_id: int, likes: int = 0, dislikes: int = 0) -> InlineKeyboardMarkup:
    """Повертає inline-клавіатуру з кнопками 👍/👎 і лічильниками."""
    like_label    = f"👍 {likes}"    if likes    else "👍"
    dislike_label = f"👎 {dislikes}" if dislikes else "👎"
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=like_label,
            callback_data=f"fb:like:{message_id}:{chat_id}"
        ),
        InlineKeyboardButton(
            text=dislike_label,
            callback_data=f"fb:dislike:{message_id}:{chat_id}"
        ),
    ]])


async def _reply_with_feedback(message: Message, text: str, sticker_id: str | None = None) -> None:
    """Надсилає reply з текстом відповіді і кнопками 👍/👎 та посиланнями на гайди.
    
    Якщо передано sticker_id, надсилає відповідний стікер перед або разом із текстом.
    """
    if sticker_id:
        try:
            await message.reply_sticker(sticker_id)
        except Exception as e:
            print(f"[_reply_with_feedback] Sticker error: {redact(e)}")

    webapp_url = os.getenv("WEBAPP_URL", "https://arisnowie97.github.io/tg-bot-doterra-ai-agent/")
    
    # Шукаємо всі маркдаун посилання виду [Текст](slug)
    pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    links = re.findall(pattern, text)
    
    # Замінюємо [Текст](slug) просто на Текст
    clean_text = re.sub(pattern, r'\1', text)
    clean_text = re.sub(r'https?://(?:www\.)?doterra\.com[^\s\)]*', '', clean_text).strip()
    clean_text = clean_text.replace("🪨", "🌿").replace("🫂", "🌿").replace("🗿", "")
    clean_text = re.sub(r'\b(я\s+—\s+віртуальний\s+гід|я\s+віртуальний\s+гід|віртуальний\s+гід-помічник|гід-помічник|віртуальний\s+гід|твій\s+гід|ваш\s+гід)\b', 'помічниця', clean_text, flags=re.IGNORECASE)
    
    sent = await message.reply(clean_text)
    keyboard = _feedback_keyboard(sent.message_id, sent.chat.id)
    
    if links:
        seen_slugs = set()
        for link_text, slug in links:
            slug = slug.strip()
            # Повністю блокуємо зовнішні посилання на сайт doterra.com
            if "doterra.com" in slug.lower():
                continue
            if slug not in seen_slugs:
                seen_slugs.add(slug)
                if slug.startswith("http://") or slug.startswith("https://"):
                    # Авторитетні наукові дослідження (PubMed тощо) відкриваємо як URL
                    keyboard.inline_keyboard.insert(0, [
                        InlineKeyboardButton(text=f"📖 {link_text}", url=slug)
                    ])
                else:
                    # Внутрішні статті довідника відкриваємо в Telegram Mini App
                    clean_slug = slug.lstrip("#/").replace("article/", "")
                    keyboard.inline_keyboard.insert(0, [
                        InlineKeyboardButton(text=f"📖 {link_text}", web_app=WebAppInfo(url=f"{webapp_url}#/article/{clean_slug}"))
                    ])
                
    await sent.edit_reply_markup(reply_markup=keyboard)


@dp.message(Command("start"))
async def command_start_handler(message: Message, state: FSMContext) -> None:
    # Скидаємо стан скринінгу при /start
    await state.clear()
    
    # Вітальний стікер зі стікерпаку aromaaitgbot («Привіт!»)
    welcome_sticker = await get_welcome_sticker(message.bot)
    if welcome_sticker:
        try:
            await message.answer_sticker(welcome_sticker)
        except Exception as e:
            print(f"[command_start] Sticker error: {redact(e)}")

    webapp_url = os.getenv("WEBAPP_URL", "https://arisnowie97.github.io/tg-bot-doterra-ai-agent/")
    
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="📱 Відкрити Mini App", 
            web_app=WebAppInfo(url=webapp_url)
        )
    ]])

    await message.answer(
        f"👋 Привіт, {message.from_user.first_name}!\n\n"
        "🌿 Мене звати Арома, я помічниця Наталії Котелянської у нашому боті Aroma Assistant.\n\n"
        "Я з радістю допоможу тобі познайомитися з ефірними оліями doTERRA "
        "та іншими чудовими продуктами, які є у Наталії 🌸\n\n"
        "Просто напиши своє запитання — і я з радістю підкажу 🔍",
        reply_markup=markup
    )


@dp.message(Command("ask"))
async def command_ask_handler(message: Message, command: CommandObject, state: FSMContext) -> None:
    """/ask [питання] — запит до бота в групі чи приватному чаті.

    Два режими:
    - /ask               → бот просить написати питання наступним повідомленням (FSM).
    - /ask <текст>       → бот відповідає одразу (як раніше).

    Корисна альтернатива @mention у групах, де Privacy Mode обмежує видимість.
    """
    # Режим 1: /ask без аргументів — переходимо в стан очікування питання
    if not command.args:
        await state.set_state(AskStates.waiting_for_question)
        await message.reply(
            "🌿 Напиши своє питання наступним повідомленням 👇"
        )
        return

    # Режим 2: /ask <текст> — відповідаємо одразу
    ask_text = command.args.strip()
    from src.agent.specialist import is_health_complaint_query, has_red_flags
    ask_complaint = is_health_complaint_query(ask_text)
    ask_red_flag = has_red_flags(ask_text)

    accompany_sticker = None
    if not ask_red_flag and should_accompany_with_sticker(ask_text, is_complaint=ask_complaint):
        accompany_sticker = await get_or_load_sticker(message.bot)

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(
        _keep_typing(message.bot, message.chat.id, stop_typing)
    )

    try:
        response = await generate_response(ask_text)
        stop_typing.set()
        typing_task.cancel()
        await _reply_with_feedback(message, response, sticker_id=accompany_sticker)
    except Exception as e:
        stop_typing.set()
        typing_task.cancel()
        await message.reply("😔 Виникла помилка при обробці запиту. Спробуй ще раз.")
        print(f"[command_ask] Error: {redact(e)}")


@dp.message(AskStates.waiting_for_question, F.text, ~F.text.startswith("/"))
async def ask_question_handler(message: Message, state: FSMContext) -> None:
    """Обробляє питання після того, як користувач ввів /ask без аргументів.

    Скидає FSM-стан і обробляє текст як звичайне питання до RAG-агента.
    """
    await state.clear()

    user_text = message.text.strip()
    if not user_text:
        await message.reply("🌿 Запитай мене що-небудь про ефірні олії doTERRA!")
        return

    from src.agent.specialist import is_health_complaint_query, has_red_flags
    user_complaint = is_health_complaint_query(user_text)
    user_red_flag = has_red_flags(user_text)

    accompany_sticker = None
    if not user_red_flag and should_accompany_with_sticker(user_text, is_complaint=user_complaint):
        accompany_sticker = await get_or_load_sticker(message.bot)

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(
        _keep_typing(message.bot, message.chat.id, stop_typing)
    )

    try:
        response = await generate_response(user_text)
        stop_typing.set()
        typing_task.cancel()

        if not response or not response.strip():
            await message.reply("😔 Не вдалося сформувати відповідь. Спробуй перефразувати запит.")
            return

        await _reply_with_feedback(message, response, sticker_id=accompany_sticker)
    except Exception as e:
        stop_typing.set()
        typing_task.cancel()
        await message.reply("😔 Виникла помилка при обробці запиту. Спробуй ще раз.")
        print(f"[ask_question] Error: {redact(e)}")


@dp.message(Command("post"), AdminFilter(), F.chat.type == ChatType.PRIVATE)
async def command_post_handler(message: Message, bot: Bot) -> None:
    """Ручна публікація посту в канал — тільки для адміністраторів.

    Використання: надіслати /post у приватний чат з ботом.
    Бот одразу публікує новий пост у канал і повідомляє про результат.
    """

    channel_id = _get_channel_id()
    if not channel_id:
        await message.answer(
            "⚠️ CHANNEL_ID не задано у .env — публікацію неможливо виконати."
        )
        return

    await message.answer("⏳ Генерую пост... Це може зайняти 30–60 секунд.")

    try:
        post_url = await publish_channel_post(bot)
        if post_url:
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📖 Читати далі в каналі", url=post_url)]
                ]
            )
            await message.answer(
                f"✅ <b>Пост успішно опубліковано у канал!</b>\n\n👉 <a href=\"{post_url}\">Читати далі</a>",
                parse_mode="HTML",
                reply_markup=kb,
            )
        else:
            await message.answer("✅ Пост успішно опубліковано у канал!")
    except Exception as e:
        await message.answer(f"❌ Помилка при публікації ({safe_error(e)}). Деталі — у логах сервера.")
        print(f"[bot] /post error: {redact(e)}")


@dp.message(Command("sync_db"), AdminFilter(), F.chat.type == ChatType.PRIVATE)
async def command_sync_db_handler(message: Message, bot: Bot) -> None:
    """Ручне оновлення бази знань (синхронізація файлів) — тільки для адміністраторів."""

    await message.answer(
        "⏳ <b>Запускаю синхронізацію бази знань...</b>\n\n"
        "⚙️ Увімкнено ліміт безкоштовного тарифу Gemini API: "
        "обробка партіями по <b>45–50 чанків</b> із паузою <b>15 хвилин</b> між ними.\n"
        "Я надсилатиму статус по кожній партії.",
        parse_mode="HTML"
    )

    loop = asyncio.get_running_loop()

    def tg_progress(msg: str) -> None:
        """Надсилає оновлення прогресу в Telegram."""
        try:
            asyncio.run_coroutine_threadsafe(
                message.answer(msg, parse_mode="HTML"), loop
            )
        except Exception as pe:
            print(f"[bot] sync_db tg_progress error: {redact(pe)}")

    try:
        # Запускаємо синхронізацію у фоновому потоці, щоб не блокувати бота
        stats = await asyncio.to_thread(run_sync, tg_progress)
        
        if stats["errors"]:
            error_msg = "\n".join([f"• {err}" for err in stats["errors"][:10]])
            if len(stats["errors"]) > 10:
                error_msg += f"\n...та ще {len(stats['errors']) - 10} помилок."
            await message.answer(
                f"⚠️ Синхронізацію завершено з окремими помилками:\n{error_msg}\n\n"
                f"📊 Оброблено карток: {stats['products']}\n"
                f"📊 Знайдено чанків: {stats['chunks_found']}",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"✅ <b>Базу знань повністю оновлено!</b>\n\n"
                f"📦 Картки: <b>{stats['products']}</b>\n"
                f"📄 Чанки: <b>{stats['chunks_found']}</b>",
                parse_mode="HTML"
            )
    except Exception as e:
        await message.answer(f"❌ Критична помилка під час синхронізації ({safe_error(e)}). Деталі — у логах сервера.")
        print(f"[bot] /sync_db error: {redact(e)}")


@dp.message(Command("post", "sync_db"))
async def admin_command_denied(message: Message) -> None:
    """Fallback для не-адмінів: не віддаємо адмін-команди загальному обробнику F.text."""
    await message.answer("⛔ У тебе немає прав для цієї команди.")


def _is_addressed(message: Message) -> bool:
    """Перевіряє, чи звернення адресоване боту.

    Повертає True якщо:
    - Приватний чат (private) — завжди True.
    - Група/супергрупа: повідомлення є Reply на повідомлення бота.
    - Група/супергрупа: у тексті є @mention бота.
    """
    chat_type = message.chat.type

    # Приватний чат — відповідаємо завжди
    if chat_type == ChatType.PRIVATE:
        return True

    # Reply на повідомлення бота
    if (
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.username == _BOT_USERNAME
    ):
        return True

    # @mention бота у тексті або підписі
    if message.entities and _BOT_USERNAME:
        text_source = message.text or message.caption or ""
        for entity in message.entities:
            if entity.type == MessageEntityType.MENTION and text_source:
                mention_text = text_source[
                    entity.offset : entity.offset + entity.length
                ]
                if mention_text.lstrip("@").lower() == _BOT_USERNAME.lower():
                    return True

    return False


def _strip_mention(text: str, bot_username: str) -> str:
    """Видаляє @mention бота з початку або кінця тексту повідомлення."""
    mention = f"@{bot_username}"
    text = text.strip()
    if text.lower().startswith(mention.lower()):
        text = text[len(mention):].strip()
    if text.lower().endswith(mention.lower()):
        text = text[: -len(mention)].strip()
    return text or text


@dp.message(F.text)
async def on_message(message: Message, bot: Bot, state: FSMContext) -> None:
    """Обробник текстових повідомлень.

    Приватний чат: відповідає на будь-яке повідомлення.
    Група / супергрупа: відповідає тільки на @mention або Reply на бота.

    Скринінг (Блоки 1–3):
    - При скарзі/симптомі вмикається screening_mode='active'/'red_flag'
    - Стан зберігається в FSMContext між повідомленнями
    - conversation_context накопичує весь діалог для RAG і LLM
    - Red_flag залишається до /start або нового запиту без скарги
    """
    # Ігноруємо повідомлення у групах, якщо бота не згадано
    if not _is_addressed(message):
        return

    # Очищуємо текст від @mention бота
    user_text = _strip_mention(message.text, _BOT_USERNAME) if _BOT_USERNAME else message.text
    if not user_text:
        await message.reply("🌿 Запитай мене що-небудь про ефірні олії doTERRA!")
        return

    # ── Завантажуємо стан скринінгу з FSMContext ──────────────────────────────
    fsm_data = await state.get_data()
    stored_mode: str | None = fsm_data.get("screening_mode")        # 'active'|'red_flag'|None
    stored_turns: list[dict[str, str]] = fsm_data.get("screening_turns") or []
    # Зворотна сумісність: якщо в стані був старий строковий screening_history
    if not stored_turns and fsm_data.get("screening_history"):
        stored_turns = [{"role": "user", "text": str(fsm_data["screening_history"])[:500]}]

    # Визначаємо чи це відповідь на скринінг чи новий незалежний запит
    from src.agent.specialist import is_health_complaint_query, has_red_flags
    is_new_complaint = is_health_complaint_query(user_text)
    is_new_red_flag  = has_red_flags(user_text)

    # ── Скидання стану якщо користувач перейшов до іншої теми або завершив скринінг ─
    if stored_mode == "red_flag":
        if not is_new_red_flag and not is_new_complaint:
            stored_mode = None
            stored_turns = []
            await state.clear()
    elif stored_mode == "active":
        should_casual, _, _ = classify_casual_interaction(user_text)
        if should_casual or len(stored_turns) >= 6:
            stored_mode = None
            stored_turns = []
            await state.clear()

    # ── Перевіряємо, чи це повсякденна коротка репліка (вітання/подяка/реакція) ──────────────
    if stored_mode not in ("active", "red_flag") and not is_new_complaint and not is_new_red_flag:
        should_casual, reply_text, pref_emojis = classify_casual_interaction(user_text)
        if should_casual:
            if is_greeting(user_text):
                casual_sticker = await get_welcome_sticker(bot)
            elif is_farewell(user_text):
                casual_sticker = await get_farewell_sticker(bot)
            else:
                casual_sticker = await get_or_load_sticker(bot, preferred_emojis=pref_emojis)

            if casual_sticker:
                try:
                    await message.reply_sticker(casual_sticker)
                    if reply_text:
                        await message.answer(reply_text)
                    return
                except Exception as e:
                    print(f"[on_message] Casual sticker error: {redact(e)}")

    # Визначаємо, чи супроводжувати коротке питання стікером із паку aromaaitgbot
    should_accompany = False
    if stored_mode != "red_flag" and not is_new_red_flag:
        should_accompany = should_accompany_with_sticker(user_text, is_complaint=is_new_complaint)

    # Якщо є активний скринінг — продовжуємо його
    if stored_mode in ("active", "red_flag"):
        active_turns, conversation_context = append_and_format_dialogue(
            stored_turns,
            new_user_text=user_text,
        )
        if stored_mode == "active" and (is_new_red_flag or has_red_flags(conversation_context)):
            pass_mode = "red_flag"
        else:
            pass_mode = stored_mode
    else:
        # Новий запит
        active_turns = []
        conversation_context = None
        pass_mode = "red_flag" if is_new_red_flag else None

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(
        _keep_typing(bot, message.chat.id, stop_typing)
    )

    try:
        response = await generate_response(
            user_text,
            screening_mode=pass_mode,
            conversation_context=conversation_context,
        )

        stop_typing.set()
        typing_task.cancel()

        if not response or not response.strip():
            print(f"[on_message] Empty response for query: {user_text!r}")
            await message.reply("😔 Не вдалося сформувати відповідь. Спробуй перефразувати запит.")
            return

        # ── Оновлюємо стан скринінгу після отримання відповіді ───────────────
        if pass_mode is None:
            if is_new_red_flag:
                new_mode = "red_flag"
            elif is_new_complaint:
                new_mode = "active"
            else:
                new_mode = None
        else:
            new_mode = pass_mode

        # Зберігаємо стан тільки для активного скринінгу (red_flag вже надав остаточну пораду)
        if new_mode == "active":
            final_turns, final_context = append_and_format_dialogue(
                active_turns if pass_mode is not None else [],
                new_user_text=user_text if pass_mode is None else None,
                bot_response=response,
            )
            await state.set_state(ScreeningStates.in_progress)
            await state.update_data(
                screening_mode="active",
                screening_turns=final_turns,
                screening_history=final_context,
            )
        else:
            # Загальне питання або червоний прапор — очищаємо стан
            await state.clear()

        # Підбираємо найбільш відповідний за темою та емоцією стікер на основі запиту та сформованої відповіді
        accompany_sticker = None
        if should_accompany:
            pref_emojis = detect_sticker_emojis_for_text(user_text, response_text=response)
            accompany_sticker = await get_or_load_sticker(bot, preferred_emojis=pref_emojis)

        await _reply_with_feedback(message, response, sticker_id=accompany_sticker)

    except Exception as e:
        stop_typing.set()
        typing_task.cancel()
        await message.reply(
            "😔 Виникла помилка при обробці запиту. Спробуй ще раз."
        )
        print(f"[on_message] Error: {type(e).__name__}: {redact(e)}")


@dp.message(F.sticker)
async def on_sticker(message: Message, bot: Bot) -> None:
    """Обробник вхідних стікерів від користувача.

    Якщо користувач надіслав стікер у приватному чаті або відповів боту в групі,
    бот іноді (з високою ймовірністю) відповідає стікером із паку aromaaitgbot.
    """
    if not _is_addressed(message):
        return

    if should_reply_to_user_sticker():
        input_emoji = message.sticker.emoji if message.sticker else None
        pref_emojis = [input_emoji] if input_emoji else None
        reply_sticker = await get_or_load_sticker(bot, preferred_emojis=pref_emojis)
        if reply_sticker:
            try:
                await message.reply_sticker(reply_sticker)
                return
            except Exception as e:
                print(f"[on_sticker] Reply sticker error: {redact(e)}")

    await message.reply("🌿")


# ---------------------------------------------------------------------------
# Обробник кнопок 👍 / 👎
# ---------------------------------------------------------------------------

@dp.callback_query(F.data.startswith("fb:"))
async def feedback_callback(callback: CallbackQuery) -> None:
    """Обробляє натискання кнопок 👍/👎 під відповіддю бота.

    Формат callback_data: fb:<vote>:<message_id>:<chat_id>
    """
    await callback.answer()  # знімаємо годинник з кнопки

    parts = callback.data.split(":")
    if len(parts) != 4:
        return

    _, vote, msg_id_str, chat_id_str = parts
    try:
        msg_id  = int(msg_id_str)
        chat_id = int(chat_id_str)
    except ValueError:
        return

    user_id = callback.from_user.id

    # Зберігаємо питання для аналітики (беремо з reply-контексту якщо є)
    query_text = ""
    if callback.message and callback.message.reply_to_message:
        query_text = callback.message.reply_to_message.text or ""

    # Захист конфіденційності здоров'я (Privacy-by-Design):
    # Якщо питання містило медичні скарги або червоні прапори, не зберігаємо чутливий текст у БД
    from src.agent.specialist import is_health_complaint_query, has_red_flags
    if is_health_complaint_query(query_text) or has_red_flags(query_text):
        query_text = "[Захищено: медичне звернення / червоний прапор]"
    else:
        query_text = query_text[:500]

    # Записуємо голос у БД у фоновому потоці (не блокуємо event loop)
    try:
        result = await asyncio.to_thread(
            save_vote,
            message_id=msg_id,
            chat_id=chat_id,
            user_id=user_id,
            vote=vote,
            query_text=query_text,
        )
    except Exception as e:
        print(f"[feedback] DB error: {redact(e)}")
        await callback.answer("⚠️ Не вдалося зберегти оцінку.", show_alert=True)
        return

    # Показуємо підтвердження
    if result == "unchanged":
        emoji = "👍" if vote == "like" else "👎"
        await callback.answer(f"{emoji} Ти вже поставив цю оцінку!", show_alert=False)
        return

    # Оновлюємо лічильники на кнопках у фоновому потоці
    try:
        counts = await asyncio.to_thread(get_vote_counts, msg_id, chat_id)
        new_keyboard = _feedback_keyboard(
            msg_id, chat_id,
            likes=counts["likes"],
            dislikes=counts["dislikes"],
        )
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)
    except Exception as e:
        print(f"[feedback] keyboard update error: {redact(e)}")

    # Підтвердження користувачу
    if vote == "like":
        await callback.answer("👍 Дякую за позитивний відгук!", show_alert=False)
    else:
        await callback.answer("👎 Зрозуміло, постараємось покращити відповіді!", show_alert=False)


# Run the bot
async def main() -> None:
    global _BOT_USERNAME

    if not ADMIN_IDS:
        print("[bot] ⚠️ ADMIN_IDS порожній або невалідний — адмін-команди (/post, /sync_db) вимкнені.")

    bot = Bot(token=BOT_TOKEN)

    # Отримуємо username бота — потрібен для фільтрації @mention у групах
    me = await bot.get_me()
    _BOT_USERNAME = me.username or ""
    print(f"[bot] 🤖 Bot username: @{_BOT_USERNAME}")

    # Ініціалізуємо таблицю фідбеку (якщо не існує)
    try:
        ensure_feedback_table()
        print("[bot] ✅ Feedback table ready.")
    except Exception as e:
        print(f"[bot] ⚠️ Could not init feedback table: {redact(e)}")

    # Налаштовуємо кнопку "Меню" (Web App)
    webapp_url = os.getenv("WEBAPP_URL", "https://arisnowie97.github.io/tg-bot-doterra-ai-agent/")
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Mini App", web_app=WebAppInfo(url=webapp_url))
        )
        print("[bot] ✅ Menu button configured.")
    except Exception as e:
        print(f"[bot] ⚠️ Could not configure menu button: {redact(e)}")

    # Налаштовуємо та запускаємо планувальник публікацій
    scheduler = setup_scheduler(bot)
    scheduler.start()
    print("[bot] 🚀 Bot started with channel post scheduler.")

    # Завантажуємо стікери зі стікерпаку aromaaitgbot
    try:
        await load_stickers(bot)
    except Exception as e:
        print(f"[bot] [WARN] Could not load stickers on startup: {redact(e)}")


    try:
        await dp.start_polling(bot)
    finally:
        # Зупиняємо планувальник при завершенні бота
        scheduler.shutdown(wait=False)
        print("[bot] 🛑 Scheduler stopped.")

if __name__ == "__main__":
    asyncio.run(main())
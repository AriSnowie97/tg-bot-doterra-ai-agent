# Standard
import os
import asyncio
import re
# Special
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, WebAppInfo, MenuButtonWebApp
from aiogram.enums import ChatAction, ChatType, MessageEntityType
# Local
from src.agent import generate_response
from src.publisher import publish_channel_post
from src.scheduler import setup_scheduler
from src.storage.feedback import ensure_feedback_table, save_vote, get_vote_counts
from handlers.states import AskStates
from src.content.sync_content import run_sync


# Loading variables from a dotenv file
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# ID адміністраторів бота, які можуть викликати /post вручну.
# Заповни своїм Telegram user_id (отримати через @userinfobot).
ADMIN_IDS: list[int] = [
    int(uid) for uid in os.getenv("ADMIN_IDS", "").split(",") if uid.strip().isdigit()
]

# Creating a dispatcher
dp = Dispatcher(storage=MemoryStorage())

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


async def _reply_with_feedback(message: Message, text: str) -> None:
    """Надсилає reply з текстом відповіді і кнопками 👍/👎 та посиланнями на гайди."""
    webapp_url = os.getenv("WEBAPP_URL", "https://arisnowie97.github.io/tg-bot-doterra-ai-agent/")
    
    # Шукаємо всі маркдаун посилання виду [Текст](slug)
    pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    links = re.findall(pattern, text)
    
    # Замінюємо [Текст](slug) просто на Текст
    clean_text = re.sub(pattern, r'\1', text)
    
    sent = await message.reply(clean_text)
    keyboard = _feedback_keyboard(sent.message_id, sent.chat.id)
    
    if links:
        seen_slugs = set()
        for link_text, slug in links:
            if slug not in seen_slugs:
                seen_slugs.add(slug)
                # Додаємо кнопку відкриття Mini App
                keyboard.inline_keyboard.insert(0, [
                    InlineKeyboardButton(text=f"📖 {link_text}", web_app=WebAppInfo(url=f"{webapp_url}#/article/{slug}"))
                ])
                
    await sent.edit_reply_markup(reply_markup=keyboard)


@dp.message(Command("start"))
async def command_start_handler(message: Message) -> None:
    webapp_url = os.getenv("WEBAPP_URL", "https://arisnowie97.github.io/tg-bot-doterra-ai-agent/")
    
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="📱 Відкрити Mini App", 
            web_app=WebAppInfo(url=webapp_url)
        )
    ]])

    await message.answer(
        f"👋 Привіт, {message.from_user.first_name}!\n\n"
        "🌿 Ласкаво просимо до AI-консультанта doTERRA!\n\n"
        "Я допоможу тобі розібратись у гайдах та знайти потрібну інформацію "
        "про ефірні олії та продукти doTERRA.\n\n"
        "Просто напиши своє запитання — і я знайду відповідь 🔍",
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
    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(
        _keep_typing(message.bot, message.chat.id, stop_typing)
    )

    try:
        response = await generate_response(command.args.strip())
        stop_typing.set()
        typing_task.cancel()
        await _reply_with_feedback(message, response)
    except Exception as e:
        stop_typing.set()
        typing_task.cancel()
        await message.reply("😔 Виникла помилка при обробці запиту. Спробуй ще раз.")
        print(f"[command_ask] Error: {e}")


@dp.message(AskStates.waiting_for_question, F.text)
async def ask_question_handler(message: Message, state: FSMContext) -> None:
    """Обробляє питання після того, як користувач ввів /ask без аргументів.

    Скидає FSM-стан і обробляє текст як звичайне питання до RAG-агента.
    """
    await state.clear()

    user_text = message.text.strip()
    if not user_text:
        await message.reply("🌿 Запитай мене що-небудь про ефірні олії doTERRA!")
        return

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

        await _reply_with_feedback(message, response)
    except Exception as e:
        stop_typing.set()
        typing_task.cancel()
        await message.reply("😔 Виникла помилка при обробці запиту. Спробуй ще раз.")
        print(f"[ask_question] Error: {e}")


@dp.message(Command("post"))
async def command_post_handler(message: Message, bot: Bot) -> None:
    """Ручна публікація посту в канал — тільки для адміністраторів.

    Використання: надіслати /post у приватний чат з ботом.
    Бот одразу публікує новий пост у канал і повідомляє про результат.
    """
    user_id = message.from_user.id

    # Захист: тільки адміни або якщо ADMIN_IDS не задано (режим розробки)
    if ADMIN_IDS and user_id not in ADMIN_IDS:
        await message.answer("⛔ У тебе немає прав для цієї команди.")
        return

    if not CHANNEL_ID:
        await message.answer(
            "⚠️ CHANNEL_ID не задано у .env — публікацію неможливо виконати."
        )
        return

    await message.answer("⏳ Генерую пост... Це може зайняти 30–60 секунд.")

    try:
        await publish_channel_post(bot)
        await message.answer("✅ Пост успішно опубліковано у канал!")
    except Exception as e:
        await message.answer(f"❌ Помилка при публікації: {e}")
        print(f"[bot] /post error: {e}")


@dp.message(Command("sync_db"))
async def command_sync_db_handler(message: Message, bot: Bot) -> None:
    """Ручне оновлення бази знань (синхронізація файлів) — тільки для адміністраторів."""
    user_id = message.from_user.id

    if ADMIN_IDS and user_id not in ADMIN_IDS:
        await message.answer("⛔ У тебе немає прав для цієї команди.")
        return

    await message.answer("⏳ Запускаю синхронізацію бази знань... Це може зайняти 10-15 хвилин через ліміти API. Я повідомлю, коли закінчу.")

    try:
        # Запускаємо синхронізацію у фоновому потоці, щоб не блокувати бота
        stats = await asyncio.to_thread(run_sync)
        
        if stats["errors"]:
            error_msg = "\n".join([f"• {err}" for err in stats["errors"][:10]])
            if len(stats["errors"]) > 10:
                error_msg += f"\n...та ще {len(stats['errors']) - 10} помилок."
            await message.answer(
                f"⚠️ Синхронізацію завершено з помилками:\n{error_msg}\n\n"
                f"📊 Оброблено карток: {stats['products']}\n"
                f"📊 Знайдено чанків: {stats['chunks_found']}"
            )
        else:
            await message.answer(
                f"✅ Базу знань успішно оновлено!\n\n"
                f"📦 Картки: {stats['products']}\n"
                f"📄 Чанки: {stats['chunks_found']}"
            )
    except Exception as e:
        await message.answer(f"❌ Критична помилка під час синхронізації: {e}")
        print(f"[bot] /sync_db error: {e}")


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
        for entity in message.entities:
            if entity.type == MessageEntityType.MENTION:
                mention_text = message.text[
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
async def on_message(message: Message, bot: Bot) -> None:
    """Обробник текстових повідомлень.

    Приватний чат: відповідає на будь-яке повідомлення.
    Група / супергрупа: відповідає тільки на @mention або Reply на бота.
    """
    # Ігноруємо повідомлення у групах, якщо бота не згадано
    if not _is_addressed(message):
        return

    # Очищуємо текст від @mention бота
    user_text = _strip_mention(message.text, _BOT_USERNAME) if _BOT_USERNAME else message.text
    if not user_text:
        await message.reply("🌿 Запитай мене що-небудь про ефірні олії doTERRA!")
        return

    stop_typing = asyncio.Event()

    # Запускаємо фоновий таск який тримає індикатор "пише..." весь час генерації
    typing_task = asyncio.create_task(
        _keep_typing(bot, message.chat.id, stop_typing)
    )

    try:
        # RAG-пайплайн: пошук → промпт → Gemini
        response = await generate_response(user_text)

        stop_typing.set()
        typing_task.cancel()

        # Захист від порожньої відповіді
        if not response or not response.strip():
            print(f"[on_message] Empty response for query: {user_text!r}")
            await message.reply("😔 Не вдалося сформувати відповідь. Спробуй перефразувати запит.")
            return

        # Відповідаємо з кнопками 👍/👎
        await _reply_with_feedback(message, response)

    except Exception as e:
        stop_typing.set()
        typing_task.cancel()

        await message.reply(
            "😔 Виникла помилка при обробці запиту. Спробуй ще раз."
        )
        print(f"[on_message] Error: {type(e).__name__}: {e}")


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

    # Записуємо голос у БД
    try:
        result = save_vote(
            message_id=msg_id,
            chat_id=chat_id,
            user_id=user_id,
            vote=vote,
            query_text=query_text[:500],  # обрізаємо довгі тексти
        )
    except Exception as e:
        print(f"[feedback] DB error: {e}")
        await callback.answer("⚠️ Не вдалося зберегти оцінку.", show_alert=True)
        return

    # Показуємо підтвердження
    if result == "unchanged":
        emoji = "👍" if vote == "like" else "👎"
        await callback.answer(f"{emoji} Ти вже поставив цю оцінку!", show_alert=False)
        return

    # Оновлюємо лічильники на кнопках
    try:
        counts = get_vote_counts(msg_id, chat_id)
        new_keyboard = _feedback_keyboard(
            msg_id, chat_id,
            likes=counts["likes"],
            dislikes=counts["dislikes"],
        )
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)
    except Exception as e:
        print(f"[feedback] keyboard update error: {e}")

    # Підтвердження користувачу
    if vote == "like":
        await callback.answer("👍 Дякую за позитивний відгук!", show_alert=False)
    else:
        await callback.answer("👎 Зрозуміло, постараємось покращити відповіді!", show_alert=False)


# Run the bot
async def main() -> None:
    global _BOT_USERNAME

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
        print(f"[bot] ⚠️ Could not init feedback table: {e}")

    # Налаштовуємо кнопку "Меню" (Web App)
    webapp_url = os.getenv("WEBAPP_URL", "https://arisnowie97.github.io/tg-bot-doterra-ai-agent/")
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Mini App", web_app=WebAppInfo(url=webapp_url))
        )
        print("[bot] ✅ Menu button configured.")
    except Exception as e:
        print(f"[bot] ⚠️ Could not configure menu button: {e}")

    # Налаштовуємо та запускаємо планувальник публікацій
    scheduler = setup_scheduler(bot)
    scheduler.start()
    print("[bot] 🚀 Bot started with channel post scheduler.")

    try:
        await dp.start_polling(bot)
    finally:
        # Зупиняємо планувальник при завершенні бота
        scheduler.shutdown(wait=False)
        print("[bot] 🛑 Scheduler stopped.")

if __name__ == "__main__":
    asyncio.run(main())
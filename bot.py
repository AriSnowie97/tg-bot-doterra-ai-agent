# Standard
import os
import asyncio
# Special
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.enums import ChatAction, ChatType, MessageEntityType
# Local
from src.agent import generate_response
from src.publisher import publish_channel_post
from src.scheduler import setup_scheduler


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
dp = Dispatcher()

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


@dp.message(Command("start"))
async def command_start_handler(message: Message) -> None:
    await message.answer(
        f"👋 Привіт, {message.from_user.first_name}!\n\n"
        "🌿 Ласкаво просимо до AI-консультанта doTERRA!\n\n"
        "Я допоможу тобі розібратись у гайдах та знайти потрібну інформацію "
        "про ефірні олії та продукти doTERRA.\n\n"
        "Просто напиши своє запитання — і я знайду відповідь 🔍"
    )


@dp.message(Command("ask"))
async def command_ask_handler(message: Message, command: CommandObject) -> None:
    """/ask <питання> — запит до бота в групі чи приватному чаті.

    Корисна альтернатива @mention у групах, де Privacy Mode обмежує видимість.
    Приклад: /ask Як використовувати лаванду для сну?
    """
    if not command.args:
        await message.reply(
            "🌿 Введіть питання після команди, наприклад:\n"
            "/ask Як використовувати лаванду для сну?"
        )
        return

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(
        _keep_typing(message.bot, message.chat.id, stop_typing)
    )

    try:
        response = await generate_response(command.args.strip())
        stop_typing.set()
        typing_task.cancel()
        await message.reply(response)
    except Exception as e:
        stop_typing.set()
        typing_task.cancel()
        await message.reply("😔 Виникла помилка при обробці запиту. Спробуй ще раз.")
        print(f"[command_ask] Error: {e}")


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
        await message.answer(f"✅ Пост опубліковано у канал {CHANNEL_ID}!")
    except Exception as e:
        await message.answer(f"❌ Помилка при публікації: {e}")
        print(f"[bot] /post error: {e}")


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

        # У групах відповідаємо через reply (щоб було видно на чиє питання)
        await message.reply(response)

    except Exception as e:
        stop_typing.set()
        typing_task.cancel()

        await message.reply(
            "😔 Виникла помилка при обробці запиту. Спробуй ще раз."
        )
        print(f"[on_message] Error: {e}")


# Run the bot
async def main() -> None:
    global _BOT_USERNAME

    bot = Bot(token=BOT_TOKEN)

    # Отримуємо username бота — потрібен для фільтрації @mention у групах
    me = await bot.get_me()
    _BOT_USERNAME = me.username or ""
    print(f"[bot] 🤖 Bot username: @{_BOT_USERNAME}")

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
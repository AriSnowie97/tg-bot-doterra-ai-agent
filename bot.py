# Standard
import os
import asyncio
# Special
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ChatAction
# Local


# Loading variables from a dotenv file
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Creating a dispatcher
dp = Dispatcher()


@dp.message(Command("start"))
async def command_start_handler(message: Message) -> None:
    await message.answer(
        f"👋 Привіт, {message.from_user.first_name}!\n\n"
        "🌿 Ласкаво просимо до AI-консультанта doTERRA!\n\n"
        "Я допоможу тобі розібратись у гайдах та знайти потрібну інформацію "
        "про ефірні олії та продукти doTERRA.\n\n"
        "Просто напиши своє запитання — і я знайду відповідь 🔍"
    )


@dp.message(F.text)
async def on_message(message: Message, bot: Bot) -> None:
    """Обробник текстових повідомлень із ефектом генерації відповіді."""

    # 1. Показуємо індикатор "пише..." у шапці чату
    await bot.send_chat_action(
        chat_id=message.chat.id,
        action=ChatAction.TYPING
    )

    # 2. Надсилаємо плейсхолдер поки генерується відповідь
    thinking_msg = await message.answer("🤔 Думаю над відповіддю...")

    try:
        # TODO: тут буде виклик LLM із RAG-контекстом
        # response = await generate_response(message.text)
        response = "⚙️ Генерацію відповіді ще не підключено. Скоро буде!"

        # 3. Редагуємо плейсхолдер на реальну відповідь
        await thinking_msg.edit_text(response)

    except Exception as e:
        await thinking_msg.edit_text(
            "😔 Виникла помилка при обробці запиту. Спробуй ще раз."
        )
        print(f"[on_message] Error: {e}")


# Run the bot
async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
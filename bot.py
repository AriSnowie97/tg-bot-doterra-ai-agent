# Standard
import os
import asyncio
# Special
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.enums import ChatAction
# Local
import handlers as h


# Loading variables from a dotenv file
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Creating a dispatcher
dp = Dispatcher()

dp.include_router(h.start_router)
dp.include_router(h.ask_router)
dp.include_router(h.mention_router)


# async def _keep_typing(bot: Bot, chat_id: int, stop_event: asyncio.Event) -> None:
#     """Підтримує індикатор 'пише...' у шапці чату поки не встановлено stop_event.

#     Telegram автоматично гасить typing через ~5 сек — тому шлємо його
#     кожні 4 сек у фоновому таску.
#     """
#     while not stop_event.is_set():
#         await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
#         await asyncio.sleep(4)


# @dp.message(F.text)
# async def on_message(message: Message, bot: Bot) -> None:
#     """Обробник текстових повідомлень із постійним ефектом 'пише...'."""

#     stop_typing = asyncio.Event()

#     # Запускаємо фоновий таск який тримає індикатор "пише..." весь час генерації
#     typing_task = asyncio.create_task(
#         _keep_typing(bot, message.chat.id, stop_typing)
#     )

#     try:
#         # RAG-пайплайн: пошук → промпт → Gemini
#         response = await generate_response(message.text)

#         # Зупиняємо typing і надсилаємо відповідь
#         stop_typing.set()
#         typing_task.cancel()

#         await message.answer(response)

#     except Exception as e:
#         stop_typing.set()
#         typing_task.cancel()

#         await message.answer(
#             "😔 Виникла помилка при обробці запиту. Спробуй ще раз."
#         )
#         print(f"[on_message] Error: {e}")


# Run the bot
async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
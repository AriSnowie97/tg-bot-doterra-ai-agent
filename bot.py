# Standard
import os
import asyncio
# Special
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
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
        "🌿 Ласкаво просимо до світу натуральних ефірних олій doTERRA!\n\n"
        "Тут ти знайдеш:\n"
        "✨ Інформацію про ефірні олії та їх властивості\n"
        "💆 Поради щодо застосування для здоров'я та краси\n"
        "🧴 Рецепти сумішей для дифузора\n"
        "📚 Наукові дослідження та факти\n\n"
        "Обери що тебе цікавить — і починаємо! 🌱"
    )


# Run the bot
async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
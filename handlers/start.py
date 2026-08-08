# Standard
# Special
from aiogram import F, Router
from aiogram.types import Message
from aiogram.filters import Command
# Local


start_router = Router()

@start_router.message(Command("start"))
async def command_start_handler(message: Message) -> None:
    await message.answer(
        f"👋 Привіт, {message.from_user.first_name}!\n\n"
        "🌿 Ласкаво просимо до AI-консультанта doTERRA!\n\n"
        "Я допоможу тобі розібратись у гайдах та знайти потрібну інформацію "
        "про ефірні олії та продукти doTERRA.\n\n"
        "Просто напиши своє запитання — і я знайду відповідь 🔍"
    )
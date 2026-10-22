# Standard
# Special
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
# Local


start_router = Router()

@start_router.message(Command("start"))
async def command_start_handler(message: Message) -> None:
    await message.answer(
        f"👋 Привіт, {message.from_user.first_name}!\n\n"
        "🌿 Я — Aroma Assistant, помічниця Наталії Котелянської.\n\n"
        "Я з радістю допоможу тобі познайомитися з ефірними оліями doTERRA "
        "та іншими чудовими продуктами, які є у Наталії 🌸\n\n"
        "Просто напиши своє запитання — і я з радістю підкажу 🔍"
    )
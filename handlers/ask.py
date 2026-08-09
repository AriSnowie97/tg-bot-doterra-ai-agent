# Standard
# Special
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command, CommandObject
# Local
from src.agent import generate_response


ask_router = Router()

@ask_router.message(Command("ask"))
async def command_ask_handler(message: Message, command: CommandObject) -> None:
    """Метод для обробки запитів з команди /ask до бота."""
    response = ""

    if not command.args:
        response = "Введіть питання після команди /ask ."

    else:
        response = await generate_response(command.args.strip())

    await message.answer(response)
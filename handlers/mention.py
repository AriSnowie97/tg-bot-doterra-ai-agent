# Standard
# Special
from aiogram import F, Router
from aiogram.types import Message
# Local
from src.agent import generate_response


mention_router = Router()

@mention_router.message(F.text)
async def bot_mention_handler(message: Message) -> None:
    response = ""

    if message.text:
        bot_user = await message.bot.get_me()

        if bot_user.username:
            mention = f"@{bot_user.username}"

            if mention.lower() in message.text.lower():
                query = message.text.replace(mention, "").strip()

                if not query:
                    response = "Введіть питання після згадування @бота."

                else:
                    response = await generate_response(query)

                await message.answer(response)
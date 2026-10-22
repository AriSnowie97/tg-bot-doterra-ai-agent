# Standard
import asyncio
from pathlib import Path
# Special
# Local
from src.content.translation import translate_file, translate_folders



async def main():
    # await translate_file(Path("src/content/test/a2z-chewable.md"))
    # await translate_folders(Path("src/content/test/"), ["adv", "prod", "symph"], True)
    await translate_folders(Path("src/content/"), ["advice", "products", "symphony_of_the_cells"])


if __name__ == "__main__":
    asyncio.run(main())
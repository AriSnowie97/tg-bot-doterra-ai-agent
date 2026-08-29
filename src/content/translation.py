# Standard
import asyncio
from pathlib import Path
# Special
# Local
from src.LLMProvider import GeminiFlashProvider as LLM


prompt = """
МЕТА
- Твоє завдання перекласти наданий текст із FILE на англійську мову.
- Формат тексту має бути збережений.
- Не пиши зайвого, а лише переклад.
- Видалення тексту заборонено.

FILE
{text}"""


async def translate_file(target_file: Path, is_retranslate: bool = False) -> None:
    """Створює, якщо не існує, файл із таким же іменем як target_file та записує в нього переклад.
    - Якщо is_retranslate = True, то переписує існуючий файл теж."""
    f = target_file

    if f.exists():
        f_trans = f.parent / "en" / f.name

        if not f_trans.exists() or is_retranslate:
            text = f.read_text(encoding="utf-8")
            response = await LLM().generate_content(prompt.format(text=text))
            text_trans = (response.text or "").strip()

            if text_trans:
                f_trans.parent.mkdir(parents=True, exist_ok=True)
                f_trans.write_text(text_trans, encoding="utf-8")
                print(f"Перекладено: {f_trans.name}")


async def translate_folder(folder: Path, is_retranslate: bool = False) -> None:
    """Перекладає усі .md файли у target_folder.
    - Якщо is_retranslate = True, то переписує існуючі файли теж."""
    if folder.exists() and folder.is_dir():
        await asyncio.gather(
            *(translate_file(f, is_retranslate) for f in folder.glob("*.md"))
        )


async def translate_folders(path: Path, folder_names: list[str], is_retranslate: bool = False) -> None:
    """Перекладає усі .md файли у target_folders.
    - path - шлях до батьківської папки де розміщені всі folder_names.
    - folder_names - список назв папок.
    - Якщо is_retranslate = True, то переписує існуючі файли теж."""
    for folder in (path / folder_name for folder_name in folder_names):
        if folder.exists() and folder.is_dir():
            await translate_folder(folder, is_retranslate)
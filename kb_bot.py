"""
doTERRA KB Uploader Bot — Адмін-бот для завантаження MD-файлів у базу знань.

Команди:
    /start   — привітання, список команд
    /upload  — FSM: отримати MD-файл → вказати slug → завантажити в KB
    /list    — список MD-документів у src/content/docs/
    /status  — кількість чанків у БД

Змінні оточення (.env):
    KB_BOT_TOKEN    — токен цього адмін-бота
    KB_ADMIN_IDS    — comma-separated user_id тих, хто може використовувати бота
    DATABASE_URL    — URL PostgreSQL БД
    DATABASE_PUBLIC_URL — публічний URL (для локального запуску)
    GEMINI_API_KEY  — ключ Gemini для генерації embeddings

Запуск:
    python kb_bot.py
"""

# Standard
import os
import asyncio
import tempfile
import traceback
from pathlib import Path
# Special
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, Document
# Local
from handlers.states import UploadKBStates
from src.kb_uploader.uploader import upload_md_to_kb
from src.storage.storage import _conn_create
from src.content.sync_content import run_sync

load_dotenv()

KB_BOT_TOKEN: str = os.getenv("KB_BOT_TOKEN", "")
KB_ADMIN_IDS: list[int] = [
    int(uid)
    for uid in os.getenv("KB_ADMIN_IDS", "").split(",")
    if uid.strip().isdigit()
]

dp = Dispatcher(storage=MemoryStorage())


# ---------------------------------------------------------------------------
# Перевірка доступу
# ---------------------------------------------------------------------------

def _is_admin(message: Message) -> bool:
    """Повертає True якщо користувач є адміном або KB_ADMIN_IDS не задано."""
    if not KB_ADMIN_IDS:
        return True  # режим розробки — дозволяємо всім
    return message.from_user.id in KB_ADMIN_IDS


def _admin_only(func):
    """Декоратор: відхиляє запити не-адмінів."""
    async def wrapper(message: Message, *args, **kwargs):
        if not _is_admin(message):
            await message.answer("⛔ У тебе немає доступу до цього бота.")
            return
        return await func(message, *args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

@dp.message(Command("start"))
@_admin_only
async def cmd_start(message: Message) -> None:
    await message.answer(
        "🌿 Привіт! Я adмін-бот для управління базою знань doTERRA.\n\n"
        "Доступні команди:\n"
        "📤 /upload  — завантажити MD-файл у базу знань\n"
        "🔄 /resync  — переіндексація всієї бази знань\n"
        "📋 /list    — список документів у docs/\n"
        "📊 /status  — кількість чанків у БД\n"
    )


# ---------------------------------------------------------------------------
# /list
# ---------------------------------------------------------------------------

@dp.message(Command("list"))
@_admin_only
async def cmd_list(message: Message) -> None:
    """Список усіх MD-файлів у src/content/docs/."""
    content_dir = Path(__file__).parent / "src" / "content"
    if not content_dir.exists():
        await message.answer("❌ Директорія content/ не знайдена.")
        return

    files = []
    for d in ["docs", "products", "advice", "symphony_of_the_cells", "kits"]:
        folder = content_dir / d
        if folder.exists():
            files.extend(list(folder.glob("*.md")))
            
    files = sorted(files, key=lambda f: f.name)
    if not files:
        await message.answer("📭 Документи відсутні.")
        return

    lines = [f"📄 {f.name}" for f in files]
    await message.answer(
        f"📋 Документи у базі ({len(files)} шт.):\n\n" + "\n".join(lines)
    )


# ---------------------------------------------------------------------------
# /status
# ---------------------------------------------------------------------------

@dp.message(Command("status"))
@_admin_only
async def cmd_status(message: Message) -> None:
    """Показує кількість чанків у БД."""
    try:
        conn = _conn_create()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM knowledge_chunks;")
            total = cur.fetchone()[0]
            cur.execute(
                "SELECT product_slug, COUNT(*) FROM knowledge_chunks "
                "GROUP BY product_slug ORDER BY COUNT(*) DESC LIMIT 10;"
            )
            rows = cur.fetchall()
        conn.close()

        lines = [f"  • {slug}: {cnt}" for slug, cnt in rows]
        await message.answer(
            f"📊 Загалом чанків у БД: {total}\n\n"
            "Топ продуктів:\n" + "\n".join(lines)
        )
    except Exception as e:
        await message.answer(f"❌ Помилка підключення до БД: {e}")


# ---------------------------------------------------------------------------
# /resync — повна переіндексація бази знань
# ---------------------------------------------------------------------------

@dp.message(Command("resync"))
@_admin_only
async def cmd_resync(message: Message) -> None:
    """Запускає повну переіндексацію: JSON картки + MD парсинг + векторизація."""
    await message.answer(
        "🔄 <b>Починаю переіндексацію бази знань...</b>\n\n"
        "📦 Крок 1/3 — JSON картки продуктів\n"
        "📄 Крок 2/3 — Парсинг MD-документів\n"
        "🔢 Крок 3/3 — Генерація embeddings\n\n"
        "⏳ Це може зайняти кілька хвилин. Прогрес нижче:",
        parse_mode="HTML"
    )

    loop = asyncio.get_running_loop()

    def tg_progress(msg: str) -> None:
        """Надсилає рядок прогресу в Telegram (виклик з sync-потоку)."""
        try:
            asyncio.run_coroutine_threadsafe(
                message.answer(msg, parse_mode="HTML"), loop
            )
        except Exception as cb_err:
            print(f"[kb_bot] resync progress error: {cb_err}")

    try:
        stats = await asyncio.to_thread(run_sync, tg_progress)
    except Exception as e:
        print(f"[kb_bot] resync error:\n{traceback.format_exc()}")
        await message.answer(
            f"❌ <b>Критична помилка переіндексації:</b>\n<code>{e}</code>",
            parse_mode="HTML"
        )
        return

    # ── Фінальний звіт ──────────────────────────────────────────────────────
    error_count = len(stats.get("errors", []))
    status_icon = "✅" if error_count == 0 else "⚠️"
    error_lines = ""
    if error_count:
        error_lines = "\n\n<b>Помилки:</b>\n" + "\n".join(
            f"  • <code>{e}</code>" for e in stats["errors"]
        )

    await message.answer(
        f"{status_icon} <b>Переіндексація завершена!</b>\n\n"
        f"📦 Оброблено карток: <b>{stats.get('products', 0)}</b>\n"
        f"📄 Чанків знайдено: <b>{stats.get('chunks_found', 0)}</b>\n"
        f"❌ Помилок: <b>{error_count}</b>"
        f"{error_lines}",
        parse_mode="HTML"
    )


# ---------------------------------------------------------------------------
# /upload — FSM: MD-файл → slug → завантаження
# ---------------------------------------------------------------------------

@dp.message(Command("upload"))
@_admin_only
async def cmd_upload(message: Message, state: FSMContext) -> None:
    """Починає FSM-сценарій завантаження MD-файлу."""
    await state.set_state(UploadKBStates.waiting_for_file)
    await message.answer(
        "📤 Надішли MD-файл документа.\n\n"
        "⚠️ Файл повинен мати розширення .md\n"
        "Для скасування — /cancel"
    )


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Скасовує поточний FSM-сценарій."""
    current = await state.get_state()
    if current is None:
        await message.answer("❌ Немає активного процесу для скасування.")
        return
    await state.clear()
    await message.answer("✅ Операцію скасовано.")


@dp.message(UploadKBStates.waiting_for_file, F.document)
async def receive_file(message: Message, state: FSMContext, bot: Bot) -> None:
    """Отримує MD-файл у стані waiting_for_file і запитує product_slug."""
    await _process_received_md(message, state)


@dp.message(F.document)
async def receive_file_any(message: Message, state: FSMContext, bot: Bot) -> None:
    """Ловить MD-файл надісланий у будь-який момент (навіть без /upload).

    Перевіряє доступ адміна та одразу починає FSM-сценарій завантаження.
    """
    if not _is_admin(message):
        return  # мовчки ігноруємо — не адмін
    await _process_received_md(message, state)


async def _process_received_md(message: Message, state: FSMContext) -> None:
    """Спільна логіка: перевірка файлу та перехід до кроку вибору slug."""
    doc: Document = message.document

    if not doc.file_name.endswith(".md"):
        await message.answer(
            "⚠️ Підтримуються лише файли з розширенням .md\n"
            "Надішли правильний файл або /cancel для скасування."
        )
        return

    # Зберігаємо file_id та ім'я файлу в стані FSM
    await state.update_data(file_id=doc.file_id, file_name=doc.file_name)

    # Пропонуємо slug на основі назви файлу (без .md)
    suggested_slug = doc.file_name.removesuffix(".md").lower().replace("_", "-").replace(" ", "-")
    await state.set_state(UploadKBStates.waiting_for_slug)
    await message.answer(
        f"✅ Файл отримано: <b>{doc.file_name}</b>\n\n"
        f"📝 Введи <b>product_slug</b> для цього документа.\n"
        f"Пропозиція: <code>{suggested_slug}</code>\n\n"
        "Slug — унікальний ідентифікатор продукту "
        "(наприклад: frankincense, lavender, deep-blue).\n\n"
        "Надішли slug текстом або натисни /cancel для скасування:",
        parse_mode="HTML"
    )


@dp.message(UploadKBStates.waiting_for_file)
async def receive_file_wrong_type(message: Message) -> None:
    """Нагадує якщо надіслано не файл."""
    await message.answer(
        "⚠️ Очікую MD-файл. Надішли документ (.md).\n"
        "Або /cancel для скасування."
    )


@dp.message(UploadKBStates.waiting_for_slug, F.text)
async def receive_slug(message: Message, state: FSMContext, bot: Bot) -> None:
    """Отримує slug, завантажує файл з Telegram і запускає upsert з прогресом."""
    slug = message.text.strip().lower().replace(" ", "-")

    # Базова валідація slug
    if not slug.replace("-", "").replace("_", "").isalnum() or len(slug) < 2:
        await message.answer(
            "⚠️ Невірний slug. Використовуй лише літери, цифри та дефіси.\n"
            "Наприклад: frankincense, deep-blue\n\nСпробуй ще раз:"
        )
        return

    data = await state.get_data()
    file_id: str = data["file_id"]
    file_name: str = data["file_name"]

    await state.clear()

    # ── Крок 1: завантажуємо файл з Telegram ────────────────────────────────
    await message.answer(
        f"🚀 Починаю обробку файлу <b>{file_name}</b>\n"
        f"Slug: <code>{slug}</code>\n\n"
        "📥 Завантажую файл з Telegram...",
        parse_mode="HTML"
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / file_name

        tg_file = await bot.get_file(file_id)
        await bot.download_file(tg_file.file_path, destination=str(tmp_path))

        await message.answer("✅ Файл отримано. Парсинг та завантаження в БД...")

        # ── Крок 2: запускаємо upsert у фоновому потоці з callback-прогресом ──
        # get_running_loop() — правильний спосіб отримати loop із async-контексту
        loop = asyncio.get_running_loop()

        def tg_progress(msg: str) -> None:
            """Відправляє прогрес-повідомлення у Telegram із синхронного потоку."""
            try:
                asyncio.run_coroutine_threadsafe(
                    message.answer(msg, parse_mode="HTML"), loop
                )
            except Exception as cb_err:
                print(f"[kb_bot] tg_progress error: {cb_err}")

        try:
            stats = await asyncio.to_thread(
                upload_md_to_kb, str(tmp_path), slug, tg_progress
            )
        except Exception as e:
            print(f"[kb_bot] upload error:\n{traceback.format_exc()}")
            await message.answer(f"❌ Помилка при завантаженні:\n<code>{e}</code>", parse_mode="HTML")
            return

    # ── Крок 3: фінальний звіт ───────────────────────────────────────────────
    status_icon = "✅" if stats["errors"] == 0 else "⚠️"
    await message.answer(
        f"{status_icon} <b>Готово!</b> Результат завантаження <b>{file_name}</b>\n"
        f"Slug: <code>{slug}</code>\n\n"
        f"📦 Всього чанків у файлі: <b>{stats['total']}</b>\n"
        f"✅ Додано нових: <b>{stats['inserted']}</b>\n"
        f"⏭ Пропущено дублікатів: <b>{stats['skipped_duplicates']}</b>\n"
        f"❌ Помилок: <b>{stats['errors']}</b>",
        parse_mode="HTML"
    )

    # Якщо є нові чанки — пропонуємо скопіювати файл у docs/
    if stats["inserted"] > 0:
        content_dir = Path(__file__).parent / "src" / "content"
        found = False
        if content_dir.exists():
            for d in ["docs", "products", "advice", "symphony_of_the_cells", "kits"]:
                if (content_dir / d / file_name).exists():
                    found = True
                    break
                    
        if not found:
            await message.answer(
                f"💡 Файл ще не в директоріях контенту. Щоб веб-перегляд "
                f"<code>/docs/{slug}</code> працював — збережи його до "
                f"<code>src/content/products/{file_name}</code>",
                parse_mode="HTML"
            )


# ---------------------------------------------------------------------------
# Запуск
# ---------------------------------------------------------------------------

async def main() -> None:
    if not KB_BOT_TOKEN:
        print("[kb_bot] ❌ KB_BOT_TOKEN не задано у .env!")
        return

    bot = Bot(token=KB_BOT_TOKEN)
    me = await bot.get_me()
    print(f"[kb_bot] 🤖 KB Bot started: @{me.username}")

    try:
        await dp.start_polling(bot)
    finally:
        print("[kb_bot] 🛑 Stopped.")


if __name__ == "__main__":
    asyncio.run(main())

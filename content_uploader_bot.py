
"""
doTERRA Content Uploader Bot
=============================
Адмін-бот для завантаження нових MD-файлів із продуктами doTERRA.

Можливості:
  - Надіслати один або декілька .md файлів → бот автоматично:
      1. Форматує їх під стандарт (той же що і в основних docs)
      2. Завантажує офіційні фото з doterra.com (og:image)
      3. Парсить у chunks (через parser.py)
      4. Зберігає в БД та оновлює all_chunks.json
      5. Зберігає в src/content/docs/

Налаштування (.env або Railway Variables):
  CONTENT_BOT_TOKEN   — токен цього бота
  CONTENT_BOT_ADMINS  — Telegram user_id адмінів через кому (наприклад: 388615032)
  DATABASE_URL        — PostgreSQL URL (береться з Railway автоматично)
"""

import asyncio
import io
import json
import logging
import os
import re
import sys
import requests
from pathlib import Path

import ftfy
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, Document
from aiogram.filters import CommandStart, Command
from dotenv import load_dotenv

# ──────────────────────────────────────────────────
# Шляхи
# ──────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DOCS_DIR = BASE_DIR / "src" / "content" / "docs"
ALL_CHUNKS_PATH = BASE_DIR / "all_chunks.json"

# ──────────────────────────────────────────────────
# Env
# ──────────────────────────────────────────────────
load_dotenv()

BOT_TOKEN: str = os.getenv("CONTENT_BOT_TOKEN", "")
ADMIN_IDS: set[int] = {
    int(x.strip())
    for x in os.getenv("CONTENT_BOT_ADMINS", "").split(",")
    if x.strip().isdigit()
}
DATABASE_URL: str = os.getenv("DATABASE_URL", "")

if not BOT_TOKEN:
    sys.exit("❌ CONTENT_BOT_TOKEN не задано у .env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────
# Форматування MD
# ──────────────────────────────────────────────────

def format_md(text: str) -> str:
    """Приводить MD-файл до стандарту проекту."""
    text = ftfy.fix_text(text)
    text = text.replace("ЕЌ", "ō").replace("еќ", "ō")

    tag_pattern = re.compile(
        r'^(\s*(?:#[A-Za-zА-Яа-яІіЇїЄєҐґ0-9_]+\s*)+)$',
        re.MULTILINE,
    )
    all_tags: list[str] = []

    def tag_repl(match: re.Match) -> str:
        for t in match.group(1).split():
            if t not in all_tags:
                all_tags.append(t)
        return ""

    text = tag_pattern.sub(tag_repl, text)

    text = re.sub(
        r'^\*?\*?(Категорія|Тип|Посилання):?\*?\*?\s*(.*?)$',
        r'**\1:** \2',
        text,
        flags=re.MULTILINE,
    )

    text = re.sub(r'^###\s+', '## ', text, flags=re.MULTILINE)
    text = re.sub(r'^####\s+', '## ', text, flags=re.MULTILINE)

    first_h2 = re.search(r'^##\s', text, re.MULTILINE)
    if first_h2:
        before = text[: first_h2.start()]
        if not re.search(r'^---\s*$', before, re.MULTILINE):
            text = before.rstrip() + "\n\n---\n\n" + text[first_h2.start():]

    zast_pattern = re.compile(
        r'^## Застереження\s*\n+([\s\S]*?)(?=\n## |\Z)', re.MULTILINE
    )

    def zast_repl(m: re.Match) -> str:
        content = m.group(1).strip()
        if not content.startswith("> ⚠️"):
            content = "> ⚠️ " + content.replace("\n", "\n> ")
        return content + "\n\n"

    text = zast_pattern.sub(zast_repl, text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    if all_tags:
        text = text.rstrip() + "\n\n" + " ".join(all_tags) + "\n"

    return text


def fetch_official_image(url: str) -> str | None:
    """Витягує og:image з офіційної сторінки doTERRA."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        )
    }
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code == 200:
            match = re.search(
                r'<meta property="og:image" content="([^"]+)"',
                response.text,
            )
            if match:
                return match.group(1)
    except Exception as e:
        log.warning("fetch_official_image error: %s", e)
    return None


def update_image(text: str) -> str:
    """Якщо є посилання → завантажує офіційне фото та підставляє."""
    link_match = re.search(
        r'\*\*Посилання:\*\*\s*(https://www\.doterra\.com[^\s\n]+)',
        text,
    )
    if not link_match:
        return text

    url = link_match.group(1).strip()
    img_url = fetch_official_image(url)
    if not img_url:
        return text

    new_img_md = f"![doTERRA Product]({img_url})"
    if re.search(r'^!\[.*?\]\(.*?\)', text, re.MULTILINE):
        text = re.sub(r'^!\[.*?\]\(.*?\)', new_img_md, text, count=1, flags=re.MULTILINE)
    else:
        text = new_img_md + "\n\n" + text

    return text


# ──────────────────────────────────────────────────
# Чанкування
# ──────────────────────────────────────────────────

def parse_to_chunks(md_path: Path) -> list[dict]:
    """Парсить MD через наявний parser.py і повертає список чанків."""
    sys.path.insert(0, str(BASE_DIR / "src" / "content"))
    from parser import DoterraMarkdownParser

    parser = DoterraMarkdownParser()
    chunks = parser.parse_file(md_path)
    return [c.to_dict() for c in chunks]


def save_chunks_to_db(chunks_dicts: list[dict]) -> None:
    """Зберігає чанки у PostgreSQL."""
    if not DATABASE_URL:
        log.warning("DATABASE_URL не задано, пропускаємо збереження в БД")
        return

    try:
        import psycopg2

        db_url = DATABASE_URL
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id            SERIAL PRIMARY KEY,
                chunk_id      VARCHAR(16)  UNIQUE NOT NULL,
                product_slug  VARCHAR(100) NOT NULL,
                section_key   VARCHAR(100) NOT NULL,
                section_title TEXT,
                content       TEXT         NOT NULL,
                char_count    INTEGER,
                tokens_approx INTEGER,
                chunk_order   INTEGER,
                chunk_metadata TEXT,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_product ON chunks(product_slug);
            CREATE INDEX IF NOT EXISTS idx_chunks_section ON chunks(section_key);
        """)

        upsert_sql = """
            INSERT INTO chunks
                (chunk_id, product_slug, section_key, section_title, content,
                 char_count, tokens_approx, chunk_order, chunk_metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (chunk_id) DO UPDATE SET
                content       = EXCLUDED.content,
                char_count    = EXCLUDED.char_count,
                tokens_approx = EXCLUDED.tokens_approx,
                chunk_order   = EXCLUDED.chunk_order;
        """

        for c in chunks_dicts:
            cur.execute(upsert_sql, (
                c["chunk_id"], c["product_slug"], c["section_key"],
                c["section_title"], c["content"],
                c["char_count"], c["tokens_approx"], c["order"],
                json.dumps(c.get("metadata", {}), ensure_ascii=False),
            ))

        conn.commit()
        cur.close()
        conn.close()
        log.info("Saved %d chunks to DB", len(chunks_dicts))
    except Exception as e:
        log.error("save_chunks_to_db error: %s", e)


def update_all_chunks_json(new_chunks: list[dict]) -> None:
    """Додає нові чанки до all_chunks.json (або оновлює існуючі)."""
    existing: list[dict] = []
    if ALL_CHUNKS_PATH.exists():
        try:
            existing = json.loads(ALL_CHUNKS_PATH.read_text(encoding="utf-8"))
        except Exception:
            existing = []

    slugs = {c["product_slug"] for c in new_chunks}
    existing = [c for c in existing if c.get("product_slug") not in slugs]
    existing.extend(new_chunks)

    ALL_CHUNKS_PATH.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("all_chunks.json updated: %d total chunks", len(existing))


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-")


# ──────────────────────────────────────────────────
# Aiogram Handlers
# ──────────────────────────────────────────────────

dp = Dispatcher()


def is_admin(user_id: int) -> bool:
    return not ADMIN_IDS or user_id in ADMIN_IDS


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "👋 <b>Привіт! Я Content Uploader Bot.</b>\n\n"
        "Надішли мені один або декілька <code>.md</code> файлів із новими продуктами doTERRA.\n\n"
        "Я автоматично:\n"
        "✅ Відформатую файл під стандарт проекту\n"
        "✅ Підставлю офіційне фото з doterra.com\n"
        "✅ Розіб'ю на чанки та збережу в БД\n"
        "✅ Оновлю <code>all_chunks.json</code>\n"
        "✅ Збережу файл у <code>src/content/docs/</code>\n\n"
        "📌 <b>Команди:</b>\n"
        "/status — Статус бота\n"
        "/list — Список завантажених продуктів",
        parse_mode="HTML",
    )


@dp.message(Command("status"))
async def cmd_status(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return

    # rglob — рахуємо всі MD рекурсивно
    docs_count = len(list(DOCS_DIR.rglob("*.md")))
    chunks_count = 0
    if ALL_CHUNKS_PATH.exists():
        try:
            data = json.loads(ALL_CHUNKS_PATH.read_text(encoding="utf-8"))
            chunks_count = len(data)
        except Exception:
            pass

    db_status = "✅ PostgreSQL" if DATABASE_URL else "⚠️ не налаштовано"
    await message.answer(
        f"📊 <b>Статус:</b>\n"
        f"📁 MD-файлів: <code>{docs_count}</code>\n"
        f"🧩 Чанків у all_chunks.json: <code>{chunks_count}</code>\n"
        f"🗄 БД: {db_status}",
        parse_mode="HTML",
    )


@dp.message(Command("list"))
async def cmd_list(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return

    # rglob — всі MD рекурсивно
    files = sorted(DOCS_DIR.rglob("*.md"))
    if not files:
        await message.answer("📂 Файлів немає.")
        return

    lines = [f"• <code>{f.stem}</code>" for f in files]
    text = f"📦 <b>Продукти в базі ({len(files)}):</b>\n\n" + "\n".join(lines)

    # Telegram limit: 4096 chars per message
    if len(text) > 4000:
        text = text[:4000] + "\n…"

    await message.answer(text, parse_mode="HTML")


@dp.message(F.document)
async def handle_document(message: Message, bot: Bot) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас немає доступу.")
        return

    doc: Document = message.document
    if not doc.file_name.endswith(".md"):
        await message.answer("⚠️ Надішліть файл з розширенням `.md`")
        return

    await message.answer(
        f"📥 Отримано: <code>{doc.file_name}</code>\nОбробка…",
        parse_mode="HTML",
    )

    # 1. Скачуємо файл
    file_bytes = io.BytesIO()
    tg_file = await bot.get_file(doc.file_id)
    await bot.download_file(tg_file.file_path, destination=file_bytes)
    file_bytes.seek(0)

    try:
        raw_text = file_bytes.read().decode("utf-8")
    except UnicodeDecodeError:
        file_bytes.seek(0)
        raw_text = file_bytes.read().decode("cp1251", errors="replace")

    # 2. Форматування
    await message.answer("🔧 Форматую файл…")
    formatted_text = format_md(raw_text)

    # 3. Офіційне фото
    await message.answer("🖼 Завантажую офіційне фото з doterra.com…")
    formatted_text = update_image(formatted_text)

    # 4. Зберігаємо MD
    stem = Path(doc.file_name).stem
    slug = slugify(stem)
    out_md = DOCS_DIR / f"{slug}.md"
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out_md.write_text(formatted_text, encoding="utf-8")
    log.info("Saved MD: %s", out_md)

    # 5. Парсинг → чанки
    await message.answer("🧩 Парсю на чанки…")
    try:
        chunks = parse_to_chunks(out_md)
    except Exception as e:
        await message.answer(f"❌ Помилка парсингу: <code>{e}</code>", parse_mode="HTML")
        return

    # 6. Зберігаємо у БД
    save_chunks_to_db(chunks)

    # 7. Оновлюємо all_chunks.json
    update_all_chunks_json(chunks)

    # 8. Звіт
    db_saved = "✅" if DATABASE_URL else "⚠️ пропущено"
    await message.answer(
        f"✅ <b>Готово!</b>\n\n"
        f"📄 Файл: <code>{out_md.name}</code>\n"
        f"🧩 Чанків створено: <code>{len(chunks)}</code>\n"
        f"🗄 Збережено в БД: {db_saved}\n"
        f"📦 all_chunks.json оновлено ✅",
        parse_mode="HTML",
    )


# ──────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────

async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    log.info("Content Uploader Bot started. Admins: %s", ADMIN_IDS)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

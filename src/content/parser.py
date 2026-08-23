"""
doTERRA Bot — Парсер MD-файлів контенту
========================================
Розбиває MD-файли за структурними маркерами (----, ##-заголовки)
на смислові чанки зі збереженням контексту (product + section).

Підтримувані формати маркерів:
  - Горизонтальні лінії: ---, ----, ------...
  - Заголовки: ## Назва розділу
  - Мета-заголовок: # Назва продукту

Вихід (ContentChunk):
  chunk_id       — SHA-256 хеш (унікальний ідентифікатор чанку)
  product_slug   — ідентифікатор продукту ('frankincense')
  section_key    — нормалізований ключ розділу ('physical_effects')
  section_title  — оригінальний заголовок ('Вплив на фізичне тіло')
  content        — очищений текст чанку
  char_count     — кількість символів
  tokens_approx  — приблизна кількість токенів (char / 4)
  metadata       — dict з додатковим контекстом

Використання:
  python content/parser.py content/docs/frankincense.md
  python content/parser.py content/docs/ --output chunks.json
  python content/parser.py content/docs/ --to-db
"""

import re
import json
import hashlib
import sys
import argparse
import os
import glob
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterator

# Виправлення кодування консолі Windows (cp1251 → utf-8)
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Налаштування ─────────────────────────────────────────────────────────────

# Маппінг: підрядок заголовку (нижній регістр) → section_key
SECTION_KEY_MAP: dict[str, str] = {
    "короткий опис":             "short_description",
    "вплив на фізичне":         "physical_effects",
    "вплив на емоційн":         "emotional_effects",
    "способи застосування":     "usage",
    "показання":                "indications",
    "походження та склад":      "origin",
    "краса та догляд":          "beauty_skincare",
    "цікаві факти":             "interesting_facts",
    "суміші для дифузора":      "diffuser_blends",
    "дослідження":              "research",
    "додаткова інформація":     "additional_info",
    "запобіжні заходи":         "precautions",
    "рекомендації":             "expert_quotes",
    "взаємодія з препаратами":  "drug_interactions",
    "дозування":                "dosage_guide",
    "протипоказання":           "contraindications",
}

# Символи-маркери списків (для підрахунку елементів)
LIST_EMOJIS = {"👑", "▫️", "🔹", "💦", "•", "-"}

# Максимальний розмір чанку в символах (якщо потрібно дробити великі секції)
MAX_CHUNK_CHARS = 2000

# Мінімальний розмір чанку (відкидаємо занадто короткі)
MIN_CHUNK_CHARS = 20


# ── Структура чанку ───────────────────────────────────────────────────────────

@dataclass
class ContentChunk:
    chunk_id:      str
    product_slug:  str
    section_key:   str
    section_title: str
    content:       str
    char_count:    int
    tokens_approx: int
    order:         int          # порядковий номер чанку в документі
    metadata:      dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def build(
        cls,
        product_slug: str,
        section_key: str,
        section_title: str,
        content: str,
        order: int,
        metadata: dict | None = None,
    ) -> "ContentChunk":
        content = content.strip()
        # Прибираємо внутрішній маркер заголовку H1
        display_title = section_title.replace("__header__", "").strip() or section_title

        chunk_id = hashlib.sha256(
            f"{product_slug}::{section_key}::{content}".encode()
        ).hexdigest()[:16]

        return cls(
            chunk_id=chunk_id,
            product_slug=product_slug,
            section_key=section_key,
            section_title=display_title,
            content=content,
            char_count=len(content),
            tokens_approx=max(1, len(content) // 4),
            order=order,
            metadata=metadata or {},
        )


# ── Утиліти ───────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Перетворює назву файлу/продукту у slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = text.strip("-")
    return text


def detect_section_key(title: str) -> str:
    """Визначає section_key за заголовком розділу."""
    # Внутрішній маркер H1-шапки
    if title.startswith("__header__"):
        return "product_header"

    title_lower = title.lower().strip()
    for pattern, key in SECTION_KEY_MAP.items():
        if pattern in title_lower:
            return key
    # Fallback: slugify заголовку
    return slugify(title) or "unknown"


def clean_line(line: str) -> str:
    """Видаляє зайві пробіли та Markdown-форматування але зберігає зміст."""
    # Прибираємо **жирний** та _курсив_, але залишаємо текст
    line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
    line = re.sub(r"_(.+?)_", r"\1", line)
    # Прибираємо inline-code `...`
    line = re.sub(r"`(.+?)`", r"\1", line)
    return line.strip()


def is_separator(line: str) -> bool:
    """Перевіряє чи є рядок горизонтальною лінією-розділювачем."""
    stripped = line.strip()
    # --- або ---- або ------- (мінімум 3 дефіси)
    return bool(re.match(r"^-{3,}$", stripped)) or stripped == "---"


def is_heading(line: str) -> tuple[int, str]:
    """
    Повертає (рівень, текст) для заголовку Markdown.
    Якщо не заголовок — (0, '').
    """
    match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
    if match:
        return len(match.group(1)), match.group(2).strip()
    return 0, ""


def is_empty(line: str) -> bool:
    return not line.strip()


def count_list_items(text: str) -> int:
    """Підраховує кількість рядків-елементів списку (з emoji або '-')."""
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        for emoji in LIST_EMOJIS:
            if stripped.startswith(emoji):
                count += 1
                break
    return count


def split_large_chunk(
    product_slug: str,
    section_key: str,
    section_title: str,
    content: str,
    base_order: int,
    max_chars: int = MAX_CHUNK_CHARS,
) -> list[ContentChunk]:
    """
    Якщо чанк занадто великий — розбиває його на підчанки
    по межах абзаців або рядків-елементів списку.
    Зберігає overlap: останній абзац попереднього підчанку
    додається на початок наступного (збереження контексту).
    """
    if len(content) <= max_chars:
        chunk = ContentChunk.build(
            product_slug, section_key, section_title, content, base_order,
            metadata={"split": False}
        )
        return [chunk]

    # Розбиваємо по абзацах (порожній рядок)
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", content) if p.strip()]
    chunks: list[ContentChunk] = []
    current_parts: list[str] = []
    current_len = 0
    sub_index = 0
    overlap_text = ""

    for para in paragraphs:
        if current_len + len(para) > max_chars and current_parts:
            # Зберегти поточний чанк
            chunk_content = overlap_text + "\n\n".join(current_parts) if overlap_text else "\n\n".join(current_parts)
            chunks.append(ContentChunk.build(
                product_slug, section_key, section_title,
                chunk_content,
                base_order + sub_index,
                metadata={"split": True, "sub_index": sub_index, "section_title": section_title}
            ))
            # Overlap = останній абзац
            overlap_text = current_parts[-1] + "\n\n" if current_parts else ""
            sub_index += 1
            current_parts = [para]
            current_len = len(para)
        else:
            current_parts.append(para)
            current_len += len(para)

    # Залишок
    if current_parts:
        chunk_content = overlap_text + "\n\n".join(current_parts) if overlap_text else "\n\n".join(current_parts)
        chunks.append(ContentChunk.build(
            product_slug, section_key, section_title,
            chunk_content,
            base_order + sub_index,
            metadata={"split": True, "sub_index": sub_index, "section_title": section_title}
        ))

    return chunks


# ── Основний парсер ───────────────────────────────────────────────────────────

class DoterraMarkdownParser:
    """
    Парсер MD-файлів у форматі doTERRA-шаблону.

    Підтримує два режими розбиття:
      'heading' — розбиття за ## заголовками (рекомендовано)
      'separator' — розбиття за горизонтальними лініями (---)

    Обидва режими можна поєднувати (auto-detect).
    """

    def __init__(
        self,
        max_chunk_chars: int = MAX_CHUNK_CHARS,
        min_chunk_chars: int = MIN_CHUNK_CHARS,
        keep_emojis: bool = True,
    ):
        self.max_chunk_chars = max_chunk_chars
        self.min_chunk_chars = min_chunk_chars
        self.keep_emojis = keep_emojis

    # ── Публічний API ─────────────────────────────────────────────────────────

    def parse_file(self, filepath: str | Path) -> list[ContentChunk]:
        """Розпарсити один MD-файл → список чанків."""
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Файл не знайдено: {filepath}")

        product_slug = slugify(filepath.stem)
        text = filepath.read_text(encoding="utf-8")
        return self.parse_text(text, product_slug=product_slug, source_file=str(filepath))

    def parse_directory(self, dirpath: str | Path) -> list[ContentChunk]:
        """Розпарсити всі *.md файли з директорії → список чанків."""
        dirpath = Path(dirpath)
        all_chunks: list[ContentChunk] = []
        md_files = sorted(dirpath.glob("*.md"))

        if not md_files:
            print(f"[!] No MD files found in: {dirpath}", file=sys.stderr)
            return []

        for md_file in md_files:
            print(f"  [file] Parsing: {md_file.name}")
            chunks = self.parse_file(md_file)
            all_chunks.extend(chunks)
            print(f"     -> {len(chunks)} chunks")

        return all_chunks

    def parse_text(
        self,
        text: str,
        product_slug: str,
        source_file: str = "",
    ) -> list[ContentChunk]:
        """
        Розпарсити текст у форматі doTERRA MD-шаблону.
        Автоматично обирає режим: heading або separator.
        """
        lines = text.splitlines()
        has_headings = any(is_heading(l)[0] == 2 for l in lines)

        if has_headings:
            raw_sections = self._split_by_headings(lines)
        else:
            raw_sections = self._split_by_separators(lines)

        chunks: list[ContentChunk] = []
        order = 0

        for section_title, section_content in raw_sections:
            if not section_content.strip():
                continue
            if len(section_content.strip()) < self.min_chunk_chars:
                continue

            section_key = detect_section_key(section_title)
            item_count = count_list_items(section_content)

            # Мета-дані чанку
            meta = {
                "source_file": source_file,
                "section_title": section_title,
                "item_count": item_count,
                "has_list": item_count > 0,
            }

            # Якщо секція велика — розбиваємо на підчанки
            sub_chunks = split_large_chunk(
                product_slug=product_slug,
                section_key=section_key,
                section_title=section_title,
                content=section_content.strip(),
                base_order=order,
                max_chars=self.max_chunk_chars,
            )

            for sc in sub_chunks:
                sc.metadata.update(meta)
                chunks.append(sc)
                order += 1

        return chunks

    # ── Приватні методи ───────────────────────────────────────────────────────

    def _split_by_headings(self, lines: list[str]) -> list[tuple[str, str]]:
        """
        Розбиття по ## заголовках.
        Повертає список (section_title, content).
        H1 (#) використовується як назва продукту — зберігається як 'product_header'.
        """
        sections: list[tuple[str, str]] = []
        current_title = "__header__"   # внутрішній маркер H1-шапки
        current_lines: list[str] = []

        for line in lines:
            level, title_text = is_heading(line)

            if level == 1:
                # H1 = назва продукту
                if current_lines:
                    sections.append((current_title, self._join_lines(current_lines)))
                current_title = f"__header__{title_text}"
                current_lines = []

            elif level >= 2:
                # H2, H3+ = нова секція
                if current_lines:
                    sections.append((current_title, self._join_lines(current_lines)))
                current_title = title_text
                current_lines = []

            elif is_separator(line):
                # --- між H2-секціями — ігноруємо
                pass

            else:
                current_lines.append(line)

        # Остання секція
        if current_lines:
            sections.append((current_title, self._join_lines(current_lines)))

        return sections

    def _split_by_separators(self, lines: list[str]) -> list[tuple[str, str]]:
        """
        Розбиття по горизонтальних лініях (---).
        Перший непорожній рядок після роздільника = заголовок секції.
        Повертає список (section_title, content).
        """
        sections: list[tuple[str, str]] = []
        blocks: list[list[str]] = []
        current_block: list[str] = []

        for line in lines:
            if is_separator(line):
                if current_block:
                    blocks.append(current_block)
                current_block = []
            else:
                current_block.append(line)

        if current_block:
            blocks.append(current_block)

        for block in blocks:
            # Перший непорожній рядок — заголовок
            title = ""
            content_lines: list[str] = []
            found_title = False

            for line in block:
                if not found_title:
                    if line.strip():
                        # Це заголовок
                        level, h_text = is_heading(line)
                        title = h_text if level > 0 else clean_line(line)
                        found_title = True
                else:
                    content_lines.append(line)

            if not title:
                continue

            content = self._join_lines(content_lines)
            sections.append((title, content))

        return sections

    def _join_lines(self, lines: list[str]) -> str:
        """
        Об'єднує рядки у текст:
        - Зберігає порожні рядки як роздільники абзаців
        - Прибирає зайві пробіли
        - Зберігає emoji (якщо keep_emojis=True)
        """
        cleaned: list[str] = []
        prev_empty = False

        for line in lines:
            stripped = line.rstrip()

            if not stripped:
                if not prev_empty:
                    cleaned.append("")
                prev_empty = True
            else:
                if not self.keep_emojis:
                    # Прибираємо emoji на початку рядка
                    stripped = re.sub(
                        r"^[\U00010000-\U0010FFFF\u2600-\u27BF\u2B50\u2702-\u27B0]+\s*",
                        "",
                        stripped
                    )
                cleaned.append(clean_line(stripped) if not stripped.startswith("#") else stripped)
                prev_empty = False

        # Прибираємо порожні рядки з початку та кінця
        while cleaned and not cleaned[0]:
            cleaned.pop(0)
        while cleaned and not cleaned[-1]:
            cleaned.pop()

        return "\n".join(cleaned)


# ── Звіт ──────────────────────────────────────────────────────────────────────

def print_report(chunks: list[ContentChunk]) -> None:
    """Виводить статистику чанкінгу в консоль."""
    if not chunks:
        print("[!] Chunks not found")
        return

    products = {}
    for c in chunks:
        products.setdefault(c.product_slug, []).append(c)

    print("\n" + "=" * 60)
    print("[STATS] PARSING REPORT")
    print("=" * 60)
    print(f"  Total chunks:    {len(chunks)}")
    print(f"  Products:        {len(products)}")
    print(f"  Avg chunk size:  {sum(c.char_count for c in chunks) // len(chunks)} chars")
    print(f"  Total tokens:    ~{sum(c.tokens_approx for c in chunks):,}")

    for slug, prod_chunks in products.items():
        print(f"\n  [{slug}] ({len(prod_chunks)} chunks):")
        for c in prod_chunks:
            split_mark = "[split]" if c.metadata.get("split") else "       "
            print(f"    {split_mark} [{c.section_key:<22}] {c.char_count:>5} chars  ~{c.tokens_approx:>4} tok  | {c.section_title[:35]}")

    print("=" * 60)


# ── Запис у БД ────────────────────────────────────────────────────────────────

def save_to_db(chunks: list[ContentChunk], db_url: str) -> None:
    """Зберігає чанки у таблицю chunks в PostgreSQL або SQLite."""

    create_table_sql = """
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
    """

    upsert_sql_pg = """
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

    upsert_sql_sqlite = """
    INSERT OR REPLACE INTO chunks
        (chunk_id, product_slug, section_key, section_title, content,
         char_count, tokens_approx, chunk_order, chunk_metadata)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    is_sqlite = db_url.startswith("sqlite")

    if is_sqlite:
        import sqlite3
        db_path = db_url.replace("sqlite:///", "")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Адаптація SQL для SQLite
        create_table_sqlite = create_table_sql.replace("SERIAL", "INTEGER").replace(
            "TIMESTAMPTZ", "TIMESTAMP"
        )
        for stmt in create_table_sqlite.split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    cursor.execute(stmt)
                except Exception:
                    pass

        for c in chunks:
            cursor.execute(upsert_sql_sqlite, (
                c.chunk_id, c.product_slug, c.section_key, c.section_title,
                c.content, c.char_count, c.tokens_approx, c.order,
                json.dumps(c.metadata, ensure_ascii=False)
            ))
        conn.commit()
        conn.close()
    else:
        try:
            import psycopg2
        except ImportError:
            print("❌ Встановіть psycopg2-binary: pip install psycopg2-binary")
            sys.exit(1)

        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        cursor.execute(create_table_sql)
        for c in chunks:
            cursor.execute(upsert_pg := upsert_sql_pg, (
                c.chunk_id, c.product_slug, c.section_key, c.section_title,
                c.content, c.char_count, c.tokens_approx, c.order,
                json.dumps(c.metadata, ensure_ascii=False)
            ))
        conn.commit()
        cursor.close()
        conn.close()

    print(f"  [OK] Saved {len(chunks)} chunks to DB")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(
        description="Парсер MD-файлів doTERRA → смислові чанки",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "input",
        help=(
            "Шлях до MD-файлу або директорії з MD-файлами.\n"
            "Приклади:\n"
            "  content/docs/frankincense.md\n"
            "  content/docs/"
        )
    )
    parser.add_argument(
        "--output", "-o",
        default="",
        help="Зберегти чанки у JSON-файл (наприклад: chunks.json)"
    )
    parser.add_argument(
        "--db",
        default=os.getenv("DATABASE_URL", "sqlite:///doterra_bot.db"),
        help="Рядок підключення до БД (або DATABASE_URL з env)"
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=MAX_CHUNK_CHARS,
        help=f"Максимальний розмір чанку в символах (default: {MAX_CHUNK_CHARS})"
    )
    parser.add_argument(
        "--no-emojis",
        action="store_true",
        help="Видаляти emoji-маркери з початку рядків"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Мінімальний вивід (без звіту)"
    )
    args = parser.parse_args()

    # Виправлення Railway postgres:// → postgresql://
    if args.db.startswith("postgres://"):
        args.db = args.db.replace("postgres://", "postgresql://", 1)

    # Ініціалізація парсера
    md_parser = DoterraMarkdownParser(
        max_chunk_chars=args.max_chars,
        keep_emojis=not args.no_emojis,
    )

    # Парсинг
    input_path = Path(args.input)
    print(f"\n[PARSE] Input: {input_path}")

    if input_path.is_dir():
        chunks = md_parser.parse_directory(input_path)
    elif input_path.is_file():
        chunks = md_parser.parse_file(input_path)
    else:
        print(f"❌ Не знайдено: {input_path}", file=sys.stderr)
        sys.exit(1)

    if not chunks:
        print("[!] Chunks not found. Check file format.")
        sys.exit(0)

    # Звіт
    if not args.quiet:
        print_report(chunks)

    # Збереження у JSON
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        data = [c.to_dict() for c in chunks]
        out_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n[SAVED] Output: {out_path} ({len(chunks)} chunks)")

    return chunks


# ── Публічний API (для імпорту в bot.py) ─────────────────────────────────────

def parse_md_file(filepath: str | Path, **kwargs) -> list[ContentChunk]:
    """Зручна функція для використання в боті."""
    p = DoterraMarkdownParser(**kwargs)
    return p.parse_file(filepath)


def parse_md_dir(dirpath: str | Path, **kwargs) -> list[ContentChunk]:
    """Зручна функція для парсингу директорії."""
    p = DoterraMarkdownParser(**kwargs)
    return p.parse_directory(dirpath)


def chunk_to_telegram_messages(
    chunk: ContentChunk,
    max_len: int = 4096
) -> list[str]:
    """
    Розбиває контент чанку на частини, придатні для Telegram-повідомлень.
    Telegram: максимум 4096 символів на повідомлення.
    """
    content = chunk.content
    if len(content) <= max_len:
        return [content]

    parts: list[str] = []
    paragraphs = content.split("\n\n")
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_len:
            current = (current + "\n\n" + para).lstrip("\n")
        else:
            if current:
                parts.append(current.strip())
            current = para

    if current:
        parts.append(current.strip())

    return parts


if __name__ == "__main__":
    main()

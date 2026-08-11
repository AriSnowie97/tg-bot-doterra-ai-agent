"""
doTERRA KB Uploader — Модуль завантаження MD-файлів у базу знань.

Використання:
    from src.kb_uploader.uploader import upload_md_to_kb

    result = upload_md_to_kb("/path/to/file.md", product_slug="frankincense")
    # result = {"total": 8, "inserted": 6, "skipped_duplicates": 2, "errors": 0}
"""

# Standard
import os
import sys
from pathlib import Path
# Special
from dotenv import load_dotenv

load_dotenv()

# Додаємо корінь проекту в sys.path, щоб імпорти src.* працювали при запуску напряму
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Local
from src.content.parser import DoterraMarkdownParser
from src.storage.storage import _upsert_chunk, іs_there_similar_embedding, _conn_create
from pgvector.psycopg2 import register_vector
from src.embedding import create_embedding
from pgvector import Vector


def upload_md_to_kb(
    md_path: str,
    product_slug: str,
    progress_callback=None,
) -> dict:
    """Парсить MD-файл і завантажує чанки в базу знань з перевіркою дублікатів.

    Args:
        md_path:           Шлях до MD-файлу.
        product_slug:      Ідентифікатор продукту (наприклад, 'frankincense').
        progress_callback: Опціональна функція(msg: str) для відправки прогресу.

    Returns:
        Словник зі статистикою:
        {
            "total":              <кількість чанків у файлі>,
            "inserted":           <скільки нових>,
            "skipped_duplicates": <скільки дублікатів>,
            "errors":             <скільки помилок>
        }
    """
    def _progress(msg: str):
        print(msg)
        if progress_callback:
            progress_callback(msg)

    stats = {"total": 0, "inserted": 0, "skipped_duplicates": 0, "errors": 0}

    md_path = Path(md_path)
    if not md_path.exists():
        raise FileNotFoundError(f"Файл не знайдено: {md_path}")

    # ── Парсинг ──────────────────────────────────────────────────────────────
    _progress(f"📄 Парсинг файлу <b>{md_path.name}</b>...")
    parser = DoterraMarkdownParser()
    chunks = parser.parse_file(md_path)

    # Якщо користувач передав slug — перевизначаємо у всіх чанках
    if product_slug:
        for chunk in chunks:
            chunk.product_slug = product_slug

    stats["total"] = len(chunks)

    if not chunks:
        _progress("⚠️ Файл не містить жодного чанку.")
        return stats

    _progress(
        f"🔍 Знайдено <b>{len(chunks)}</b> секцій.\n"
        "Генерую embeddings та перевіряю дублікати..."
    )

    # ── Завантаження по одному чанку ─────────────────────────────────────────
    conn = _conn_create()
    register_vector(conn)

    for i, chunk in enumerate(chunks, start=1):
        try:
            chunk_dict = chunk.to_dict() if hasattr(chunk, "to_dict") else vars(chunk)
            section = chunk_dict.get("section_title", chunk_dict.get("section_key", "?"))

            # Генеруємо embedding (займає ~1–3 сек на чанк)
            embedding = Vector(create_embedding(chunk_dict["content"]))

            with conn.cursor() as cur:
                is_dup = іs_there_similar_embedding(cur, chunk_dict, embedding)

            if is_dup:
                stats["skipped_duplicates"] += 1
                _progress(f"⏭ [{i}/{stats['total']}] <i>{section}</i> — дублікат, пропущено")
            else:
                _upsert_chunk(chunk_dict)
                stats["inserted"] += 1
                _progress(f"✅ [{i}/{stats['total']}] <i>{section}</i> — додано")

        except Exception as e:
            stats["errors"] += 1
            section = getattr(chunk, "section_title", "?")
            _progress(f"❌ [{i}/{stats['total']}] <i>{section}</i> — помилка: {e}")
            print(f"  Full error: {e}")

    conn.close()
    return stats

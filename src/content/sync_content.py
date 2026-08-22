"""
doTERRA Bot — Скрипт масового імпорту контенту (JSON + MD + Вектори)
Цей скрипт об'єднує функціонал seed.py (JSON), parser.py (MD) та створює
вектори (embeddings) для збереження у knowledge_chunks.

Публічне API:
    run_sync(progress_callback=None) -> dict
        Запускає повну синхронізацію та повертає статистику.
        Можна імпортувати з будь-якого місця проекту (наприклад, kb_bot.py).
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

# Завантажуємо .env обов'язково
load_dotenv(project_root / ".env")

from src.content.seed import load_product_files, validate_product, seed_sqlite, seed_postgresql
from src.content.parser import parse_md_dir
from src.storage.storage import bulk_upsert_chunks, creating_table_for_chunks


def run_sync(progress_callback=None) -> dict:
    """Виконує повну синхронізацію контенту: JSON картки + MD парсинг + векторизація.

    Args:
        progress_callback: опціональна функція(msg: str) для відправки прогресу
                           (наприклад, у Telegram-повідомлення).

    Returns:
        Словник зі статистикою:
        {
            "products":      <кількість оброблених JSON карток>,
            "chunks_found":  <кількість чанків з MD-файлів>,
            "errors":        <список рядків помилок>,
        }
    """
    def _log(msg: str) -> None:
        print(msg, flush=True)
        if progress_callback:
            try:
                progress_callback(msg)
            except Exception:
                pass

    stats = {"products": 0, "chunks_found": 0, "errors": []}

    # ── 1. JSON картки продуктів ──────────────────────────────────────────────
    _log("📦 <b>[1/3]</b> Завантаження JSON карток продуктів...")
    try:
        products = load_product_files()
        validation_errors = []
        for product in products:
            errs = validate_product(product)
            if errs:
                validation_errors.append(
                    f"{product.get('slug', '?')}: {'; '.join(errs)}"
                )

        if validation_errors:
            for ve in validation_errors:
                stats["errors"].append(f"Валідація: {ve}")
            _log(f"⚠️ Знайдено {len(validation_errors)} помилок валідації (продовжуємо).")

        is_railway = bool(os.getenv("RAILWAY_ENVIRONMENT"))
        db_url = os.getenv("DATABASE_URL", "") if is_railway else (
            os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL", "")
        )
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        if db_url.startswith("sqlite"):
            seed_sqlite(products, db_url)
        else:
            seed_postgresql(products, db_url)

        stats["products"] = len(products)
        _log(f"✅ Картки продуктів оновлено: <b>{len(products)}</b> шт.")
    except Exception as e:
        stats["errors"].append(f"JSON seed: {e}")
        _log(f"❌ Помилка при завантаженні JSON карток: <code>{e}</code>")

    # ── 2. Парсинг MD-файлів ─────────────────────────────────────────────────
    _log("\n📄 <b>[2/3]</b> Парсинг MD-документів...")
    
    md_dirs = [
        project_root / "src" / "content" / "docs",
        project_root / "src" / "content" / "products",
        project_root / "src" / "content" / "advice",
        project_root / "src" / "content" / "symphony_of_the_cells",
    ]
    chunks = []
    for d in md_dirs:
        if not d.exists():
            msg = f"Директорія не знайдена: {d}"
            stats["errors"].append(msg)
            _log(f"❌ {msg}")
        else:
            try:
                dir_chunks = parse_md_dir(d)
                chunks.extend(dir_chunks)
                _log(f"✅ Знайдено чанків: <b>{len(dir_chunks)}</b> з {d.name}/")
            except Exception as e:
                stats["errors"].append(f"MD парсинг ({d.name}): {e}")
                _log(f"❌ Помилка парсингу MD ({d.name}): <code>{e}</code>")
                
    stats["chunks_found"] = len(chunks)
    _log(f"✅ Всього знайдено чанків: <b>{len(chunks)}</b>")

    # ── 3. Векторизація і запис у БД ─────────────────────────────────────────
    if chunks:
        _log("\n🔢 <b>[3/3]</b> Генерація embeddings та збереження у knowledge_chunks...")
        try:
            creating_table_for_chunks()
            chunk_dicts = [c.to_dict() for c in chunks]
            bulk_upsert_chunks(chunk_dicts)
            _log("✅ Вектори збережено у БД!")
        except Exception as e:
            stats["errors"].append(f"Векторизація: {e}")
            _log(f"❌ Помилка векторизації: <code>{e}</code>")
    else:
        _log("⚠️ Чанки не знайдено — векторизація пропущена.")

    return stats


def main():
    """CLI-обгортка для запуску sync_content.py з командного рядка."""
    # Розумний вибір URL для локального/серверного запуску
    is_railway = bool(os.getenv("RAILWAY_ENVIRONMENT"))
    default_db = os.getenv("DATABASE_URL", "sqlite:///doterra_bot.db")
    if not is_railway and os.getenv("DATABASE_PUBLIC_URL"):
        default_db = os.getenv("DATABASE_PUBLIC_URL")

    parser = argparse.ArgumentParser(description="Імпорт контенту у базу даних doTERRA Bot")
    parser.add_argument("--db", default=default_db, help="Рядок підключення до БД")
    args = parser.parse_args()

    if args.db.startswith("postgres://"):
        args.db = args.db.replace("postgres://", "postgresql://", 1)

    import src.storage.storage as storage_mod
    storage_mod.DATABASE_URL = args.db
    storage_mod.DATABASE_PUBLIC_URL = args.db
    storage_mod.IS_RAILWAY = True

    print("\n📦 doTERRA Bot — Масовий імпорт контенту", flush=True)
    print("=" * 60, flush=True)
    print(f"🔗 Підключення до бази: {args.db[:50]}...", flush=True)

    stats = run_sync()

    print("\n" + "=" * 60)
    if stats["errors"]:
        print(f"⚠️  Завершено з {len(stats['errors'])} помилками:")
        for err in stats["errors"]:
            print(f"   • {err}")
    else:
        print("🎉 Масовий імпорт контенту успішно завершено!")
    print("=" * 60)

    if stats["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
doTERRA Bot — Скрипт масового імпорту контенту (JSON + MD + Вектори)
Цей скрипт об'єднує функціонал seed.py (JSON), parser.py (MD) та створює
вектори (embeddings) для збереження у knowledge_chunks.
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

def main():
    # Розумний вибір URL для локального/серверного запуску
    is_railway = bool(os.getenv("RAILWAY_ENVIRONMENT"))
    default_db = os.getenv("DATABASE_URL", "sqlite:///doterra_bot.db")
    if not is_railway and os.getenv("DATABASE_PUBLIC_URL"):
        default_db = os.getenv("DATABASE_PUBLIC_URL")

    parser = argparse.ArgumentParser(description="Імпорт контенту у базу даних doTERRA Bot")
    parser.add_argument(
        "--db",
        default=default_db,
        help="Рядок підключення до БД"
    )
    args = parser.parse_args()

    # Виправлення Railway postgres:// → postgresql://
    if args.db.startswith("postgres://"):
        args.db = args.db.replace("postgres://", "postgresql://", 1)

    # Примусово вказуємо storage.py використовувати цей самий URL
    import src.storage.storage as storage_mod
    storage_mod.DATABASE_URL = args.db
    storage_mod.DATABASE_PUBLIC_URL = args.db
    storage_mod.IS_RAILWAY = True # Завжди використовувати наданий URL

    print("\n📦 doTERRA Bot — Масовий імпорт контенту", flush=True)
    print("=" * 60, flush=True)
    print(f"🔗 Підключення до бази: {args.db[:50]}...", flush=True)

    # 1. Завантаження JSON карток
    print("\n[1/3] Оновлення карток продуктів (JSON)...", flush=True)
    products = load_product_files()
    
    print(f"🔍 Валідація {len(products)} продуктів...", flush=True)
    all_valid = True
    for product in products:
        errors = validate_product(product)
        if errors:
            print(f"  ❌ {product.get('slug', 'unknown')}: {'; '.join(errors)}")
            all_valid = False

    if not all_valid:
        print("\n❌ Знайдено помилки валідації в JSON. Виправте та запустіть знову.")
        sys.exit(1)

    if args.db.startswith("sqlite"):
        seed_sqlite(products, args.db)
    else:
        seed_postgresql(products, args.db)
    print(f"✅ Базу продуктів ({len(products)} штук) успішно оновлено!", flush=True)

    # 2. Парсинг MD файлів
    print("\n[2/3] Парсинг текстів продуктів (Markdown)...", flush=True)
    docs_dir = project_root / "src" / "content" / "docs"
    
    if not docs_dir.exists():
        print(f"❌ Директорія {docs_dir} не знайдена!")
        sys.exit(1)

    # parser_dir expects a path object or string
    # We pass quiet=True to avoid printing the big report if supported
    # Wait, parse_md_dir doesn't take quiet as kwarg in my previous view, let's just not pass it.
    chunks = parse_md_dir(docs_dir)
    if not chunks:
        print("❌ Не знайдено жодного тексту для парсингу.", flush=True)
        sys.exit(1)
        
    print(f"✅ Знайдено {len(chunks)} текстових фрагментів (чанків) у {docs_dir.name}/", flush=True)

    # 3. Генерація векторів та запис у knowledge_chunks
    print("\n[3/3] Генерація векторів та збереження у knowledge_chunks...", flush=True)
    try:
        # Переконаємось, що таблиця існує (з pgvector)
        creating_table_for_chunks()
        
        chunk_dicts = [c.to_dict() for c in chunks]
        bulk_upsert_chunks(chunk_dicts)
        print("✅ Вектори успішно згенеровано та збережено у БД!")
    except Exception as e:
        print(f"❌ Помилка під час збереження векторів: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("🎉 Масовий імпорт контенту успішно завершено!")
    print("=" * 60)

if __name__ == "__main__":
    main()

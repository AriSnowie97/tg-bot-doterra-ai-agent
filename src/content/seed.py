"""
doTERRA Bot — Скрипт завантаження першого пакету контенту в БД
Сумісний з Railway (DATABASE_URL із змінних оточення)

Використання на Railway:
    # В Railway Dashboard → Variables додайте DATABASE_URL (автоматично є якщо підключена PostgreSQL)
    # Потім у Railway → Settings → Deploy → Start Command:
    #   python content/seed.py && python bot.py
    # АБО запустіть один раз вручну через Railway CLI:
    #   railway run python content/seed.py

Локальне використання:
    # SQLite (для тестування без БД)
    python content/seed.py --db sqlite:///test.db

    # PostgreSQL локально
    DATABASE_URL=postgresql://user:pass@localhost/doterra python content/seed.py

    # Тільки валідувати JSON
    python content/seed.py --validate-only
"""

import json
import os
import sys
import argparse
import glob
from datetime import datetime

# ── Залежності ──────────────────────────────────────────────────────────────
# pip install psycopg2-binary  (для PostgreSQL)
# pip install (вбудовано sqlite3 для SQLite)


CONTENT_DIR = os.path.dirname(__file__)
DATA_DIRS = ["products", "advice", "kits"]

def load_product_files() -> list[dict]:
    """Завантажити всі JSON-файли продуктів з директорій products, advice, kits"""
    all_products = []
    for d in DATA_DIRS:
        pattern = os.path.join(CONTENT_DIR, d, "*.json")
        files = sorted(glob.glob(pattern))
        files = [f for f in files if not f.endswith("_chunks.json")]
        print(f"📦 Завантаження пакету: {d} ({len(files)} продуктів)")
        for filepath in files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Якщо це список (наприклад, старий формат), беремо перший елемент
                    if isinstance(data, list):
                        data = data[0]
                    all_products.append(data)
            except Exception as e:
                print(f"  ❌ Помилка завантаження {os.path.basename(filepath)}: {e}")

    if not all_products:
        print(f"❌ Не знайдено JSON-файлів у {DATA_DIRS}")
        sys.exit(1)

    return all_products


def validate_product(product: dict) -> list[str]:
    """Перевірити обов'язкові поля продукту. Повертає список помилок."""
    errors = []
    required_fields = ["slug", "name_ua", "name_en", "type"]

    for field in required_fields:
        if not product.get(field):
            errors.append(f"Відсутнє обов'язкове поле: '{field}'")

    valid_types = {"single", "blend", "supplement"}
    if product.get("type") and product["type"] not in valid_types:
        errors.append(f"Невалідний тип: '{product['type']}'. Дозволено: {valid_types}")

    # Перевірка JSON-полів
    json_array_fields = [
        "tags", "product_variants", "short_description", "physical_effects",
        "indications", "interesting_facts", "diffuser_blends", "precautions",
        "research", "expert_quotes", "drug_interactions", "contraindications"
    ]
    json_object_fields = ["emotional_effects", "usage", "origin", "dosage_guide"]

    for field in json_array_fields:
        value = product.get(field)
        if value is not None and not isinstance(value, list):
            errors.append(f"Поле '{field}' має бути масивом (list)")

    for field in json_object_fields:
        value = product.get(field)
        if value is not None and not isinstance(value, dict):
            errors.append(f"Поле '{field}' має бути об'єктом (dict)")

    return errors


def json_serialize(value) -> str | None:
    """Серіалізувати Python-об'єкт у JSON-рядок для збереження в БД."""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def seed_sqlite(products: list[dict], db_path: str):
    """Завантажити дані у SQLite базу даних."""
    import sqlite3

    # Видалити "sqlite:///" префікс якщо є
    db_path = db_path.replace("sqlite:///", "")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Читаємо та виконуємо схему
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    if os.path.exists(schema_path):
        with open(schema_path, encoding="utf-8") as f:
            schema_sql = f.read()
        # SQLite: прибираємо PostgreSQL-специфічні речі
        schema_sql = schema_sql.replace("SERIAL", "INTEGER")
        schema_sql = schema_sql.replace("TIMESTAMPTZ", "TIMESTAMP")
        
        try:
            cursor.executescript(schema_sql)
        except Exception as e:
            print(f"Schema Error: {e}")

    inserted = 0
    updated = 0

    for product in products:
        now = datetime.now().isoformat()

        row = {
            "slug": product.get("slug"),
            "name_ua": product.get("name_ua"),
            "name_en": product.get("name_en"),
            "type": product.get("type"),
            "tags": json_serialize(product.get("tags")),
            "product_variants": json_serialize(product.get("product_variants")),
            "short_description": json_serialize(product.get("short_description")),
            "physical_effects": json_serialize(product.get("physical_effects")),
            "emotional_effects": json_serialize(product.get("emotional_effects")),
            "usage": json_serialize(product.get("usage")),
            "indications": json_serialize(product.get("indications")),
            "origin": json_serialize(product.get("origin")),
            "beauty_skincare": json_serialize(product.get("beauty_skincare")),
            "interesting_facts": json_serialize(product.get("interesting_facts")),
            "diffuser_blends": json_serialize(product.get("diffuser_blends")),
            "additional_info": product.get("additional_info"),
            "precautions": json_serialize(product.get("precautions")),
            "disclaimer": product.get("disclaimer"),
            "research": json_serialize(product.get("research")),
            "expert_quotes": json_serialize(product.get("expert_quotes")),
            "drug_interactions": json_serialize(product.get("drug_interactions")),
            "dosage_guide": json_serialize(product.get("dosage_guide")),
            "contraindications": json_serialize(product.get("contraindications")),
            "updated_at": now,
        }

        # Upsert: вставити або оновити якщо slug вже існує
        cursor.execute("SELECT id FROM products WHERE slug = ?", (row["slug"],))
        existing = cursor.fetchone()

        if existing:
            set_clause = ", ".join([f"{k} = ?" for k in row.keys()])
            cursor.execute(
                f"UPDATE products SET {set_clause} WHERE slug = ?",
                list(row.values()) + [row["slug"]]
            )
            updated += 1
            print(f"  🔄 Оновлено: {product.get('name_ua')} ({row['slug']})")
        else:
            row["created_at"] = now
            cols = ", ".join(row.keys())
            placeholders = ", ".join(["?" for _ in row])
            cursor.execute(
                f"INSERT INTO products ({cols}) VALUES ({placeholders})",
                list(row.values())
            )
            inserted += 1
            print(f"  ➕ Додано: {product.get('name_ua')} ({row['slug']})")

    conn.commit()
    conn.close()

    print(f"\n✅ SQLite: {inserted} додано, {updated} оновлено")
    print(f"   Файл БД: {os.path.abspath(db_path)}")


def seed_postgresql(products: list[dict], conn_string: str):
    """Завантажити дані у PostgreSQL базу даних."""
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        print("❌ Встановіть psycopg2: pip install psycopg2-binary")
        sys.exit(1)

    # psycopg2 приймає повний URL напряму (postgresql://user:pass@host:port/db)
    # Railway може повертати postgres:// — нормалізуємо до postgresql://
    if conn_string.startswith("postgres://"):
        conn_string = conn_string.replace("postgres://", "postgresql://", 1)

    # Retry-логіка: Railway PostgreSQL може стартувати пізніше за бот
    import time
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            conn = psycopg2.connect(conn_string)
            break
        except psycopg2.OperationalError as e:
            if attempt == max_retries:
                print(f"❌ Не вдалося підключитися до БД після {max_retries} спроб: {e}")
                sys.exit(1)
            wait = 2 ** attempt  # 2, 4, 8, 16 секунд
            print(f"⏳ Спроба {attempt}/{max_retries} невдала. Повтор через {wait}с...")
            time.sleep(wait)

    cursor = conn.cursor()

    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    if os.path.exists(schema_path):
        with open(schema_path, encoding="utf-8") as f:
            cursor.execute(f.read())

    inserted = 0
    updated = 0

    for product in products:
        now = datetime.now()

        row = {
            "slug": product.get("slug"),
            "name_ua": product.get("name_ua"),
            "name_en": product.get("name_en"),
            "type": product.get("type"),
            "tags": json_serialize(product.get("tags")),
            "product_variants": json_serialize(product.get("product_variants")),
            "short_description": json_serialize(product.get("short_description")),
            "physical_effects": json_serialize(product.get("physical_effects")),
            "emotional_effects": json_serialize(product.get("emotional_effects")),
            "usage": json_serialize(product.get("usage")),
            "indications": json_serialize(product.get("indications")),
            "origin": json_serialize(product.get("origin")),
            "beauty_skincare": json_serialize(product.get("beauty_skincare")),
            "interesting_facts": json_serialize(product.get("interesting_facts")),
            "diffuser_blends": json_serialize(product.get("diffuser_blends")),
            "additional_info": product.get("additional_info"),
            "precautions": json_serialize(product.get("precautions")),
            "disclaimer": product.get("disclaimer"),
            "research": json_serialize(product.get("research")),
            "expert_quotes": json_serialize(product.get("expert_quotes")),
            "drug_interactions": json_serialize(product.get("drug_interactions")),
            "dosage_guide": json_serialize(product.get("dosage_guide")),
            "contraindications": json_serialize(product.get("contraindications")),
            "updated_at": now,
        }

        cursor.execute("SELECT id FROM products WHERE slug = %s", (row["slug"],))
        existing = cursor.fetchone()

        if existing:
            set_clause = ", ".join([f"{k} = %s" for k in row.keys()])
            cursor.execute(
                f"UPDATE products SET {set_clause} WHERE slug = %s",
                list(row.values()) + [row["slug"]]
            )
            updated += 1
            print(f"  🔄 Оновлено: {product.get('name_ua')} ({row['slug']})")
        else:
            row["created_at"] = now
            cols = ", ".join(row.keys())
            placeholders = ", ".join(["%s" for _ in row])
            cursor.execute(
                f"INSERT INTO products ({cols}) VALUES ({placeholders})",
                list(row.values())
            )
            inserted += 1
            print(f"  ➕ Додано: {product.get('name_ua')} ({row['slug']})")

    conn.commit()
    cursor.close()
    conn.close()

    print(f"\n✅ PostgreSQL: {inserted} додано, {updated} оновлено")


def main():
    # ── Визначення рядка підключення до БД ──────────────────────────────────
    # Пріоритет: DATABASE_URL (Railway/Render/Heroku) → --db аргумент → SQLite тест
    env_db_url = os.getenv("DATABASE_URL", "")

    # Railway іноді повертає postgres:// замість postgresql:// — виправляємо
    if env_db_url.startswith("postgres://"):
        env_db_url = env_db_url.replace("postgres://", "postgresql://", 1)

    parser = argparse.ArgumentParser(
        description="Завантаження першого пакету контенту doTERRA в БД",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--db",
        default=env_db_url or "sqlite:///doterra_bot.db",
        help=(
            "Рядок підключення до БД.\n"
            "За замовчуванням використовується DATABASE_URL з оточення.\n"
            "Приклади:\n"
            "  sqlite:///doterra_bot.db\n"
            "  postgresql://user:pass@localhost/doterra"
        )
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Тільки перевірити JSON без запису в БД"
    )
    args = parser.parse_args()

    print("\n📦 doTERRA Bot — Оновлення бази продуктів")
    print("=" * 55)

    # Показати звідки взято DATABASE_URL
    if env_db_url and not any(a.startswith("--db") for a in sys.argv):
        print(f"🔗 Підключення з DATABASE_URL (env)")
    else:
        print(f"🔗 Підключення: {args.db[:60]}...")

    print(f"\n📂 Пошук файлів по категоріях...")
    products = load_product_files()

    print(f"\n🔍 Валідація {len(products)} продуктів...")
    all_valid = True
    for product in products:
        errors = validate_product(product)
        if errors:
            print(f"  ❌ {product.get('slug', 'unknown')}: {'; '.join(errors)}")
            all_valid = False
        else:
            print(f"  ✅ {product.get('slug')} — валідний")

    if not all_valid:
        print("\n❌ Знайдено помилки валідації. Виправте та запустіть знову.")
        sys.exit(1)

    if args.validate_only:
        print(f"\n✅ Всі {len(products)} продуктів пройшли валідацію!")
        print("   (Режим --validate-only: запис у БД не виконується)")
        return

    print(f"\n💾 Завантаження в БД...")
    if args.db.startswith("sqlite"):
        seed_sqlite(products, args.db)
    else:
        seed_postgresql(products, args.db)

    print(f"\n🎉 Базу продуктів ({len(products)} штук) успішно оновлено!")
    print("   Наступний крок: перевірте команди бота.")



if __name__ == "__main__":
    main()

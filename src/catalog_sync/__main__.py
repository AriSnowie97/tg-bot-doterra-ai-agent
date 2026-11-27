"""
CLI-запуск глобальної синхронізації каталогу doTERRA:

    python -m src.catalog_sync                       # Postgres (runtime)
    python -m src.catalog_sync --write-files         # Запис .md у src/content/products/ (для GitHub Actions)
    python -m src.catalog_sync --dry-run --markets US,EU,UK
"""

from __future__ import annotations

import argparse
import asyncio
import json

from dotenv import load_dotenv

from .markets import GLOBAL_MARKETS
from .service import (
    deduplicate_dynamic_overrides,
    deduplicate_static_products,
    run_catalog_sync,
)


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Глобальна синхронізація каталогу doTERRA по всіх ринках")
    parser.add_argument("--write-files", action="store_true", help="Записувати нові/архівні .md файли у src/content/products/")
    parser.add_argument("--no-db", action="store_true", help="Не записувати зміни в PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Лише перевірка без внесення змін")
    parser.add_argument("--dedup-only", action="store_true", help="Лише перевірка на дублікати (об'єднання інформації + видалення дублів)")
    parser.add_argument("--max-new", type=int, default=15, help="Максимум нових карток за один прогон")
    parser.add_argument("--markets", default="", help="Список кодів ринків через кому (напр. US,EU,UK). Порожньо = усі 18")
    parser.add_argument("--json-out", default="", help="Зберегти JSON-звіт у файл")
    args = parser.parse_args()

    if args.dedup_only:
        report = {"static": None, "dynamic": None}
        if args.write_files or args.no_db:
            report["static"] = deduplicate_static_products(dry_run=args.dry_run)
        if not args.no_db:
            report["dynamic"] = deduplicate_dynamic_overrides(dry_run=args.dry_run)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if args.json_out:
            with open(args.json_out, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        return

    selected = GLOBAL_MARKETS
    if args.markets.strip():
        wanted = {c.strip().upper() for c in args.markets.split(",") if c.strip()}
        selected = tuple(m for m in GLOBAL_MARKETS if m.code in wanted)

    report = asyncio.run(
        run_catalog_sync(
            markets=selected,
            write_files=args.write_files,
            save_db=not args.no_db,
            dry_run=args.dry_run,
            max_new=args.max_new,
        )
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

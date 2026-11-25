"""
Постійне сховище динамічних змін каталогу у PostgreSQL (`catalog_overrides`).

Гарантує, що автоматично додані новинки та архівовані (зняті з усіх ринків) позиції
зберігаються між перезапусками та перезбірками Docker-контейнера на Railway.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from src.safety import redact

# Кеш у пам'яті, щоб Mini App API (/api/articles) не бив у БД на кожен клік
_CACHE_TTL_SECONDS = 30.0
_CACHE: dict[str, Any] = {"ts": 0.0, "active": [], "archived": set()}


def _has_db_config() -> bool:
    return bool(os.getenv("DATABASE_URL") or os.getenv("DATABASE_PUBLIC_URL"))


def _get_conn():
    from src.storage.storage import _conn_create
    return _conn_create()


def invalidate_overrides_cache() -> None:
    """Скидає in-memory кеш каталогу після змін."""
    _CACHE["ts"] = 0.0


def ensure_catalog_tables() -> bool:
    """Створює таблиці `catalog_overrides` та `catalog_sync_runs`, якщо їх ще немає."""
    if not _has_db_config():
        return False
    conn = None
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS catalog_overrides (
                    slug            VARCHAR(120) PRIMARY KEY,
                    status          VARCHAR(20)  NOT NULL DEFAULT 'active',
                    title_ua        TEXT         NOT NULL DEFAULT '',
                    title_en        TEXT         NOT NULL DEFAULT '',
                    category_ua     VARCHAR(100) NOT NULL DEFAULT 'Ефірні олії',
                    category_en     VARCHAR(100) NOT NULL DEFAULT 'Essential Oils',
                    short_ua        TEXT         NOT NULL DEFAULT '',
                    short_en        TEXT         NOT NULL DEFAULT '',
                    image_url       TEXT         NOT NULL DEFAULT '',
                    md_ua           TEXT         NOT NULL DEFAULT '',
                    md_en           TEXT         NOT NULL DEFAULT '',
                    markets         TEXT         NOT NULL DEFAULT '[]',
                    source_url      TEXT         NOT NULL DEFAULT '',
                    change_type     VARCHAR(20)  NOT NULL DEFAULT 'new',
                    missing_streak  INTEGER      NOT NULL DEFAULT 0,
                    last_seen_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
                    updated_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
                );
                ALTER TABLE catalog_overrides
                    ADD COLUMN IF NOT EXISTS change_type VARCHAR(20) NOT NULL DEFAULT 'new';
                UPDATE catalog_overrides
                    SET change_type = 'track'
                    WHERE status = 'active' AND change_type = 'new'
                      AND length(COALESCE(md_ua, '')) = 0 AND length(COALESCE(md_en, '')) = 0;
                CREATE INDEX IF NOT EXISTS idx_catalog_overrides_status
                    ON catalog_overrides(status);

                CREATE TABLE IF NOT EXISTS catalog_sync_runs (
                    id                SERIAL PRIMARY KEY,
                    started_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    markets_checked   INTEGER   NOT NULL DEFAULT 0,
                    markets_healthy   INTEGER   NOT NULL DEFAULT 0,
                    added_count       INTEGER   NOT NULL DEFAULT 0,
                    restored_count    INTEGER   NOT NULL DEFAULT 0,
                    archived_count    INTEGER   NOT NULL DEFAULT 0,
                    notes             TEXT      NOT NULL DEFAULT ''
                );
                """
            )
        conn.commit()
        return True
    except Exception as e:
        print(f"[catalog_sync.store] ensure_catalog_tables error: {redact(e)}")
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def get_catalog_overrides(force_refresh: bool = False) -> tuple[list[dict], set[str]]:
    """Повертає (active_items, archived_slugs) із PostgreSQL (з 60-сек кешем).

    Якщо БД недоступна — безпечно повертає ([], set()), щоб веб-сервер і бот не падали.
    """
    now = time.monotonic()
    if not force_refresh and (now - _CACHE["ts"]) < _CACHE_TTL_SECONDS and _CACHE["ts"] > 0:
        return list(_CACHE["active"]), set(_CACHE["archived"])

    if not _has_db_config():
        return [], set()

    conn = None
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT slug, status, title_ua, title_en, category_ua, category_en,
                       short_ua, short_en, image_url, md_ua, md_en, markets, source_url,
                       missing_streak, COALESCE(change_type, 'new'), updated_at
                FROM catalog_overrides
                """
            )
            rows = cur.fetchall()
    except Exception:
        # Таблиці може ще не бути або БД недоступна — працюємо лише зі статичним контентом
        return [], set()
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    active: list[dict] = []
    archived: set[str] = set()
    for row in rows:
        (
            slug, status, title_ua, title_en, category_ua, category_en,
            short_ua, short_en, image_url, md_ua, md_en, markets_raw, source_url,
            missing_streak, change_type, updated_at
        ) = row
        try:
            markets = json.loads(markets_raw or "[]")
        except Exception:
            markets = []
        if status == "archived":
            archived.add(slug)
        elif status == "active":
            active.append({
                "slug": slug,
                "status": status,
                "title_ua": title_ua,
                "title_en": title_en,
                "category_ua": category_ua,
                "category_en": category_en,
                "short_ua": short_ua,
                "short_en": short_en,
                "image_url": image_url,
                "md_ua": md_ua,
                "md_en": md_en,
                "markets": markets,
                "source_url": source_url,
                "missing_streak": int(missing_streak or 0),
                "change_type": change_type or "new",
                "updated_at": str(updated_at or ""),
            })

    _CACHE["ts"] = now
    _CACHE["active"] = active
    _CACHE["archived"] = archived
    return list(active), set(archived)


def get_override_doc(slug: str, lang: str = "ua") -> tuple[str | None, str | None, bool]:
    """Повертає (title, md_text, is_archived) для конкретного slug із `catalog_overrides`."""
    active, archived = get_catalog_overrides()
    if slug in archived:
        return None, None, True
    for item in active:
        if item["slug"] == slug:
            if lang == "en":
                return item["title_en"] or item["title_ua"], item["md_en"] or item["md_ua"], False
            return item["title_ua"] or item["title_en"], item["md_ua"] or item["md_en"], False
    return None, None, False


def get_all_override_states() -> dict[str, dict]:
    """Повертає повну мапу {slug: {status, missing_streak, markets, has_md}} для синхронізатора."""
    if not _has_db_config():
        return {}
    conn = None
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT slug, status, missing_streak, markets, (length(md_ua) > 0) FROM catalog_overrides"
            )
            result = {}
            for slug, status, streak, markets_raw, has_md in cur.fetchall():
                try:
                    markets = json.loads(markets_raw or "[]")
                except Exception:
                    markets = []
                result[slug] = {
                    "status": status,
                    "missing_streak": int(streak or 0),
                    "markets": markets,
                    "has_md": bool(has_md),
                }
            return result
    except Exception as e:
        print(f"[catalog_sync.store] get_all_override_states error: {redact(e)}")
        return {}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def upsert_catalog_item(item: dict) -> bool:
    """Додає або оновлює активний продукт у `catalog_overrides`."""
    if not _has_db_config():
        return False
    conn = None
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO catalog_overrides
                    (slug, status, title_ua, title_en, category_ua, category_en,
                     short_ua, short_en, image_url, md_ua, md_en, markets, source_url,
                     change_type, missing_streak, last_seen_at, updated_at)
                VALUES (%s, 'active', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (slug) DO UPDATE SET
                    status         = 'active',
                    title_ua       = CASE WHEN EXCLUDED.title_ua <> '' THEN EXCLUDED.title_ua ELSE catalog_overrides.title_ua END,
                    title_en       = CASE WHEN EXCLUDED.title_en <> '' THEN EXCLUDED.title_en ELSE catalog_overrides.title_en END,
                    category_ua    = CASE WHEN EXCLUDED.category_ua <> '' THEN EXCLUDED.category_ua ELSE catalog_overrides.category_ua END,
                    category_en    = CASE WHEN EXCLUDED.category_en <> '' THEN EXCLUDED.category_en ELSE catalog_overrides.category_en END,
                    short_ua       = CASE WHEN EXCLUDED.short_ua <> '' THEN EXCLUDED.short_ua ELSE catalog_overrides.short_ua END,
                    short_en       = CASE WHEN EXCLUDED.short_en <> '' THEN EXCLUDED.short_en ELSE catalog_overrides.short_en END,
                    image_url      = CASE WHEN EXCLUDED.image_url <> '' THEN EXCLUDED.image_url ELSE catalog_overrides.image_url END,
                    md_ua          = CASE WHEN EXCLUDED.md_ua <> '' THEN EXCLUDED.md_ua ELSE catalog_overrides.md_ua END,
                    md_en          = CASE WHEN EXCLUDED.md_en <> '' THEN EXCLUDED.md_en ELSE catalog_overrides.md_en END,
                    markets        = EXCLUDED.markets,
                    source_url     = CASE WHEN EXCLUDED.source_url <> '' THEN EXCLUDED.source_url ELSE catalog_overrides.source_url END,
                    change_type    = EXCLUDED.change_type,
                    missing_streak = 0,
                    last_seen_at   = CURRENT_TIMESTAMP,
                    updated_at     = CURRENT_TIMESTAMP
                """,
                (
                    item["slug"],
                    item.get("title_ua", ""),
                    item.get("title_en", ""),
                    item.get("category_ua", "Ефірні олії"),
                    item.get("category_en", "Essential Oils"),
                    item.get("short_ua", ""),
                    item.get("short_en", ""),
                    item.get("image_url", ""),
                    item.get("md_ua", ""),
                    item.get("md_en", ""),
                    json.dumps(item.get("markets", []), ensure_ascii=False),
                    item.get("source_url", ""),
                    item.get("change_type", "new"),
                ),
            )
        conn.commit()
        invalidate_overrides_cache()
        return True
    except Exception as e:
        print(f"[catalog_sync.store] upsert_catalog_item({item.get('slug')}) error: {redact(e)}")
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def record_missing_streak(slug: str, streak: int, archive: bool) -> bool:
    """Оновлює лічильник пропусків продукту або переводить його у статус `archived`."""
    if not _has_db_config():
        return False
    status = "archived" if archive else "active"
    conn = None
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO catalog_overrides (slug, status, change_type, missing_streak, updated_at)
                VALUES (%s, %s, 'track', %s, CURRENT_TIMESTAMP)
                ON CONFLICT (slug) DO UPDATE SET
                    status         = EXCLUDED.status,
                    missing_streak = EXCLUDED.missing_streak,
                    updated_at     = CURRENT_TIMESTAMP
                """,
                (slug, status, streak),
            )
            if archive:
                # Видаляємо чанки архівованого товару з векторного пошуку RAG
                try:
                    cur.execute("DELETE FROM knowledge_chunks WHERE product_slug = %s", (slug,))
                except Exception:
                    pass
        conn.commit()
        invalidate_overrides_cache()
        return True
    except Exception as e:
        print(f"[catalog_sync.store] record_missing_streak({slug}) error: {redact(e)}")
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def log_sync_run(
    markets_checked: int,
    markets_healthy: int,
    added: int,
    restored: int,
    archived: int,
    notes: str = "",
) -> None:
    if not _has_db_config():
        return
    conn = None
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO catalog_sync_runs
                    (markets_checked, markets_healthy, added_count, restored_count, archived_count, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (markets_checked, markets_healthy, added, restored, archived, notes[:1000]),
            )
        conn.commit()
    except Exception as e:
        print(f"[catalog_sync.store] log_sync_run error: {redact(e)}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def get_catalog_stats() -> dict:
    """Повертає статистику `catalog_overrides` та останній прогон для команди /catalog_status."""
    stats = {
        "db_connected": False,
        "dynamic_active": 0,
        "archived": 0,
        "last_run": None,
    }
    if not _has_db_config():
        return stats
    conn = None
    try:
        ensure_catalog_tables()
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status = 'active' AND length(md_ua) > 0),
                    COUNT(*) FILTER (WHERE status = 'archived')
                FROM catalog_overrides
                """
            )
            row = cur.fetchone()
            if row:
                stats["dynamic_active"] = int(row[0] or 0)
                stats["archived"] = int(row[1] or 0)
            cur.execute(
                """
                SELECT started_at, markets_checked, markets_healthy, added_count, restored_count, archived_count, notes
                FROM catalog_sync_runs
                ORDER BY id DESC LIMIT 1
                """
            )
            run = cur.fetchone()
            if run:
                stats["last_run"] = {
                    "started_at": str(run[0]),
                    "markets_checked": run[1],
                    "markets_healthy": run[2],
                    "added": run[3],
                    "restored": run[4],
                    "archived": run[5],
                    "notes": run[6],
                }
        stats["db_connected"] = True
    except Exception as e:
        print(f"[catalog_sync.store] get_catalog_stats error: {redact(e)}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    return stats

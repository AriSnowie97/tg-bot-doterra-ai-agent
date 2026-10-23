# Standard
import os
import json
import psycopg2
from pgvector import Vector
from pgvector.psycopg2 import register_vector
# Local
from ..embedding import create_embedding
from ..safety import redact


DATABASE_URL = os.getenv("DATABASE_URL", "")
DATABASE_PUBLIC_URL = os.getenv("DATABASE_PUBLIC_URL", "")

# Railway sometimes returns "postgres://" instead of "postgresql://" — fix it.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
if DATABASE_PUBLIC_URL.startswith("postgres://"):
    DATABASE_PUBLIC_URL = DATABASE_PUBLIC_URL.replace("postgres://", "postgresql://", 1)

# Detect environment: Railway sets RAILWAY_ENVIRONMENT automatically.
# If it's absent — we're running locally.
IS_RAILWAY = bool(os.getenv("RAILWAY_ENVIRONMENT"))


def _conn_create():
    """Створення зв'язку з БД.

    Логіка вибору URL:
    - На Railway (IS_RAILWAY=True): використовується DATABASE_URL (внутрішня мережа Railway).
    - Локально (IS_RAILWAY=False): використовується DATABASE_PUBLIC_URL (публічний хост Railway).
      Якщо DATABASE_PUBLIC_URL не задано — fallback на DATABASE_URL.
    """
    if IS_RAILWAY:
        url = DATABASE_URL
        source = "Railway internal (DATABASE_URL)"
    elif DATABASE_PUBLIC_URL:
        url = DATABASE_PUBLIC_URL
        source = "local dev (DATABASE_PUBLIC_URL)"
    else:
        url = DATABASE_URL
        source = "fallback (DATABASE_URL)"

    print(f"[DB] Connecting via {source}")

    try:
        conn = psycopg2.connect(url, connect_timeout=10)
    except psycopg2.OperationalError as e:
        print(f"[DB] Connection error: {redact(e)}")
        raise

    return conn


def іs_there_similar_embedding(cur,
                               chunk: dict,
                               embedding: list[float],
                               threshold: float = 0.95) -> bool:
    """Перевірка на наявність в БД схожого embedding.\n
    Значення threshold:\n
    0.98+ = майже гарантований дубль\n
    0.95-0.98 = дуже схожий текст\n
    0.90-0.95 = часто той самий зміст, але перефразовано\n
    <0.90 = зазвичай різний контент
    """
    check = False
    cur.execute(
        CHECK_FOR_SIMILAR_EMBEDDING,
        {
            "chunk_id": chunk["chunk_id"],
            "embedding": embedding,
            "threshold": threshold
        }
    )
    row = cur.fetchone()

    if row:
        chunk_id, product_slug, chunk_order, similarity = row
        check = True

        print(f"""
        similar embedding ----------
        chunk_id: {chunk_id},
        product_slug: {product_slug},
        chunk_order: {chunk_order},
        To new chunk----------------
        chunk_id: {chunk["chunk_id"]},
        product_slug: {chunk["product_slug"]},
        chunk_order: {chunk["order"]},
        ======== similarity: {float(similarity)} ========""")

    return check


def _upsert_chunk(chunk: dict) -> None:
    """Створює чи оновлює для вказаного chunk ембеддинг
    та зберігає цей чанк у БД."""
    conn = _conn_create()
    try:
        register_vector(conn)

        text_to_embed = f"{chunk['section_title']}\n{chunk['content']}"
        embedding = Vector(create_embedding(text_to_embed))

        with conn.cursor() as cur:
            if not іs_there_similar_embedding(cur, chunk, embedding):
                cur.execute(
                    UPSERT_CHUNK,
                    {
                        "chunk_id": chunk["chunk_id"],
                        "product_slug": chunk["product_slug"],
                        "section_key": chunk["section_key"],
                        "section_title": chunk["section_title"],
                        "content": chunk["content"],
                        "char_count": chunk["char_count"],
                        "tokens_approx": chunk["tokens_approx"],
                        "chunk_order": chunk["order"],
                        "metadata": json.dumps(chunk["metadata"]),
                        "embedding": embedding
                    }
                )

        conn.commit()
    finally:
        conn.close()


def bulk_upsert_chunks(
    chunks: list[dict],
    progress_callback = None,
    batch_size: int | None = None,
    pause_seconds: int | None = None,
    chunk_delay: float | None = None,
    delete_orphans: bool = False,
) -> None:
    """Оновлення списку чанків у БД з лімітом 45–50 чанків за партію та паузою 15 хв між ними.
    
    Це запобігає вичерпанню лімітів безкоштовного тарифу Gemini API (15 RPM / добові квоти).
    """
    import time
    from src.LLMProvider.budget import budget_manager

    if batch_size is None:
        batch_size = int(os.getenv("SYNC_BATCH_SIZE", "45"))
    if pause_seconds is None:
        pause_seconds = int(os.getenv("SYNC_BATCH_PAUSE_SECONDS", "900"))  # 15 хвилин
    if chunk_delay is None:
        chunk_delay = float(os.getenv("SYNC_CHUNK_DELAY_SECONDS", "1.0"))  # 1 сек між запитами в партії

    budget_manager.set_sync_mode(True)

    def _log(msg: str) -> None:
        print(f"[DB] {msg}", flush=True)
        if progress_callback:
            try:
                progress_callback(msg)
            except Exception as pe:
                print(f"[DB] progress_callback error: {redact(pe)}", flush=True)

    try:
        conn = _conn_create()
        existing_ids = set()
        try:
            register_vector(conn)
            with conn.cursor() as cur:
                new_ids = {chunk.get("chunk_id") for chunk in chunks if chunk.get("chunk_id")}
                try:
                    cur.execute("SELECT chunk_id FROM knowledge_chunks;")
                    existing_ids = {row[0] for row in cur.fetchall()}
                    
                    # Delete orphaned chunks ONLY during full sync when delete_orphans=True
                    if delete_orphans:
                        orphans = existing_ids - new_ids
                        if orphans:
                            _log(f"Видалення {len(orphans)} застарілих чанків із БД...")
                            orphans_list = list(orphans)
                            for i in range(0, len(orphans_list), 100):
                                batch = orphans_list[i:i+100]
                                format_strings = ','.join(['%s'] * len(batch))
                                cur.execute(f"DELETE FROM knowledge_chunks WHERE chunk_id IN ({format_strings})", tuple(batch))
                            conn.commit()
                except Exception as e:
                    _log(f"Помилка перевірки/видалення чанків: {redact(e)}")
                    conn.rollback()
        finally:
            conn.close()

        # Фільтруємо лише нові чанки, які дійсно потребують обчислення ембеддингів
        chunks_to_embed = [c for c in chunks if c.get("chunk_id") and c.get("chunk_id") not in existing_ids]
        total_new = len(chunks_to_embed)

        _log(f"Всього чанків: {len(chunks)}, вже у БД: {len(existing_ids)}, нових для генерації: {total_new}")

        if total_new == 0:
            _log("✅ Усі чанки вже мають вектори у базі знань. Нових позицій для генерації немає.")
            return

        total_batches = (total_new + batch_size - 1) // batch_size
        minutes_pause = pause_seconds // 60
        _log(
            f"📦 <b>План синхронізації:</b> {total_new} нових чанків буде оброблено "
            f"партіями по <b>{batch_size}</b> з паузою <b>{minutes_pause} хв</b> між ними (всього партій: {total_batches})."
        )

        embedded_count = 0
        for batch_idx in range(total_batches):
            batch = chunks_to_embed[batch_idx * batch_size : (batch_idx + 1) * batch_size]
            batch_num = batch_idx + 1
            start_num = embedded_count + 1
            end_num = embedded_count + len(batch)

            _log(f"⏳ Обробка партії <b>{batch_num}/{total_batches}</b> (чанки {start_num}–{end_num} з {total_new})...")

            batch_conn = _conn_create()
            try:
                register_vector(batch_conn)
                with batch_conn.cursor() as cur:
                    for chunk in batch:
                        chunk_id = chunk.get("chunk_id")
                        try:
                            text_to_embed = f"{chunk['section_title']}\n{chunk['content']}"
                            emb = create_embedding(text_to_embed)
                            if not emb:
                                continue
                            embedding = Vector(emb)
                            
                            if not іs_there_similar_embedding(cur, chunk, embedding):
                                cur.execute(
                                    UPSERT_CHUNK,
                                    {
                                        "chunk_id": chunk_id,
                                        "product_slug": chunk["product_slug"],
                                        "section_key": chunk["section_key"],
                                        "section_title": chunk["section_title"],
                                        "content": chunk["content"],
                                        "char_count": chunk["char_count"],
                                        "tokens_approx": chunk["tokens_approx"],
                                        "chunk_order": chunk.get("order", chunk.get("chunk_order", 0)),
                                        "metadata": json.dumps(chunk.get("metadata", {})),
                                        "embedding": embedding
                                    }
                                )
                                batch_conn.commit()
                                embedded_count += 1
                            if chunk_delay > 0:
                                time.sleep(chunk_delay)
                        except Exception as e:
                            _log(f"Помилка збереження чанку {chunk_id}: {redact(e)}")
                            batch_conn.rollback()
            finally:
                batch_conn.close()

            # Якщо це не остання партія — пауза 15 хвилин для дотримання безкоштовних лімітів Gemini
            if batch_idx < total_batches - 1:
                pause_msg = (
                    f"☕ Партія <b>{batch_num}/{total_batches}</b> завершена (збережено {embedded_count}/{total_new} чанків).\n"
                    f"⏳ Пауза <b>{minutes_pause} хвилин</b> для відновлення безкоштовних квот Gemini API ({batch_size} запитів/15 хв)..."
                )
                _log(pause_msg)
                
                # Спимо з кроком 15 секунд
                sleep_left = pause_seconds
                while sleep_left > 0:
                    step = min(15, sleep_left)
                    time.sleep(step)
                    sleep_left -= step

                _log(f"🔄 Відновлення синхронізації: переходимо до партії <b>{batch_num + 1}/{total_batches}</b>...")

        _log(f"🎉 <b>Успішно!</b> Всі {embedded_count} нових чанків збережено та індексовано у базі знань.")
    finally:
        budget_manager.set_sync_mode(False)


def upsert_file_of_chunks(pathFile: str) -> None:
    """Збереження чи оновлення чанків файлу в БД."""
    try:
        with open(pathFile, "r", encoding="utf-8") as f:
            chunks = json.load(f)

            for chunk in chunks:
                _upsert_chunk(chunk)

    except Exception as e:
        print(f"File error: {redact(e)}")


def upsert_dir_of_chunks(pathDir: str) -> None:
    """Збереження чи оновлення чанків файлів з директорії в БД."""
    try:
        folder = pathDir

        for pathFile in folder.glob("*.json"):
            upsert_file_of_chunks(pathFile)

    except Exception as e:
        print(f"Folder error: {redact(e)}")


def search_chunks(query: str, top_k: int = 5) -> list[dict]:
    """Пошук найближчих чанків у БД за косинусною схожістю.

    Args:
        query:  текст запиту від користувача.
        top_k:  кількість найближчих чанків для повернення.

    Returns:
        Список словників із полями chunk_id, content, section_title,
        product_slug та similarity.
    """

    query_embedding = create_embedding(query)
    if not query_embedding:
        return []

    conn = _conn_create()
    try:
        register_vector(conn)

        with conn.cursor() as cur:
            cur.execute(
                SEARCH_CHUNKS,
                {"embedding": Vector(query_embedding), "top_k": top_k}
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "chunk_id":      row[0],
            "content":       row[1],
            "section_title": row[2],
            "product_slug":  row[3],
            "similarity":    float(row[4]),
        }
        for row in rows
    ]


def creating_table_for_chunks() -> None:
    """Створення таблиці для чанків у БД."""
    conn = _conn_create()
    try:
        with conn.cursor() as cur:
            for command in CREATING_TABLE_KNOWLEDGE_CHUNKS:
                cur.execute(command)

        conn.commit()
    finally:
        conn.close()


CHECK_FOR_SIMILAR_EMBEDDING = """
SELECT
    chunk_id,
    product_slug,
    chunk_order,
    1 - (embedding <=> %(embedding)s) AS similarity
FROM knowledge_chunks
WHERE
    chunk_id <> %(chunk_id)s
    AND (1 - (embedding <=> %(embedding)s)) >= %(threshold)s
ORDER BY embedding <=> %(embedding)s
LIMIT 1
"""


SEARCH_CHUNKS = """
SELECT
    chunk_id,
    content,
    section_title,
    product_slug,
    1 - (embedding <=> %(embedding)s) AS similarity
FROM knowledge_chunks
ORDER BY embedding <=> %(embedding)s
LIMIT %(top_k)s
"""


UPSERT_CHUNK = """
INSERT INTO knowledge_chunks (
    chunk_id,
    product_slug,
    section_key,
    section_title,
    content,
    char_count,
    tokens_approx,
    chunk_order,
    metadata,
    embedding
)
VALUES (
    %(chunk_id)s,
    %(product_slug)s,
    %(section_key)s,
    %(section_title)s,
    %(content)s,
    %(char_count)s,
    %(tokens_approx)s,
    %(chunk_order)s,
    %(metadata)s,
    %(embedding)s
)
ON CONFLICT (chunk_id)
DO UPDATE SET
    content = EXCLUDED.content,
    metadata = EXCLUDED.metadata,
    embedding = EXCLUDED.embedding,
    char_count = EXCLUDED.char_count,
    tokens_approx = EXCLUDED.tokens_approx,
    updated_at = NOW();
"""


CREATING_TABLE_KNOWLEDGE_CHUNKS = [
    "CREATE EXTENSION IF NOT EXISTS vector;",
    
    """CREATE TABLE IF NOT EXISTS knowledge_chunks (
    chunk_id TEXT PRIMARY KEY,
    product_slug TEXT NOT NULL,
    section_key TEXT NOT NULL,
    section_title TEXT NOT NULL,
    content TEXT NOT NULL,
    char_count INTEGER NOT NULL,
    tokens_approx INTEGER NOT NULL,
    chunk_order INTEGER NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    embedding VECTOR(768),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
    );""",

    """CREATE INDEX IF NOT EXISTS idx_product_slug
    ON knowledge_chunks(product_slug);""",

    """CREATE INDEX IF NOT EXISTS idx_section_key
    ON knowledge_chunks(section_key);""",

    """CREATE INDEX IF NOT EXISTS idx_chunk_order
    ON knowledge_chunks(chunk_order);""",

    """CREATE INDEX IF NOT EXISTS idx_embedding
    ON knowledge_chunks
    USING hnsw (embedding vector_cosine_ops);"""
]
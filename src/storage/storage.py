# Standard
import os
import json
import psycopg2
from pgvector import Vector
from pgvector.psycopg2 import register_vector
# Local
from ..embedding import create_embedding


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
        conn = psycopg2.connect(url)
    except psycopg2.OperationalError as e:
        print(f"[DB] Connection error: {e}")
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
    register_vector(conn)

    embedding = Vector(create_embedding(chunk["content"]))

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
    conn.close()


def bulk_upsert_chunks(chunks: list[dict]) -> None:
    """Оновлення списку чанків у БД з використанням одного з'єднання (оптимізовано)."""
    conn = _conn_create()
    register_vector(conn)
    
    print(f"[DB] Bulk upserting {len(chunks)} chunks to knowledge_chunks...")
    with conn.cursor() as cur:
        # 1. Fetch existing chunk_ids to avoid re-embedding
        existing_ids = set()
        new_ids = {chunk.get("chunk_id") for chunk in chunks if chunk.get("chunk_id")}
        try:
            cur.execute("SELECT chunk_id FROM knowledge_chunks;")
            existing_ids = {row[0] for row in cur.fetchall()}
            
            # Delete orphaned chunks (chunks that exist in DB but not in the new MD files)
            orphans = existing_ids - new_ids
            if orphans:
                print(f"[DB] Deleting {len(orphans)} orphaned chunks...")
                # SQLite and Postgres handle IN differently if the list is huge, 
                # but for 300 chunks it's fine. We do it in batches of 100 just in case.
                orphans_list = list(orphans)
                for i in range(0, len(orphans_list), 100):
                    batch = orphans_list[i:i+100]
                    format_strings = ','.join(['%s'] * len(batch))
                    cur.execute(f"DELETE FROM knowledge_chunks WHERE chunk_id IN ({format_strings})", tuple(batch))
                conn.commit()
                
        except Exception as e:
            print(f"[!] Error fetching/deleting existing chunk_ids: {e}")
            conn.rollback()
            
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id")
            if chunk_id in existing_ids:
                continue
                
            try:
                emb = create_embedding(chunk["content"])
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
                    conn.commit() # Commit after each insert to make it visible
            except Exception as e:
                print(f"[!] Error upserting chunk {chunk_id}: {e}")
                conn.rollback()
                
    conn.close()


def upsert_file_of_chunks(pathFile: str) -> None:
    """Збереження чи оновлення чанків файлу в БД."""
    try:
        with open(pathFile, "r", encoding="utf-8") as f:
            chunks = json.load(f)

            for chunk in chunks:
                _upsert_chunk(chunk)

    except Exception as e:
        print(f"File error: {e}")


def upsert_dir_of_chunks(pathDir: str) -> None:
    """Збереження чи оновлення чанків файлів з директорії в БД."""
    try:
        folder = pathDir

        for pathFile in folder.glob("*.json"):
            upsert_file_of_chunks(pathFile)

    except Exception as e:
        print(f"Folder error: {e}")


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

    conn = _conn_create()
    register_vector(conn)

    with conn.cursor() as cur:
        cur.execute(
            SEARCH_CHUNKS,
            {"embedding": Vector(query_embedding), "top_k": top_k}
        )
        rows = cur.fetchall()

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

    with conn.cursor() as cur:
        for command in CREATING_TABLE_KNOWLEDGE_CHUNKS:
            cur.execute(command)

    conn.commit()
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
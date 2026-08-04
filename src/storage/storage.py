# Standard
import os
import json
# Special
import psycopg2
from pgvector.psycopg2 import register_vector
# Local
from ..embedding import create_embedding


PGDATABASE = os.getenv("PGDATABASE", "")
PGUSER = os.getenv("PGUSER", "")
PGPASSWORD = os.getenv("PGPASSWORD", "")
PGHOST = os.getenv("PGHOST", "")
PGPORT = os.getenv("PGPORT", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
DATABASE_PUBLIC_URL = os.getenv("DATABASE_PUBLIC_URL", "")

# Railway sometimes returns "postgres://" instead of "postgresql://" —
# — here’s the fix.
if DATABASE_URL.startswith("postgres://"):
    print(DATABASE_URL)
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    print(DATABASE_URL)


def _conn_create():
    """Створення зв'язку з БД."""
    try:
        # Creating connect with DB
        conn = psycopg2.connect(DATABASE_URL)
    # conn = psycopg2.connect(
    #     dbname=PGDATABASE,
    #     user=PGUSER,
    #     password=PGPASSWORD,
    #     host=PGHOST,
    #     port=PGPORT
    # )

    except psycopg2.OperationalError as e:
        print(f"Error: {e}")

    return conn


def _upsert_chunk(chunk: dict) -> None:
    """Створює чи оновлює для вказаного chunk ембеддинг
    та зберігає цей чанк у БД."""
    conn = _conn_create()
    register_vector(conn)

    embedding = create_embedding(chunk.content)

    with conn.cursor() as cur:
        cur.execute(
            UPSERT_CHUNK,
            {
                "chunk_id": chunk.chunk_id,
                "product_slug": chunk.product_slug,
                "section_key": chunk.section_key,
                "section_title": chunk.section_title,
                "content": chunk.content,
                "char_count": chunk.char_count,
                "tokens_approx": chunk.tokens_approx,
                "chunk_order": chunk.order,
                "metadata": json.dumps(chunk.metadata),
                "embedding": embedding
            }
        )

    conn.commit()
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


def creating_table_for_chunks() -> None:
    """Створення таблиці для чанків у БД."""
    conn = _conn_create()

    with conn.cursor() as cur:
        for command in CREATING_TABLE_KNOWLEDGE_CHUNKS:
            cur.execute(command)

    conn.commit()
    conn.close()


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
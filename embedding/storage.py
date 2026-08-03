# CREATE EXTENSION IF NOT EXISTS vector;

# CREATE TABLE knowledge_chunks (
#     chunk_id TEXT PRIMARY KEY,
#     product_slug TEXT NOT NULL,
#     section_key TEXT NOT NULL,
#     section_title TEXT NOT NULL,
#     content TEXT NOT NULL,
#     char_count INTEGER NOT NULL,
#     tokens_approx INTEGER NOT NULL,
#     chunk_order INTEGER NOT NULL,
#     metadata JSONB NOT NULL DEFAULT '{}',
#     embedding VECTOR(768),
#     created_at TIMESTAMP DEFAULT NOW(),
#     updated_at TIMESTAMP DEFAULT NOW()
# );

# CREATE INDEX knowledge_chunks_embedding_idx
# ON knowledge_chunks
# USING hnsw (embedding vector_cosine_ops);

UPSERT_SQL = """
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
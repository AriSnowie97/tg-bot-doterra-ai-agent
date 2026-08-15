"""
doTERRA Bot — Модуль зворотного зв'язку (👍/👎)

Таблиця response_feedback:
    - message_id   — ID повідомлення-відповіді бота
    - chat_id      — ID чату (для унікальності ключа)
    - user_id      — хто проголосував
    - vote         — 'like' | 'dislike'
    - query_text   — питання користувача (для аналізу)
    - created_at

Кожен користувач може проголосувати лише один раз за відповідь.
Повторний голос того ж типу — ігнорується.
Зміна голосу (like → dislike) — дозволяється.
"""

from __future__ import annotations
import psycopg2
from src.storage.storage import _conn_create


# ── DDL ──────────────────────────────────────────────────────────────────────

_CREATE_FEEDBACK_TABLE = """
CREATE TABLE IF NOT EXISTS response_feedback (
    id          SERIAL PRIMARY KEY,
    message_id  BIGINT      NOT NULL,
    chat_id     BIGINT      NOT NULL,
    user_id     BIGINT      NOT NULL,
    vote        VARCHAR(10) NOT NULL CHECK (vote IN ('like', 'dislike')),
    query_text  TEXT,
    created_at  TIMESTAMP   DEFAULT NOW(),
    UNIQUE (message_id, chat_id, user_id)
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_feedback_msg
    ON response_feedback (message_id, chat_id);
"""


def ensure_feedback_table() -> None:
    """Створює таблицю response_feedback якщо вона не існує."""
    conn = _conn_create()
    with conn.cursor() as cur:
        cur.execute(_CREATE_FEEDBACK_TABLE)
        cur.execute(_CREATE_INDEX)
    conn.commit()
    conn.close()


# ── Запис голосу ─────────────────────────────────────────────────────────────

def save_vote(
    message_id: int,
    chat_id: int,
    user_id: int,
    vote: str,
    query_text: str = "",
) -> str:
    """Зберігає або оновлює голос користувача.

    Returns:
        'inserted'  — новий голос
        'updated'   — змінено попередній голос
        'unchanged' — той самий голос, нічого не змінилось
    """
    conn = _conn_create()
    try:
        with conn.cursor() as cur:
            # Перевіряємо чи вже є голос від цього юзера
            cur.execute(
                "SELECT vote FROM response_feedback "
                "WHERE message_id = %s AND chat_id = %s AND user_id = %s",
                (message_id, chat_id, user_id),
            )
            row = cur.fetchone()

            if row is None:
                # Новий голос
                cur.execute(
                    """
                    INSERT INTO response_feedback
                        (message_id, chat_id, user_id, vote, query_text)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (message_id, chat_id, user_id, vote, query_text or ""),
                )
                conn.commit()
                return "inserted"

            existing_vote = row[0]
            if existing_vote == vote:
                return "unchanged"

            # Зміна голосу
            cur.execute(
                """
                UPDATE response_feedback
                SET vote = %s, created_at = NOW()
                WHERE message_id = %s AND chat_id = %s AND user_id = %s
                """,
                (vote, message_id, chat_id, user_id),
            )
            conn.commit()
            return "updated"

    finally:
        conn.close()


# ── Лічильники ───────────────────────────────────────────────────────────────

def get_vote_counts(message_id: int, chat_id: int) -> dict[str, int]:
    """Повертає кількість лайків і дизлайків для повідомлення.

    Returns:
        {"likes": N, "dislikes": M}
    """
    conn = _conn_create()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT vote, COUNT(*) FROM response_feedback
                WHERE message_id = %s AND chat_id = %s
                GROUP BY vote
                """,
                (message_id, chat_id),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    counts = {"likes": 0, "dislikes": 0}
    for vote, count in rows:
        if vote == "like":
            counts["likes"] = count
        elif vote == "dislike":
            counts["dislikes"] = count
    return counts

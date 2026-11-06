"""
doTERRA Bot — довготривала пам'ять про особливості користувача.

Таблиця user_memory (одна строка на користувача Telegram, спільна для особистого чату і груп):
    - user_id    — Telegram user_id
    - consent    — NULL: ще не питали, TRUE: дозволив запам'ятовувати, FALSE: відмовився
    - tags       — перелік дозволених міток (вагітність, діти, хронічні стани тощо)
    - allergies  — до MAX_ALLERGIES назв речовин-алергенів (одне слово, лише літери)
    - updated_at

Принципи приватності:
    - зберігаються лише мітки з фіксованого словника та алергени, а не сирий текст повідомлень;
    - без згоди користувача нічого не записується і не читається;
    - пам'ять стирається командами /start та /forget, а також коли користувач
      блокує або видаляє бота.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.storage.storage import _conn_create

MAX_ALLERGIES = 8

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS user_memory (
    user_id    BIGINT PRIMARY KEY,
    consent    BOOLEAN,
    tags       TEXT[]      NOT NULL DEFAULT '{}',
    allergies  TEXT[]      NOT NULL DEFAULT '{}',
    updated_at TIMESTAMP   NOT NULL DEFAULT NOW()
);
"""


@dataclass
class StoredMemory:
    consent: bool | None = None
    tags: set[str] = field(default_factory=set)
    allergies: list[str] = field(default_factory=list)

    @property
    def active(self) -> bool:
        return self.consent is True


def ensure_user_memory_table() -> None:
    conn = _conn_create()
    try:
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE)
        conn.commit()
    finally:
        conn.close()


def get_memory(user_id: int) -> StoredMemory:
    """Повертає збережений стан пам'яті. Для невідомого користувача consent=None."""
    conn = _conn_create()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT consent, tags, allergies FROM user_memory WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        return StoredMemory()
    consent, tags, allergies = row
    return StoredMemory(consent=consent, tags=set(tags or []), allergies=list(allergies or []))


def set_consent(user_id: int, consent: bool) -> None:
    """Зберігає рішення користувача. Відмова одразу стирає всі збережені факти."""
    conn = _conn_create()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_memory (user_id, consent, tags, allergies, updated_at)
                VALUES (%s, %s, '{}', '{}', NOW())
                ON CONFLICT (user_id) DO UPDATE
                SET consent = EXCLUDED.consent,
                    tags = CASE WHEN EXCLUDED.consent THEN user_memory.tags ELSE '{}' END,
                    allergies = CASE WHEN EXCLUDED.consent THEN user_memory.allergies ELSE '{}' END,
                    updated_at = NOW()
                """,
                (user_id, consent),
            )
        conn.commit()
    finally:
        conn.close()


def merge_facts(user_id: int, tags: set[str], allergies: list[str]) -> StoredMemory | None:
    """Додає факти до профілю, лише якщо користувач дав згоду. Повертає оновлений профіль."""
    conn = _conn_create()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tags, allergies FROM user_memory WHERE user_id = %s AND consent IS TRUE FOR UPDATE",
                (user_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            merged_tags = sorted(set(row[0] or []) | set(tags))
            merged_allergies = list(dict.fromkeys([*(row[1] or []), *allergies]))[:MAX_ALLERGIES]
            cur.execute(
                "UPDATE user_memory SET tags = %s, allergies = %s, updated_at = NOW() WHERE user_id = %s",
                (merged_tags, merged_allergies, user_id),
            )
        conn.commit()
    finally:
        conn.close()
    return StoredMemory(consent=True, tags=set(merged_tags), allergies=merged_allergies)


def delete_memory(user_id: int) -> bool:
    """Повністю видаляє запис користувача (факти і рішення про згоду). True, якщо щось було."""
    conn = _conn_create()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_memory WHERE user_id = %s", (user_id,))
            deleted = cur.rowcount > 0
        conn.commit()
    finally:
        conn.close()
    return deleted

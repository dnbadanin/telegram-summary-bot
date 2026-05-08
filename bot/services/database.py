import json
import logging
from datetime import datetime, date
from typing import Any

import aiosqlite

from bot.config import DATABASE_PATH

logger = logging.getLogger(__name__)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS chats (
    chat_id INTEGER PRIMARY KEY,
    chat_title TEXT,
    chat_type TEXT,
    in_group_post BOOLEAN DEFAULT 0,
    active BOOLEAN DEFAULT 1,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER,
    message_id INTEGER,
    user_id INTEGER,
    username TEXT,
    first_name TEXT,
    text TEXT,
    has_media BOOLEAN DEFAULT 0,
    media_type TEXT,
    links TEXT,
    timestamp TIMESTAMP,
    FOREIGN KEY (chat_id) REFERENCES chats(chat_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_time ON messages(chat_id, timestamp);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    chat_id INTEGER,
    active BOOLEAN DEFAULT 1,
    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, chat_id)
);

CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER,
    summary_date DATE,
    content TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chat_id, summary_date)
);

CREATE TABLE IF NOT EXISTS upload_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    local_path TEXT,
    remote_path TEXT,
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript(_CREATE_SQL)
        # Migration: add active column if it doesn't exist yet
        try:
            await db.execute("ALTER TABLE chats ADD COLUMN active BOOLEAN DEFAULT 1")
            await db.commit()
            logger.info("Migrated chats table: added active column")
        except Exception:
            pass  # column already exists
    logger.info("Database initialised at %s", DATABASE_PATH)


async def upsert_chat(chat_id: int, title: str, chat_type: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO chats (chat_id, chat_title, chat_type, active)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(chat_id) DO UPDATE SET chat_title=excluded.chat_title, active=1
            """,
            (chat_id, title, chat_type),
        )
        await db.commit()


async def get_all_chats() -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM chats WHERE active = 1") as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def set_chat_active(chat_id: int, active: bool) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE chats SET active = ? WHERE chat_id = ?",
            (int(active), chat_id),
        )
        await db.commit()
    logger.info("Chat %s active=%s", chat_id, active)


async def get_chat(chat_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM chats WHERE chat_id = ?", (chat_id,)) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def set_in_group_post(chat_id: int, enabled: bool) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE chats SET in_group_post = ? WHERE chat_id = ?",
            (int(enabled), chat_id),
        )
        await db.commit()


async def save_message(
    *,
    chat_id: int,
    message_id: int,
    user_id: int,
    username: str | None,
    first_name: str | None,
    text: str | None,
    has_media: bool,
    media_type: str | None,
    links: list[str],
    timestamp: datetime,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO messages
              (chat_id, message_id, user_id, username, first_name, text,
               has_media, media_type, links, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                message_id,
                user_id,
                username,
                first_name,
                text,
                int(has_media),
                media_type,
                json.dumps(links, ensure_ascii=False),
                timestamp.isoformat(),
            ),
        )
        await db.commit()


async def get_messages_since(chat_id: int, since: datetime) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM messages WHERE chat_id = ? AND timestamp >= ? ORDER BY timestamp",
            (chat_id, since.isoformat()),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) | {"links": json.loads(dict(r)["links"] or "[]")} for r in rows]


async def add_subscription(user_id: int, chat_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO subscriptions (user_id, chat_id, active)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, chat_id) DO UPDATE SET active=1
            """,
            (user_id, chat_id),
        )
        await db.commit()


async def remove_subscription(user_id: int, chat_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE subscriptions SET active=0 WHERE user_id=? AND chat_id=?",
            (user_id, chat_id),
        )
        await db.commit()


async def get_subscriptions(user_id: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT s.*, c.chat_title FROM subscriptions s
            JOIN chats c ON s.chat_id = c.chat_id
            WHERE s.user_id = ? AND s.active = 1
            """,
            (user_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_subscribers(chat_id: int) -> list[int]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT user_id FROM subscriptions WHERE chat_id=? AND active=1",
            (chat_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [r[0] for r in rows]


async def deactivate_subscription(user_id: int, chat_id: int) -> None:
    await remove_subscription(user_id, chat_id)


async def get_cached_summary(chat_id: int, summary_date: date) -> str | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT content FROM summaries WHERE chat_id=? AND summary_date=?",
            (chat_id, summary_date.isoformat()),
        ) as cur:
            row = await cur.fetchone()
    return row[0] if row else None


async def save_summary(chat_id: int, summary_date: date, content: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO summaries (chat_id, summary_date, content)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id, summary_date) DO UPDATE SET content=excluded.content,
                generated_at=CURRENT_TIMESTAMP
            """,
            (chat_id, summary_date.isoformat(), content),
        )
        await db.commit()


async def enqueue_upload(local_path: str, remote_path: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO upload_queue (local_path, remote_path) VALUES (?, ?)",
            (local_path, remote_path),
        )
        await db.commit()


async def get_pending_uploads() -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM upload_queue WHERE attempts < 3 ORDER BY created_at"
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def update_upload_attempt(upload_id: int, error: str | None) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE upload_queue SET attempts=attempts+1, last_error=? WHERE id=?",
            (error, upload_id),
        )
        await db.commit()


async def delete_upload_queue_entry(upload_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM upload_queue WHERE id=?", (upload_id,))
        await db.commit()


async def count_today_messages(chat_id: int, since: datetime) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM messages WHERE chat_id=? AND timestamp>=?",
            (chat_id, since.isoformat()),
        ) as cur:
            row = await cur.fetchone()
    return row[0] if row else 0


async def purge_old_messages(retention_days: int) -> None:
    if retention_days <= 0:
        return
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM messages WHERE timestamp < datetime('now', ? || ' days')",
            (f"-{retention_days}",),
        )
        await db.commit()

import asyncio
import os
import tempfile
from datetime import datetime, timezone, date

import pytest
import pytest_asyncio

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("YANDEX_DISK_TOKEN", "test")


@pytest_asyncio.fixture
async def db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr("bot.config.DATABASE_PATH", db_file)
    import bot.services.database as db_mod
    monkeypatch.setattr(db_mod, "DATABASE_PATH", db_file)
    await db_mod.init_db()
    return db_mod


@pytest.mark.asyncio
async def test_upsert_and_get_chat(db):
    await db.upsert_chat(-100123, "Test Chat", "supergroup")
    chat = await db.get_chat(-100123)
    assert chat is not None
    assert chat["chat_title"] == "Test Chat"
    assert chat["chat_type"] == "supergroup"


@pytest.mark.asyncio
async def test_upsert_chat_updates_title(db):
    await db.upsert_chat(-100123, "Old Title", "supergroup")
    await db.upsert_chat(-100123, "New Title", "supergroup")
    chat = await db.get_chat(-100123)
    assert chat["chat_title"] == "New Title"


@pytest.mark.asyncio
async def test_save_and_get_messages(db):
    await db.upsert_chat(-100123, "Chat", "supergroup")
    ts = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    await db.save_message(
        chat_id=-100123,
        message_id=1,
        user_id=42,
        username="alice",
        first_name="Alice",
        text="Hello world https://example.com",
        has_media=False,
        media_type=None,
        links=["https://example.com"],
        timestamp=ts,
    )
    since = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
    messages = await db.get_messages_since(-100123, since)
    assert len(messages) == 1
    assert messages[0]["username"] == "alice"
    assert "https://example.com" in messages[0]["links"]


@pytest.mark.asyncio
async def test_subscription_lifecycle(db):
    await db.upsert_chat(-100456, "Another Chat", "group")
    await db.add_subscription(user_id=99, chat_id=-100456)
    subs = await db.get_subscriptions(99)
    assert len(subs) == 1
    assert subs[0]["chat_id"] == -100456

    subscribers = await db.get_subscribers(-100456)
    assert 99 in subscribers

    await db.remove_subscription(99, -100456)
    subs = await db.get_subscriptions(99)
    assert len(subs) == 0


@pytest.mark.asyncio
async def test_summary_cache(db):
    await db.upsert_chat(-100789, "Summary Chat", "supergroup")
    d = date(2024, 1, 15)
    cached = await db.get_cached_summary(-100789, d)
    assert cached is None

    await db.save_summary(-100789, d, "## Тема: Тест\nКраткое резюме.")
    cached = await db.get_cached_summary(-100789, d)
    assert cached is not None
    assert "Тема: Тест" in cached


@pytest.mark.asyncio
async def test_upload_queue(db):
    await db.enqueue_upload("/tmp/file.jpg", "/TelegramBot/Chat/2024-01-15/images/1_file.jpg")
    items = await db.get_pending_uploads()
    assert len(items) == 1
    item_id = items[0]["id"]

    await db.update_upload_attempt(item_id, "Connection error")
    items = await db.get_pending_uploads()
    assert items[0]["attempts"] == 1
    assert items[0]["last_error"] == "Connection error"

    await db.delete_upload_queue_entry(item_id)
    items = await db.get_pending_uploads()
    assert len(items) == 0


@pytest.mark.asyncio
async def test_set_in_group_post(db):
    await db.upsert_chat(-100111, "Group", "group")
    await db.set_in_group_post(-100111, True)
    chat = await db.get_chat(-100111)
    assert chat["in_group_post"] == 1

    await db.set_in_group_post(-100111, False)
    chat = await db.get_chat(-100111)
    assert chat["in_group_post"] == 0

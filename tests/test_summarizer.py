import os
import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("YANDEX_DISK_TOKEN", "test")

from bot.utils.text_formatter import format_messages_for_prompt, split_long_message


def test_format_messages_basic():
    messages = [
        {
            "timestamp": "2024-01-15T10:30:00",
            "username": "alice",
            "first_name": "Alice",
            "text": "Hello everyone",
            "has_media": False,
        },
        {
            "timestamp": "2024-01-15T10:31:00",
            "username": None,
            "first_name": "Bob",
            "text": "Hi Alice!",
            "has_media": False,
        },
    ]
    result = format_messages_for_prompt(messages)
    assert "[10:30] alice: Hello everyone" in result
    assert "[10:31] Bob: Hi Alice!" in result


def test_format_messages_media():
    messages = [
        {
            "timestamp": "2024-01-15T09:00:00",
            "username": "carol",
            "first_name": "Carol",
            "text": None,
            "has_media": True,
        }
    ]
    result = format_messages_for_prompt(messages)
    assert "[медиа]" in result


def test_format_messages_empty():
    assert format_messages_for_prompt([]) == ""


def test_split_long_message_short():
    text = "Короткое сообщение"
    parts = split_long_message(text, limit=4096)
    assert parts == [text]


def test_split_long_message_exact_limit():
    text = "x" * 4096
    parts = split_long_message(text, limit=4096)
    assert len(parts) == 1


def test_split_long_message_over_limit():
    line = "Строка текста\n"
    text = line * 350  # ~4900 chars
    parts = split_long_message(text, limit=4096)
    assert len(parts) == 2
    for part in parts:
        assert len(part) <= 4096


def test_split_long_message_no_newlines():
    text = "a" * 5000
    parts = split_long_message(text, limit=4096)
    assert len(parts) == 2
    assert len(parts[0]) == 4096
    assert len(parts[1]) == 904

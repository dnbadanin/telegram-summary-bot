import os
import re

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("YANDEX_DISK_TOKEN", "test")

import bot.services.yandex_disk as yd


def test_sanitize_removes_forbidden_chars():
    assert yd._sanitize("Chat/Name:Test*?") == "Chat_Name_Test__"


def test_sanitize_normal_name():
    assert yd._sanitize("Обычный чат") == "Обычный чат"


def test_image_remote_path():
    path = yd._image_remote_path("My Chat", "2024-01-15", 42, "photo.jpg")
    assert path == "/TelegramBot/My Chat/2024-01-15/images/42_photo.jpg"


def test_image_remote_path_special_chars():
    path = yd._image_remote_path("Chat/Test", "2024-01-15", 1, "img.jpg")
    assert "/" not in path.split("/TelegramBot/")[1].split("/")[0]


def test_links_remote_path():
    path = yd._links_remote_path("Dev Team", "2024-03-20")
    assert path == "/TelegramBot/Dev Team/2024-03-20/links.txt"


def test_link_extractor_http():
    from bot.utils.link_extractor import extract_links
    links = extract_links("Check this out https://example.com and http://test.org/page")
    assert "https://example.com" in links
    assert "http://test.org/page" in links


def test_link_extractor_no_links():
    from bot.utils.link_extractor import extract_links
    assert extract_links("Just some plain text") == []


def test_link_extractor_none():
    from bot.utils.link_extractor import extract_links
    assert extract_links(None) == []


def test_link_extractor_filters_non_http():
    from bot.utils.link_extractor import extract_links
    links = extract_links("Visit ftp://files.example.com for files")
    assert all(l.startswith("http") for l in links)
